#!/usr/bin/env python3
"""Efficiency benchmark: the same small tasks with and without the harness, on Claude Code.

For every task and repetition, two disposable copies of bench/project/ are made:
  bare     the project alone
  harness  the project with V4 installed by install/apply.py
Claude Code runs the task prompt headless in each (same CLI flags, same allowed tools). Afterwards:
  - tokens and cost come from Claude's own final `result` event (`total_cost_usd`, `usage`);
  - changed lines = added + deleted lines in project files (`git diff --numstat`, harness files and
    .agent-state excluded), so extra edits and over-engineering show up;
  - correct = hidden acceptance tests (bench/hidden/, never visible to the agent) pass;
  - tests / checked = the agent itself ran the tests / any python check of its change.

  python3 bench/run_bench.py --reps 3            # 6 tasks x 2 arms x 3 = 36 Claude runs
  python3 bench/run_bench.py --tasks cart,listing --reps 3   # the two multi-file tasks only
  python3 bench/run_bench.py --tasks typo --reps 1 --model sonnet
  python3 bench/run_bench.py --tasks cart,listing --arms bare,harness,harness-nosandbox,harness-norule

Variant arms install the harness and then switch one thing off, to price it separately:
  harness-nosandbox  .claude/settings.json sandbox.enabled = false
  harness-norule     the regression-test rule removed from AGENTS.md (and its .agents copy)

Results: bench/results/<timestamp>.json and a printed summary (medians per task and arm).
This spends real Claude usage. It needs the `claude` CLI logged in.
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / 'bench'
ALLOWED = ['Read', 'Edit', 'Write', 'Glob', 'Grep', 'Bash(python3:*)', 'Bash(git diff:*)', 'Bash(git status:*)', 'Bash(ls:*)']
ARMS = ('bare', 'harness', 'harness-nosandbox', 'harness-norule')
REGRESSION_RULE = '- Bug fixes in a repository with tests: add or update a test that fails before the fix and passes after it.\n'
HARNESS_PATHS = (':!AGENTS.md', ':!CLAUDE.md', ':!START-HERE*', ':!PROJECT.md', ':!.agents', ':!.claude', ':!.codex',
                 ':!.github', ':!agent-core', ':!docs/agent', ':!templates', ':!.gitignore', ':!.agent-state')


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True).stdout


def make_repo(arm: str, project: str = 'project') -> Path:
    repo = Path(tempfile.mkdtemp(prefix=f'v4-bench-{arm}-')).resolve()
    shutil.copytree(BENCH / project, repo, dirs_exist_ok=True)
    git(repo, 'init', '-q')
    if arm.startswith('harness'):
        proc = subprocess.run([sys.executable, '-B', str(ROOT / 'install/apply.py'), '--target', str(repo), '--apply'],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit('harness install failed:\n' + proc.stdout + proc.stderr)
    if arm == 'harness-nosandbox':
        settings = repo / '.claude/settings.json'
        data = json.loads(settings.read_text())
        data['sandbox']['enabled'] = False
        settings.write_text(json.dumps(data, indent=2) + '\n')
    if arm == 'harness-norule':
        for rel in ('AGENTS.md', '.agents/AGENTS.md'):
            policy = repo / rel
            text = policy.read_text()
            if REGRESSION_RULE not in text:
                raise SystemExit(f'regression-test rule not found in {rel}')
            policy.write_text(text.replace(REGRESSION_RULE, ''))
    git(repo, 'add', '-A')
    git(repo, '-c', 'user.name=bench', '-c', 'user.email=bench@example.invalid', 'commit', '-qm', 'baseline')
    return repo


def run_claude(repo: Path, prompt: str, model: str, timeout: int) -> tuple[dict, list]:
    cmd = ['claude', '-p', prompt, '--output-format', 'stream-json', '--verbose',
           '--permission-mode', 'acceptEdits', '--allowedTools', *ALLOWED]
    if model:
        cmd += ['--model', model]
    try:
        out = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout).stdout
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or '')
    events = []
    for line in out.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    result = next((e for e in reversed(events) if e.get('type') == 'result'), {})
    init = next((e for e in events if e.get('type') == 'system' and e.get('model')), {})
    result = {**result, 'model': init.get('model', '')}
    return result, events


def tool_calls(events: list) -> list[str]:
    """Tool calls in order, e.g. 'Read shop/text.py' or 'Bash python3 -m unittest ...'."""
    calls = []
    for e in events:
        message = e.get('message')
        for block in (message.get('content') or [] if isinstance(message, dict) else []):
            if isinstance(block, dict) and block.get('type') == 'tool_use':
                args = block.get('input') or {}
                detail = args.get('command') or args.get('file_path') or args.get('pattern') or args.get('skill') or ''
                calls.append(f"{block.get('name')} {str(detail)[:120]}".strip())
    return calls


def measure(repo: Path, task: dict, result: dict, events: list) -> dict:
    git(repo, 'add', '-A', '-N')
    changed = 0
    files = []
    for line in git(repo, 'diff', '--numstat', 'HEAD', '--', '.', *HARNESS_PATHS).splitlines():
        added, deleted, name = line.split('\t', 2)
        changed += int(added) + int(deleted) if added != '-' else 0
        files.append(name)
    hidden = repo / 'tests_hidden'
    hidden.mkdir()
    shutil.copy2(BENCH / 'hidden' / task['hidden'], hidden / task['hidden'])
    (hidden / '__init__.py').write_text('')
    check = subprocess.run([sys.executable, '-m', 'unittest', f"tests_hidden.{task['hidden'][:-3]}"], cwd=repo,
                           capture_output=True, text=True, timeout=60)
    visible = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=repo,
                             capture_output=True, text=True, timeout=60)
    usage = result.get('usage') or {}
    calls = tool_calls(events)
    shell = [c[5:] for c in calls if c.startswith('Bash ')]
    return {
        # API errors and limits can also end with subtype=success, but flagged is_error or with no output.
        'ok': result.get('subtype') == 'success' and not result.get('is_error') and bool(usage.get('output_tokens')),
        'error': str(result.get('result', 'no result event'))[:200] if result.get('is_error') or not result else '',
        'model': result.get('model', ''),
        'cost_usd': result.get('total_cost_usd'),
        'input_tokens': usage.get('input_tokens', 0) + usage.get('cache_creation_input_tokens', 0) + usage.get('cache_read_input_tokens', 0),
        'output_tokens': usage.get('output_tokens', 0),
        'turns': result.get('num_turns'),
        'seconds': round((result.get('duration_ms') or 0) / 1000, 1),
        'changed_lines': changed,
        'files': files,
        'correct': check.returncode == 0 and visible.returncode == 0,
        'tests_run': any('unittest' in c or 'pytest' in c for c in shell),
        'checked': any('python' in c for c in shell),  # ran tests or any python check of the change
        'tool_calls': calls,
    }


def summarize(rows: list) -> list[str]:
    lines = ['task      arm               n  correct  tests   checked  changed  out_tok  in_tok(all)  cost$   turns  sec   (medians)']
    keys = sorted({(r['task'], r['arm']) for r in rows}, key=lambda k: (k[0], ARMS.index(k[1])))
    for task, arm in keys:
        rs = [r for r in rows if r['task'] == task and r['arm'] == arm and r['ok']]
        if not rs:
            lines.append(f'{task:9} {arm:17} 0  (no successful runs)')
            continue
        med = lambda k: statistics.median(r[k] or 0 for r in rs)  # noqa: E731
        lines.append(f"{task:9} {arm:17} {len(rs)}  {sum(r['correct'] for r in rs)}/{len(rs):<6} {sum(r['tests_run'] for r in rs)}/{len(rs):<5} {sum(r['checked'] for r in rs)}/{len(rs):<6} "
                     f"{med('changed_lines'):<8g} {med('output_tokens'):<8g} {med('input_tokens'):<12g} {med('cost_usd'):<7.3f} "
                     f"{med('turns'):<6g} {med('seconds'):g}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description='With/without-harness efficiency benchmark on Claude Code.')
    ap.add_argument('--tasks', default='', help='comma-separated task ids (default: all)')
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--arms', default='bare,harness', help=f"comma-separated arms from {', '.join(ARMS)}")
    ap.add_argument('--model', default='', help='claude --model value (default: the CLI default)')
    ap.add_argument('--timeout', type=int, default=420)
    args = ap.parse_args()
    arms = [a for a in args.arms.split(',') if a]
    if not arms or any(a not in ARMS for a in arms):
        ap.error(f"--arms takes a comma-separated subset of {', '.join(ARMS)}")
    sys.stdout.reconfigure(line_buffering=True)

    tasks = json.loads((BENCH / 'tasks.json').read_text())
    wanted = {t for t in args.tasks.split(',') if t}
    tasks = [t for t in tasks if not wanted or t['id'] in wanted]
    version = subprocess.run(['claude', '--version'], capture_output=True, text=True).stdout.strip()
    jobs = [(rep, task, arm) for rep in range(args.reps) for task in tasks
            for arm in (arms if rep % 2 == 0 else arms[::-1])]  # alternate order
    rows = []
    for rep, task, arm in jobs:
        repo = make_repo(arm, task.get('project', 'project'))
        result, events = run_claude(repo, task['prompt'], args.model, args.timeout)
        row = {'task': task['id'], 'arm': arm, 'rep': rep, **measure(repo, task, result, events)}
        rows.append(row)
        shutil.rmtree(repo, ignore_errors=True)
        print(f"{task['id']:9} {arm:17} rep{rep} ok={row['ok']} correct={row['correct']} tests={row['tests_run']} checked={row['checked']} "
              f"changed={row['changed_lines']} out={row['output_tokens']} in={row['input_tokens']} "
              f"cost={row['cost_usd']} turns={row['turns']} {row['seconds']}s | {row['error'] or ' ; '.join(row['tool_calls'])[:300]}")
        if len(rows) >= 3 and not any(r['ok'] for r in rows[-3:]):
            print('Stopping: three failed runs in a row (service error or usage limit). Rerun later.')
            break
    out = BENCH / 'results' / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'claude_version': version, 'model': args.model or 'default', 'reps': args.reps, 'arms': arms,
                               'rows': rows}, indent=2) + '\n')
    print('\n'.join(summarize(rows)))
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
