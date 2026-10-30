#!/usr/bin/env python3
"""Run the skill-routing evals in agent-core/evals/skill-routing.json against a real agent CLI.

Each case runs in a disposable copy of this harness. The agent is told the task is
hypothetical and must not edit files or run commands; it loads the workflow skills it
would use over the whole task (start through pre-completion verification) and reports them.

Scoring uses the skills the agent *declares* in its final SKILLS line (--basis declared, the
default), because some agents open several SKILL.md files just to compare them. Skills actually
opened are recorded as `loaded` for reference; --basis union scores on both. A case passes when
every `expect` skill is used and no `forbid` skill is. This measures routing, not task execution.

Results go to .agent-state/evals/<timestamp>-<provider>.json. Each case is one model
call, so a full run spends real usage on the chosen provider.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_files import make_fixture  # noqa: E402

SKILLS = ['project-context', 'dev-plan', 'dev-debug', 'dev-ui-verify', 'dev-verify', 'dev-review']
TEMPLATE = """Skill-routing evaluation in a disposable repository. The task below is hypothetical.
Do NOT edit files and do NOT run shell commands. Under this repository's operating policy, decide which
workflow skills you would use over the whole task -- from starting it through verifying it before you
would claim it is complete -- and open/load exactly those skills (possibly none), then stop.
Finish with one final line: "SKILLS: <comma-separated skill names, or none>".

Task: {prompt}"""


def command(provider: str, prompt: str, fixture: Path, args) -> list[str]:
    if provider == 'claude':
        return ['claude', '-p', prompt, '--output-format', 'stream-json', '--verbose', '--permission-mode', 'plan']
    if provider == 'antigravity':
        return ['agy', '-p', prompt, '--mode', 'plan', '--print-timeout', f'{args.timeout}s']
    if provider == 'codex':
        cmd = ['codex', 'exec', '--ephemeral', '--json', '-s', 'read-only', '-C', str(fixture),
               '-c', f'projects."{fixture}".trust_level="trusted"']
        if args.codex_model:
            cmd += ['-m', args.codex_model]
        return cmd + [prompt]
    raise ValueError(provider)


def antigravity_tool_calls(since: float, fixture: Path) -> str:
    """Tool calls (only) from Antigravity transcripts written for this fixture.

    The transcript also embeds the skill catalog, so scanning it whole would count every
    skill as loaded; only the agent's own tool calls are evidence of loading a skill.
    """
    base = Path.home() / '.gemini/antigravity-cli/brain'
    calls = []
    for path in base.glob('*/.system_generated/logs/transcript_full.jsonl'):
        try:
            if path.stat().st_mtime < since:
                continue
            lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        except OSError:
            continue
        if not any(fixture.name in line for line in lines):  # unique v4-fixture-* directory name
            continue
        for line in lines:
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue
            if step.get('tool_calls'):
                calls.append(json.dumps(step['tool_calls']))
    return '\n'.join(calls)


def used_skills(text: str) -> tuple[set[str], set[str]]:
    """(loaded, declared): loaded from tool calls/paths, declared from the final SKILLS line."""
    loaded = set(re.findall(r'skills/(%s)/SKILL\.md' % '|'.join(map(re.escape, SKILLS)), text))
    for match in re.finditer(r'"name"\s*:\s*"Skill"\s*,\s*"input"\s*:\s*\{[^}]*"(?:skill|command|name)"\s*:\s*"([a-z-]+)"', text):
        if match.group(1) in SKILLS:
            loaded.add(match.group(1))
    declared: set[str] = set()
    lines = answer_lines(text)
    if lines:
        declared = {s for s in SKILLS if re.search(r'(?<![a-z-])%s(?![a-z-])' % re.escape(s), lines[-1])}
    return loaded, declared


def answer_lines(text: str) -> list[str]:
    """The agent's own SKILLS lines; an echo of the instruction template is not an answer."""
    return [line for line in re.findall(r'SKILLS:\s*([^\n"\\]*)', text) if not line.lstrip().startswith('<')]


def score(case: dict, used: set[str]) -> tuple[bool, list[str]]:
    problems = [f'missing {s}' for s in case.get('expect', []) if s not in used]
    problems += [f'forbidden {s}' for s in case.get('forbid', []) if s in used]
    return not problems, problems


