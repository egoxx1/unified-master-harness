#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ inside the harness tree
from policy import _relative_base, classify_generic, classify_unknown_tool  # noqa: E402
from hook_log import record  # noqa: E402
from scope import project_hooks_dir, should_defer  # noqa: E402

MAX_INPUT_BYTES = 128 * 1024
# Tools with their own rules. The hook matches every tool (".*"): Antigravity 1.4 renamed its file tools once and
# the hook missed them, so any other tool still gets its path-like arguments checked.
KNOWN_TOOLS = {'run_command', 'view_file', 'read_file', 'edit_file', 'write_file'}  # as in codex_pretool.py: deny what could not be checked within the 5 s timeout

# Antigravity's "allow" auto-approves the tool call, so only a small, fully
# matched set of read-only/dev-check commands may return it.
SAFE = (
    r'(?:npm|pnpm|yarn|bun)(?:\s+run)?\s+(?:test|lint|typecheck|build)',
    r'(?:python(?:3(?:\.\d+)?)?\s+-m\s+(?:pytest|unittest|mypy)|pytest|mypy|ruff\s+check|tsc)',
    r'git\s+(?:status|diff|log|show)',
    r'(?:pwd|ls|rg)',
)


def command_decision(command: str, verdict) -> str:
    if verdict.action == 'deny':
        return 'deny'
    if verdict.kind == 'external':
        # Measured on Antigravity CLI 1.3.2: with toolPermission "always-proceed" a
        # force_ask decision still runs the command. deny is the only decision that
        # holds in every permission mode, so external actions fail closed here.
        return 'deny'
    if verdict.action == 'ask':
        return 'deny'  # sensitive input: fail closed, the user can read it themselves
    if re.search(r'[$`;|&<>\n\r]', command):
        return 'ask'
    if any(re.fullmatch(pattern + r'(?:\s+[-\w./=@]+)*', command.strip(), re.I) for pattern in SAFE):
        return 'allow'
    return 'ask'


def main() -> int:
    try:
        event = json.load(sys.stdin)
        call = event['toolCall']
        tool = call['name']
        args = call['args']
        if not isinstance(tool, str) or not isinstance(args, dict):
            raise ValueError('invalid toolCall')
    except (KeyError, ValueError, TypeError):
        print(json.dumps({'decision': 'deny', 'reason': 'V4 safety hook could not parse tool input.'}))
        return 0
    if len(json.dumps(args)) > MAX_INPUT_BYTES and tool in ('run_command', 'edit_file', 'write_file'):
        print(json.dumps({'decision': 'deny', 'reason': f'Tool input over {MAX_INPUT_BYTES // 1024} KB is too large to check '
                          'within the hook timeout; write it in smaller parts.'}))
        return 0
    workspaces = event.get('workspacePaths') or []
    cwd = args.get('Cwd') or (workspaces[0] if workspaces and isinstance(workspaces[0], str) else None)
    if should_defer(cwd):
        return 0  # global copy: no output, the project's own equal-or-newer V4 hook decides
    hooks_dir = project_hooks_dir(cwd) or Path(__file__).resolve().parent
    root = str(hooks_dir.parents[1])
    if tool not in KNOWN_TOOLS:
        verdict = classify_unknown_tool(tool, args, _relative_base(cwd, root), root)
        if verdict.action == 'allow':
            return 0  # no output: never auto-approve a tool this policy knows nothing about
        record('antigravity', tool, args, 'deny', verdict)
        print(json.dumps({'decision': 'deny', 'reason': verdict.reason}))
        return 0
    verdict = classify_generic(tool, args, cwd, root)
    if tool == 'run_command':
        command = args.get('CommandLine', '')
        decision = command_decision(command if isinstance(command, str) else '', verdict)
    else:
        decision = 'deny' if verdict.action == 'ask' else verdict.action
    if decision == 'allow' and tool in ('edit_file', 'write_file'):
        return 0  # no output: Antigravity's own permission setting decides, "allow" would auto-approve the edit
    record('antigravity', tool, args, decision, verdict)
    reason = verdict.reason
    if verdict.kind == 'external' and decision == 'deny':
        reason += ' Antigravity may auto-approve ask/force_ask, so V4 blocks it; ask the user to run it themselves.'
    print(json.dumps({'decision': decision, 'reason': reason}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
