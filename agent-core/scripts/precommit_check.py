#!/usr/bin/env python3
"""Git pre-commit check: refuse staged secret files and broken harness configuration.

Installed by install_git_hooks.py. Bypassing it requires an explicit `git commit --no-verify`,
which agents must not use without the user's permission.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agent-core/hooks'))
from policy import sensitive_path  # noqa: E402

HARNESS_PREFIXES = ('AGENTS.md', 'CLAUDE.md', '.agents/', '.claude/', '.codex/', 'agent-core/')


def staged() -> list[str]:
    out = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'], cwd=ROOT,
                         text=True, capture_output=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    files = staged()
    secrets = [f for f in files if sensitive_path(f)]
    if secrets:
        print('V4 pre-commit: refusing to commit sensitive-looking files:', file=sys.stderr)
        for f in secrets:
            print(f'  {f}', file=sys.stderr)
        print('Unstage them (git restore --staged <file>) and add them to .gitignore.', file=sys.stderr)
        return 1
    if any(f.startswith(HARNESS_PREFIXES) for f in files):
        check = subprocess.run([sys.executable, '-B', str(ROOT / 'agent-core/scripts/check_agent_config.py')], cwd=ROOT,
                               text=True, capture_output=True)
        if check.returncode != 0:
            print('V4 pre-commit: harness configuration check failed:', file=sys.stderr)
            print(check.stdout + check.stderr, file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
