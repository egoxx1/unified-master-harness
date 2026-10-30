#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside the harness tree


def deny(reason: str) -> None:
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason,
    }}))


def main() -> int:
    # Codex runs the tool anyway when a PreToolUse hook errors, times out or exits with a
    # code other than 0 or 2, so every failure below must still print a deny.
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError('event is not an object')
    except Exception:
        deny('V4 safety hook could not parse the tool call, so it is blocked.')
        return 0
    try:
        from pathlib import Path
        from policy import Verdict, classify_generic, interactive_session
        from hook_log import record
        from scope import project_hooks_dir, should_defer
    except Exception as exc:
        deny(f'V4 safety hook could not load its policy ({type(exc).__name__}), so the tool call is blocked.')
        return 0
    try:
        if should_defer(event.get('cwd')):
            return 0  # global copy: the project's own, equal-or-newer V4 hook decides
        tool, tool_input = str(event.get('tool_name', '')), event.get('tool_input') or {}
        cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
        hooks_dir = project_hooks_dir(cwd) or Path(__file__).resolve().parent
        verdict = classify_generic(tool, tool_input, cwd, str(hooks_dir.parents[1]))
        if verdict.action == 'allow' and tool in {'Bash', 'exec_command', 'shell', 'local_shell'} and isinstance(tool_input, dict):
            command = tool_input.get('command') or tool_input.get('cmd') or ''
            session = interactive_session(command if isinstance(command, str) else ' '.join(map(str, command)))
            if session:
                verdict = Verdict('deny', f'Starting {session} without a command opens a session whose later input '
                                  '(write_stdin) never reaches this hook.', 'interactive')
    except Exception as exc:
        deny(f'V4 safety hook failed while checking the tool call ({type(exc).__name__}), so it is blocked.')
        return 0
    if verdict.action == 'allow':
        return 0
    record('codex', tool, tool_input if isinstance(tool_input, dict) else {'command': str(tool_input)}, 'deny', verdict)
    reason = verdict.reason
    if verdict.kind == 'external':
        reason += (' Codex PreToolUse hooks cannot prompt ("ask" is not supported), so V4 blocks it here.'
                   ' Ask the user to approve and run it themselves.')
    elif verdict.kind == 'harness':
        reason += (' Codex PreToolUse hooks cannot prompt ("ask" is not supported), so V4 blocks it here.'
                   ' Ask the user to make or approve this change themselves.')
    elif verdict.kind == 'interactive':
        reason += ' Pass the command itself instead (for example bash -lc "...", python3 -c "..." or a heredoc).'
    elif verdict.action == 'ask':
        reason += ' Codex PreToolUse hooks cannot prompt ("ask" is not supported), so V4 denies by default.'
    deny(reason)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
