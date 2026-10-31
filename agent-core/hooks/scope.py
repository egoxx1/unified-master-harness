#!/usr/bin/env python3
"""Decide whether a globally installed copy of the V4 hooks should defer to a project's own hooks.

A user may register these adapters at user level (for example ~/.claude/settings.json) so that
folders without a harness are still guarded. Inside a project that ships its own V4 hooks of the
same or a newer policy version, running both is redundant, so the global copy steps aside. A
project with an older policy keeps the (stricter, newer) global copy running as well.
"""
from __future__ import annotations

import re
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
_VERSION_RE = re.compile(r"^POLICY_VERSION\s*=\s*['\"](\d+(?:\.\d+)*)['\"]", re.M)


def _version(policy_file: Path) -> tuple[int, ...]:
    try:
        match = _VERSION_RE.search(policy_file.read_text(encoding='utf-8', errors='ignore'))
    except OSError:
        return ()
    return tuple(int(x) for x in match.group(1).split('.')) if match else ()


def project_hooks_dir(cwd: str | None) -> Path | None:
    """Nearest ancestor of cwd (inclusive) that contains V4 hook adapters."""
    if not cwd:
        return None
    try:
        start = Path(cwd).resolve()
    except OSError:
        return None
    for directory in (start, *start.parents):
        candidate = directory / 'agent-core' / 'hooks'
        if (candidate / 'policy.py').is_file() and (candidate / 'claude_pretool.py').is_file():
            return candidate.resolve()
    return None


def should_defer(cwd: str | None) -> bool:
    """True when these hooks are a global copy and the project's own hooks are at least as new."""
    project = project_hooks_dir(cwd)
    if project is None or project == HOOKS_DIR:
        return False
    own, theirs = _version(HOOKS_DIR / 'policy.py'), _version(project / 'policy.py')
    return bool(own) and bool(theirs) and theirs >= own
