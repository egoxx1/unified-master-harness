#!/usr/bin/env python3
"""Synchronize generated provider mirrors from V4 canonical sources."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

MANAGED=['project-context','dev-plan','dev-debug','dev-verify','dev-ui-verify','dev-review']


def root() -> Path:
    try: return Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True,stderr=subprocess.DEVNULL).strip())
    except Exception: return Path.cwd()


def copy_tree(src: Path,dst: Path) -> None:
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','.mypy_cache','.ruff_cache'))


def main() -> int:
    r=root()
    ag=r/'.agents/AGENTS.md'; ag.parent.mkdir(parents=True,exist_ok=True)
    ag.write_bytes((r/'AGENTS.md').read_bytes())
    for name in MANAGED:
        src=r/'.agents/skills'/name; dst=r/'.claude/skills'/name
        if not src.exists(): raise SystemExit(f'Missing canonical skill: {src}')
        dst.parent.mkdir(parents=True,exist_ok=True); copy_tree(src,dst)
    print('Synchronized root AGENTS.md to .agents/AGENTS.md and canonical skills to .claude/skills/.')
    return 0


if __name__=='__main__': raise SystemExit(main())