def main() -> int:
    ap = argparse.ArgumentParser(description='Run V4 skill-routing evals against a real agent CLI.')
    ap.add_argument('--provider', choices=['claude', 'antigravity', 'codex'], required=True)
    ap.add_argument('--cases', default='', help='comma-separated case ids (default: all)')
    ap.add_argument('--timeout', type=int, default=0, help='seconds per run (default: 720 on antigravity, 240 otherwise)')
    ap.add_argument('--codex-model', default='')
    ap.add_argument('--basis', choices=['declared', 'union'], default='declared')
    ap.add_argument('--repeat', type=int, default=1, help='run every case N times; a case passes only if all N pass')
    args = ap.parse_args()
    if args.repeat < 1:
        ap.error('--repeat must be at least 1')
    # Antigravity took 300-575 s per case on 1.4.11; 420 s still cut one run off before its answer line.
    args.timeout = args.timeout or (720 if args.provider == 'antigravity' else 240)
    sys.stdout.reconfigure(line_buffering=True)  # show progress when redirected to a log

    cases = json.loads((ROOT / 'agent-core/evals/skill-routing.json').read_text(encoding='utf-8'))
    wanted = {c for c in args.cases.split(',') if c}
    cases = [c for c in cases if not wanted or c['id'] in wanted]
    results = []
    for case in cases:
        runs = []
        for attempt in range(args.repeat):
            run = run_case(case, args)
            runs.append(run)
            label = 'PASS' if run['pass'] else ('FAIL' if run['answered'] else 'NOANS')
            tag = f"{case['id']}" + (f' #{attempt + 1}' if args.repeat > 1 else '')
            print(f"{label:5} {tag:22} loaded={','.join(run['loaded']) or '-'} declared={','.join(run['declared']) or '-'}"
                  + (f"  ({'; '.join(run['problems'])})" if run['problems'] else ''))
        results.append(combine(case, runs))
    summary = summarize(results)
    print(f"{args.provider}: {summary['passed']}/{summary['total']} routing cases passed (basis: {args.basis}"
          + (f', every one of {args.repeat} runs' if args.repeat > 1 else '') + ')'
          + (f"; unstable: {', '.join(summary['unstable'])}" if summary['unstable'] else '')
          + (f"; {summary['unanswered']} gave no answer -- rerun them with --cases and a longer --timeout" if summary['unanswered'] else ''))
    out = ROOT / '.agent-state/evals' / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.provider}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'provider': args.provider, 'basis': args.basis, 'repeat': args.repeat, **summary, 'results': results},
                              indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(out)
    return 0 if summary['passed'] == summary['total'] else 1


def run_case(case: dict, args) -> dict:
    fixture = make_fixture(ROOT)
    started = time.time()
    try:
        proc = subprocess.run(command(args.provider, TEMPLATE.format(prompt=case['prompt']), fixture, args), cwd=fixture,
                              text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=args.timeout + 60)
        text, code = (proc.stdout or '') + '\n' + (proc.stderr or ''), proc.returncode
    except subprocess.TimeoutExpired:
        text, code = 'TIMEOUT', 124
    output = text
    if args.provider == 'antigravity':
        text += '\n' + antigravity_tool_calls(started - 1, fixture)
    loaded, declared = used_skills(text)
    answered = bool(answer_lines(output if args.provider == 'antigravity' else text))
    used = (loaded | declared) if args.basis == 'union' or not answered else declared
    ok, problems = score(case, used)
    if not answered and args.basis == 'declared':
        # No final SKILLS line (timeout or the agent stopped early): not a routing decision either way.
        ok, problems = False, ['no answer: the agent ended without a SKILLS line' + (' (timed out)' if code == 124 else '')]
    if code not in (0, 124) and not (loaded or declared or answered):
        ok, problems = False, [f'provider error (exit {code}): ' + ' '.join(text.strip().splitlines()[-2:])[:200]]
    shutil.rmtree(fixture, ignore_errors=True)
    return {'pass': ok, 'answered': answered, 'problems': problems, 'loaded': sorted(loaded), 'declared': sorted(declared),
            'seconds': round(time.time() - started), 'output_tail': '' if ok else output.strip()[-800:]}


def combine(case: dict, runs: list[dict]) -> dict:
    """One case over repeated runs: it passes only if every run passed (one pass can hide variance)."""
    first_bad = next((r for r in runs if not r['pass']), runs[0])
    return {'id': case['id'], 'pass': all(r['pass'] for r in runs), 'answered': all(r['answered'] for r in runs),
            'passes': sum(r['pass'] for r in runs), 'runs': len(runs), 'problems': first_bad['problems'],
            'loaded': first_bad['loaded'], 'declared': first_bad['declared'], 'expect': case.get('expect', []),
            'forbid': case.get('forbid', []), 'seconds': sum(r['seconds'] for r in runs), 'output_tail': first_bad['output_tail'],
            'attempts': [{k: r[k] for k in ('pass', 'answered', 'problems', 'declared', 'seconds')} for r in runs]}


def summarize(results: list[dict]) -> dict:
    return {'passed': sum(r['pass'] for r in results), 'total': len(results),
            'unanswered': sum(not r['answered'] for r in results),
            'unstable': [f"{r['id']} {r['passes']}/{r['runs']}" for r in results if 0 < r['passes'] < r['runs']]}


if __name__ == '__main__':
    raise SystemExit(main())
