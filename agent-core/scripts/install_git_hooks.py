#!/usr/bin/env python3
"""Install the V4 git pre-commit hook (secret files + harness config check).

Refuses to replace an existing non-V4 pre-commit hook unless --force, in which case the
old hook is kept as pre-commit.before-v4.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MARKER = '# V4 pre-commit hook'
HOOK = f"""#!/bin/sh
{MARKER}
root="$(git rev-parse --show-toplevel)" || exit 1
exec python3 -B "$root/agent-core/scripts/precommit_check.py"
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    try:
        git_dir = subprocess.run(['git', 'rev-parse', '--git-common-dir'], text=True, capture_output=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('Not inside a git repository; nothing installed.')
        return 1
    hook = Path(git_dir).resolve() / 'hooks/pre-commit'
    if hook.exists() and MARKER not in hook.read_text(errors='ignore'):
        if not args.force:
            print(f'{hook} already exists and is not the V4 hook. Re-run with --force to keep it as pre-commit.before-v4 and install V4.')
            return 1
        hook.rename(hook.with_name('pre-commit.before-v4'))
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK, encoding='utf-8')
    hook.chmod(0o755)
    print(f'Installed {hook}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
