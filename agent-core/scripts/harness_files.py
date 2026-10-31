#!/usr/bin/env python3
"""Shared definition of which files the V4 harness owns, plus disposable test fixtures."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

# Paths the harness owns and may update. Everything else (product code, PROJECT.md,
# the generated project profile, accepted growth history) belongs to the project.
OWNED_PATHS = [
    'AGENTS.md', 'CLAUDE.md', 'START-HERE.md', 'START-HERE.ko.md',
    '.agents/AGENTS.md', '.agents/hooks.json', '.agents/skills',
    '.claude/settings.json', '.claude/skills', '.claude/agents', '.claude/commands',
    '.codex',
    '.github/workflows/agent-harness.yml',
    'agent-core', 'docs/agent', 'templates',
]
PROJECT_OWNED = {
    'agent-core/project/profile.json', 'agent-core/project/profile.md',
    'agent-core/growth/history.jsonl', 'agent-core/HARNESS-MANIFEST.json',
}
CACHE_PARTS = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.DS_Store'}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def owned_files(root: Path) -> list[str]:
    """Relative POSIX paths of harness-owned files that exist under root."""
    found: set[str] = set()
    for rel in OWNED_PATHS:
        base = root / rel
        if base.is_file():
            found.add(rel)
        elif base.is_dir():
            for p in base.rglob('*'):
                if p.is_file() and not CACHE_PARTS.intersection(p.parts) and not p.name.endswith('.v4-new'):
                    found.add(p.relative_to(root).as_posix())
    return sorted(f for f in found if f not in PROJECT_OWNED)


def make_fixture(source: Path, extra_files: dict[str, str] | None = None) -> Path:
    """Copy the harness into a fresh temporary git repository (no commits, no remote)."""
    dest = Path(tempfile.mkdtemp(prefix='v4-fixture-')).resolve()
    for rel in owned_files(source) + ['PROJECT.md']:
        src = source / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
    for rel, text in (extra_files or {}).items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_text(text, encoding='utf-8')
    subprocess.run(['git', 'init', '-q'], cwd=dest, check=True)
    return dest
