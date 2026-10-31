#!/usr/bin/env python3
"""Install the V4 harness into a repository.

  python3 install/apply.py --target /path/to/repo            # dry run: show what would change
  python3 install/apply.py --target /path/to/repo --apply    # install

Only harness-owned files are written (see agent-core/scripts/harness_files.py); product files
such as README.md are never touched. If the target already has its own agent configuration
(AGENTS.md, CLAUDE.md, .claude/settings.json, .codex/hooks.json, ...) that differs from V4, nothing
is written and the exit code is 2: that needs a semantic merge, not an overwrite. Follow
install/INSTALLATION-PROMPT.md (an agent can do it). A repository that already has V4 is
upgraded with agent-core/scripts/upgrade_harness.py instead.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent-core/scripts'))
import upgrade_harness as up  # noqa: E402

GITIGNORE = ['.agent-state/', '.agent-worktrees/', '.agent-migration-backup/', '__pycache__/', '*.pyc', '.DS_Store']


def main() -> int:
    ap = argparse.ArgumentParser(description='Install the V4 agent harness into a repository.')
    ap.add_argument('--target', default='.', help='repository to install into (default: current directory)')
    ap.add_argument('--apply', action='store_true', help='write files (default: dry run)')
    ap.add_argument('--create-project-template', action='store_true', help='create PROJECT.md from templates/PROJECT.md if missing')
    args = ap.parse_args()
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f'Target is not a directory: {target}')
        return 1
    if target == ROOT:
        print('Target is the harness repository itself; choose another directory.')
        return 1
    if up.read_manifest(target):
        print('V4 is already installed here. Upgrade instead:\n'
              f'  python3 agent-core/scripts/upgrade_harness.py --from {ROOT}')
        return 2

    actions = up.plan(ROOT, target, set())
    conflicts = [rel for action, rel in actions if action == 'CONFLICT']
    if conflicts:
        print('MIGRATION REQUIRED: the target already has agent configuration that differs from V4.')
        for rel in conflicts:
            print(f'  {rel}')
        print('Nothing was written. Merge by following install/INSTALLATION-PROMPT.md, then rerun.')
        return 2

    added = [rel for action, rel in actions if action == 'ADD']
    print(f"V4 install into {target} ({'APPLY' if args.apply else 'dry run'}): {len(added)} files to add")
    if not args.apply:
        print('Rerun with --apply to install.')
        return 0

    up.apply(ROOT, target, actions)
    ignore = target / '.gitignore'
    existing = ignore.read_text(encoding='utf-8').splitlines() if ignore.exists() else []
    missing = [line for line in GITIGNORE if line not in existing]
    if missing:
        prefix = '' if not existing or existing[-1] == '' else '\n'
        with ignore.open('a', encoding='utf-8') as f:
            f.write(prefix + '# V4 agent harness\n' + '\n'.join(missing) + '\n')
    if args.create_project_template and not (target / 'PROJECT.md').exists():
        shutil.copy2(ROOT / 'templates/PROJECT.md', target / 'PROJECT.md')
    check = subprocess.run([sys.executable, '-B', 'agent-core/scripts/check_agent_config.py'], cwd=target,
                           capture_output=True, text=True)
    print('Installed. Config check: ' + ('PASSED' if check.returncode == 0 else 'FAILED\n' + check.stdout + check.stderr))
    print('Next, in the target repository:\n'
          '  python3 agent-core/scripts/bootstrap_project.py --write   # record repo facts (commands, ports)\n'
          '  python3 agent-core/scripts/install_git_hooks.py           # pre-commit secret block + harness check\n'
          '  python3 agent-core/scripts/doctor.py                      # find user settings that weaken the harness\n'
          'Then read START-HERE.md.')
    return 0 if check.returncode == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
