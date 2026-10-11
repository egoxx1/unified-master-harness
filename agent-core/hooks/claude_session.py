#!/usr/bin/env python3
"""Claude Code lifecycle hooks for V4: verification tracking, session context, compaction snapshots.

One script, dispatched on hook_event_name:

- PostToolUse   record code edits and verification runs for this session
                (.agent-state/sessions/<session>.jsonl; the transcript can lag, this file does not)
- Stop          if code was edited after the last verification, show the user a warning
                (warning only: it never blocks or sends Claude back to work) and log it
- PreCompact    save a short snapshot (recent requests, edited files, last checks) before compaction
- SessionStart  give Claude a short situational brief; after compaction, re-inject the snapshot

Every path is best-effort: any failure exits 0 without output so a hook can never break a session.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
from hook_log import command_shape, record  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / '.agent-state'
SESSIONS = STATE / 'sessions'
EDIT_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}
VERIFY_SKILLS = {'dev-verify', 'dev-ui-verify'}
NON_CODE_SUFFIXES = {'.md', '.mdx', '.txt', '.rst', '.adoc'}
VERIFY_COMMAND = re.compile(
    r'(?:^|[\s;&|(])(?:'
    r'pytest|py\.test|tox|nox|mypy|pyright|ruff|flake8|pylint|black\s+--check|'
    r'python3?(?:\.\d+)?\s+(?:-B\s+)?-m\s+(?:pytest|unittest|mypy|ruff)|'
    r'(?:npm|pnpm|yarn|bun)(?:\s+run)?\s+(?:test|lint|typecheck|type-check|check|build|e2e|verify)\b|'
    r'npx\s+(?:tsc|vitest|jest|playwright|eslint|cypress)|tsc|vitest|jest|eslint|playwright\s+test|cypress\s+run|'
    r'cargo\s+(?:test|check|clippy|build)|go\s+(?:test|vet|build)|make\s+(?:test|check|lint|build|verify)|'
    r'gradle\w*\s+(?:test|check|build)|\./gradlew\s+(?:test|check|build)|mvn\s+(?:test|verify|package)|'
    r'dotnet\s+(?:test|build)|swift\s+(?:test|build)|rspec|phpunit|deno\s+(?:test|check)|'
    r'python3?\s+(?:-B\s+)?agent-core/scripts/(?:check_agent_config|provider_smoke|run_evals)\.py'
    r')')
MAX_CONTEXT = 1800


def session_file(session_id: str) -> Path:
    safe = re.sub(r'[^A-Za-z0-9_-]', '', session_id or 'unknown')[:80] or 'unknown'
    return SESSIONS / f'{safe}.jsonl'


def append(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry['ts'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def project_relative(file_path: str) -> str | None:
    try:
        resolved = Path(file_path).resolve()
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return None


# ------------------------------------------------------------------ PostToolUse

def on_post_tool_use(event: dict) -> None:
    tool = str(event.get('tool_name', ''))
    data = event.get('tool_input') or {}
    path = session_file(str(event.get('session_id', '')))
    if tool in EDIT_TOOLS:
        rel = project_relative(str(data.get('file_path') or data.get('notebook_path') or ''))
        if rel and not rel.startswith('.agent-state/') and Path(rel).suffix.lower() not in NON_CODE_SUFFIXES:
            append(path, {'kind': 'edit', 'file': rel})
    elif tool == 'Bash':
        command = str(data.get('command', ''))
        if VERIFY_COMMAND.search(command):
            append(path, {'kind': 'verify', 'what': command_shape(command)})
    elif tool == 'Skill':
        name = str(data.get('skill') or data.get('command') or data.get('name') or '')
        if name in VERIFY_SKILLS:
            append(path, {'kind': 'verify', 'what': f'skill {name}'})
    elif tool.startswith('mcp__') and re.search(r'playwright|browser', tool, re.I):
        append(path, {'kind': 'verify', 'what': 'browser check'})


# ------------------------------------------------------------------ Stop

def unverified_edits(rows: list[dict]) -> tuple[list[str], str]:
    """Files edited after the last verification, and the timestamp of the last such edit."""
    pending: list[str] = []
    last_ts = ''
    for row in rows:
        if row.get('kind') == 'verify':
            pending, last_ts = [], ''
        elif row.get('kind') == 'edit':
            if row.get('file') not in pending:
                pending.append(row.get('file'))
            last_ts = row.get('ts', '')
    return pending, last_ts


def on_stop(event: dict) -> None:
    path = session_file(str(event.get('session_id', '')))
    rows = load(path)
    pending, last_ts = unverified_edits(rows)
    if not pending:
        return
    if any(r.get('kind') == 'warned' and r.get('edit_ts') == last_ts for r in rows):
        return  # already warned about exactly this state
    append(path, {'kind': 'warned', 'edit_ts': last_ts})
    shown = ', '.join(pending[:5]) + (f' and {len(pending) - 5} more' if len(pending) > 5 else '')
    message = (f'V4 verification warning: code was edited but no test, build or run check followed ({shown}). '
               'Ask for verification (dev-verify) before accepting the work as done.')
    record('claude', 'Stop', {'command': 'unverified-completion'}, 'warn',
           SimpleNamespace(action='warn', kind='verification', reason=f'{len(pending)} edited file(s) without verification'))
    print(json.dumps({'systemMessage': message}, ensure_ascii=False))


# ------------------------------------------------------------------ PreCompact

def recent_user_requests(transcript: str, limit: int = 3) -> list[str]:
    requests: list[str] = []
    try:
        lines = Path(transcript).read_text(encoding='utf-8', errors='ignore').splitlines()
    except OSError:
        return requests
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get('type') != 'user':
            continue
        content = (item.get('message') or {}).get('content')
        text = ''
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = ' '.join(c.get('text', '') for c in content if isinstance(c, dict) and c.get('type') == 'text')
        text = ' '.join(text.split())
        if text and not text.startswith('<'):
            requests.append(text[:300])
    return requests[-limit:]


def on_pre_compact(event: dict) -> None:
    sid = str(event.get('session_id', ''))
    rows = load(session_file(sid))
    edited = list(dict.fromkeys(r['file'] for r in rows if r.get('kind') == 'edit'))[-15:]
    checks = [r.get('what', '') for r in rows if r.get('kind') == 'verify'][-5:]
    pending, _ = unverified_edits(rows)
    lines = ['# V4 pre-compaction snapshot', f"saved: {time.strftime('%Y-%m-%d %H:%M:%S')}", '', '## Recent user requests']
    lines += [f'- {r}' for r in recent_user_requests(str(event.get('transcript_path', '')))] or ['- (not available)']
    lines += ['', '## Files edited this session'] + ([f'- {f}' for f in edited] or ['- none'])
    lines += ['', '## Verification run this session'] + ([f'- {c}' for c in checks] or ['- none'])
    if pending:
        lines += ['', '## Edited after the last verification (still unverified)'] + [f'- {f}' for f in pending]
    out = session_file(sid).with_suffix('.precompact.md')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')


# ------------------------------------------------------------------ SessionStart

def active_tasks(limit: int = 5) -> list[str]:
    skip = {'sessions', 'growth', 'evals', 'upgrade-backup', 'backups'}
    found = []
    cutoff = time.time() - 14 * 86400
    if not STATE.is_dir():
        return found
    for directory in STATE.iterdir():
        if not directory.is_dir() or directory.name in skip:
            continue
        try:
            mtime = max((p.stat().st_mtime for p in directory.rglob('*') if p.is_file()), default=directory.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            continue
        summary = ''
        for name in ('progress.md', 'handoff.md', 'PLAN.md', 'plan.md', 'state.md'):
            note = directory / name
            if note.is_file():
                first = next((l.strip('# ').strip() for l in note.read_text(encoding='utf-8', errors='ignore').splitlines() if l.strip()), '')
                summary = f' — {first[:140]}' if first else ''
                break
        found.append((mtime, f"- .agent-state/{directory.name}/ (updated {time.strftime('%Y-%m-%d', time.localtime(mtime))}){summary}"))
    return [line for _, line in sorted(found, reverse=True)[:limit]]


def recent_blocks(days: int = 7) -> str:
    log = STATE / 'hook-log.jsonl'
    if not log.exists():
        return ''
    cutoff = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - days * 86400))
    counts: dict[str, int] = {}
    for row in load(log):
        if row.get('ts', '') >= cutoff:
            counts[row.get('kind') or 'policy'] = counts.get(row.get('kind') or 'policy', 0) + 1
    return ', '.join(f'{k} {v}' for k, v in sorted(counts.items()))


def prune_sessions(days: int = 14) -> None:
    if not SESSIONS.is_dir():
        return
    cutoff = time.time() - days * 86400
    for path in SESSIONS.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def on_session_start(event: dict) -> None:
    source = str(event.get('source', ''))
    if source == 'startup':
        prune_sessions()
    parts: list[str] = []
    if source == 'compact':
        snapshot = session_file(str(event.get('session_id', ''))).with_suffix('.precompact.md')
        if snapshot.is_file():
            parts.append('Context was just compacted. Snapshot saved by the V4 PreCompact hook:\n'
                         + snapshot.read_text(encoding='utf-8', errors='ignore')[:1200])
    tasks = active_tasks()
    if tasks:
        parts.append('Recent task state under .agent-state (read before redoing work; AGENTS.md section 14):\n' + '\n'.join(tasks))
    blocks = recent_blocks()
    if blocks:
        parts.append(f'V4 hook decisions in the last 7 days: {blocks}. Do not retry blocked calls; ask the user instead.')
    record_path = STATE / 'provider-versions.json'
    if record_path.exists():
        try:
            claude = json.loads(record_path.read_text(encoding='utf-8')).get('claude') or {}
            if claude.get('result') and claude.get('result') != 'PASS':
                parts.append(f"Last V4 provider smoke test for Claude Code: {claude.get('result')}. Harness protections may be degraded.")
        except (OSError, json.JSONDecodeError):
            pass
    if not parts:
        return
    text = 'V4 harness session brief\n\n' + '\n\n'.join(parts)
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': text[:MAX_CONTEXT]}},
                     ensure_ascii=False))


HANDLERS = {'PostToolUse': on_post_tool_use, 'Stop': on_stop, 'PreCompact': on_pre_compact, 'SessionStart': on_session_start}


def main() -> int:
    try:
        event = json.load(sys.stdin)
        handler = HANDLERS.get(str(event.get('hook_event_name', '')))
        if handler:
            handler(event)
    except Exception:
        return 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
