#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside the harness tree
from policy import classify_generic  # noqa: E402
from hook_log import record  # noqa: E402
from scope import should_defer  # noqa: E402


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if should_defer(event.get('cwd')):
        return 0  # global copy: the project's own, equal-or-newer V4 hook decides
    tool, tool_input = str(event.get('tool_name', '')), event.get('tool_input') or {}
    verdict = classify_generic(tool, tool_input)
    if verdict.action == 'allow':
        return 0
    record('codex', tool, tool_input, 'deny', verdict)
    reason = verdict.reason
    if verdict.kind == 'external':
        reason += (' Codex PreToolUse hooks cannot prompt ("ask" is not supported), so V4 blocks it here.'
                   ' Ask the user to approve and run it themselves.')
    elif verdict.action == 'ask':
        reason += ' Codex PreToolUse hooks cannot prompt ("ask" is not supported), so V4 denies by default.'
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason,
    }}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
