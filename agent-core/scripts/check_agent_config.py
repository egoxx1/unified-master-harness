#!/usr/bin/env python3
"""Validate an installed or source-tree Agent Dev Environment V4 harness."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path

MANAGED = ['project-context','dev-plan','dev-debug','dev-verify','dev-ui-verify','dev-review']
REQUIRED = [
    'AGENTS.md','CLAUDE.md',
    '.agents/AGENTS.md','.agents/hooks.json','.codex/hooks.json','.claude/settings.json',
    'agent-core/hooks/policy.py','agent-core/hooks/codex_pretool.py',
    'agent-core/hooks/claude_pretool.py','agent-core/hooks/antigravity_pretool.py',
    'agent-core/scripts/bootstrap_project.py','agent-core/scripts/sync_agent_config.py',
    'agent-core/scripts/growth_engine.py','agent-core/scripts/worktree.py',
    'agent-core/growth/policy.json','agent-core/evals/skill-routing.json',
    'agent-core/hooks/hook_log.py','agent-core/scripts/harness_files.py','agent-core/scripts/doctor.py',
    'agent-core/scripts/provider_smoke.py','agent-core/scripts/codex_hook_probe.py','agent-core/scripts/run_evals.py','agent-core/scripts/upgrade_harness.py',
    'agent-core/scripts/precommit_check.py','agent-core/scripts/install_git_hooks.py','.codex/config.toml',
    'agent-core/hooks/claude_session.py','agent-core/hooks/scope.py','.claude/agents/dev-reviewer.md',
    '.claude/commands/harness-check.md','.claude/commands/retro.md','.claude/commands/smoke.md',
]
# Local caches are gitignored and excluded by build_release.py, so running tests/hooks must not fail this check.
CACHE_PARTS = {'__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.DS_Store'}
FORBIDDEN_PARTS = {'node_modules'}
TEXT_SUFFIXES = {'.md','.json','.py','.txt','.yml','.yaml','.toml'}


def root() -> Path:
    try:
        return Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True,stderr=subprocess.DEVNULL).strip())
    except Exception:
        return Path.cwd()


def digest(path: Path) -> str:
    h=hashlib.sha256()
    for f in sorted(x for x in path.rglob('*') if x.is_file() and not (FORBIDDEN_PARTS|CACHE_PARTS).intersection(x.parts)):
        h.update(str(f.relative_to(path)).encode()); h.update(b'\0'); h.update(f.read_bytes()); h.update(b'\0')
    return h.hexdigest()


def frontmatter(text: str) -> dict[str,str]:
    if not text.startswith('---\n'): return {}
    end=text.find('\n---\n',4)
    if end < 0: return {}
    out={}
    for line in text[4:end].splitlines():
        if ':' in line:
            k,v=line.split(':',1); out[k.strip()]=v.strip()
    return out


def has_home_path_contamination(text: str) -> bool:
    # Catch concrete personal home paths, not generic documentation words.
    patterns = [
        r'/(?:Users)/[A-Za-z0-9._-]+/',
        r'/(?:home)/[A-Za-z0-9._-]+/',
        r'[A-Za-z]:\\(?:Users)\\[A-Za-z0-9._-]+\\',
    ]
    return any(re.search(p,text,re.IGNORECASE) for p in patterns)


def main() -> int:
    r=root(); errors=[]
    for rel in REQUIRED:
        if not (r/rel).exists(): errors.append(f'Missing required file: {rel}')
    if not (r/'AGENTS.md').exists():
        print('CONFIG CHECK FAILED\n- Missing AGENTS.md'); return 1

    policy=(r/'AGENTS.md').read_text(encoding='utf-8')
    nonblank=[line for line in policy.splitlines() if line.strip()]
    if len(nonblank)>150: errors.append(f'AGENTS.md has {len(nonblank)} nonblank lines; target <= 150.')

    descriptions={}
    for name in MANAGED:
        canonical=r/'.agents/skills'/name; mirror=r/'.claude/skills'/name
        skill=canonical/'SKILL.md'
        if not skill.exists(): errors.append(f'Missing canonical skill {name}'); continue
        fm=frontmatter(skill.read_text(encoding='utf-8'))
        if fm.get('name') != name: errors.append(f'{name}: frontmatter name mismatch')
        desc=fm.get('description',''); descriptions[name]=desc
        if not desc: errors.append(f'{name}: missing description')
        if len(desc)>380: errors.append(f'{name}: description too long ({len(desc)})')
        if not mirror.exists(): errors.append(f'{name}: Claude mirror missing')
        elif digest(canonical) != digest(mirror): errors.append(f'{name}: Claude mirror drift')

    names=list(descriptions)
    for i,a in enumerate(names):
        for b in names[i+1:]:
            ratio=SequenceMatcher(None,descriptions[a].lower(),descriptions[b].lower()).ratio()
            if ratio>.82: errors.append(f'Descriptions too similar: {a} vs {b} ({ratio:.2f})')

    if (r/'.agents/AGENTS.md').exists() and (r/'.agents/AGENTS.md').read_bytes() != (r/'AGENTS.md').read_bytes():
        errors.append('Antigravity AGENTS mirror drift; run sync_agent_config.py.')
    if (r/'CLAUDE.md').exists() and '@AGENTS.md' not in (r/'CLAUDE.md').read_text(encoding='utf-8',errors='ignore'):
        errors.append('Claude adapter must import canonical @AGENTS.md.')

    try:
        cases=json.loads((r/'agent-core/evals/skill-routing.json').read_text(encoding='utf-8'))
        known=set(MANAGED)
        for case in cases:
            for key in ('expect','forbid'):
                for skill_name in case.get(key,[]):
                    if skill_name not in known: errors.append(f"Eval {case.get('id')} references unknown skill {skill_name}")
    except Exception as exc:
        cases=[]; errors.append(f'Routing eval invalid: {exc}')

    try:
        gp=json.loads((r/'agent-core/growth/policy.json').read_text(encoding='utf-8'))
        for sev in ('low','medium','high','critical'):
            if int(gp['qualification'][sev]['min_occurrences'])<1: errors.append(f'Growth threshold invalid: {sev}')
        for target in ('root-policy','safety-hook','provider-permission','external-authority'):
            if not gp['targets'][target].get('human_review_before_promotion'):
                errors.append(f'High-risk growth target lacks human gate: {target}')
    except Exception as exc: errors.append(f'Growth policy invalid: {exc}')

    # Source/package trees should be clean. Installed repositories may naturally
    # contain node_modules elsewhere, so only reject cache artifacts inside V4-owned paths.
    owned_roots=[r/'.agents',r/'.claude/skills',r/'agent-core']
    for base in owned_roots:
        if not base.exists(): continue
        for p in base.rglob('*'):
            if FORBIDDEN_PARTS.intersection(p.parts): errors.append(f'Forbidden harness artifact: {p.relative_to(r)}')

    # Scan V4-owned/config text for concrete personal-home contamination. Skip this checker
    # itself because it necessarily contains the detection patterns.
    skip={(r/'agent-core/scripts/check_agent_config.py').resolve()}
    scan_roots=[r/'AGENTS.md',r/'.agents',r/'.claude',r/'.codex',r/'agent-core',r/'docs/agent',r/'templates']
    for base in scan_roots:
        paths=[base] if base.is_file() else (list(base.rglob('*')) if base.exists() else [])
        for p in paths:
            if not p.is_file() or p.resolve() in skip or p.suffix.lower() not in TEXT_SUFFIXES: continue
            try: text=p.read_text(encoding='utf-8',errors='ignore')
            except Exception: continue
            if has_home_path_contamination(text): errors.append(f'Concrete user-home path contamination in {p.relative_to(r)}')

    if errors:
        print('CONFIG CHECK FAILED')
        for error in sorted(set(errors)): print('- '+error)
        return 1
    print('CONFIG CHECK PASSED')
    print(f'- AGENTS.md nonblank lines: {len(nonblank)}')
    print(f'- canonical skills: {len(MANAGED)}; Claude mirrors synchronized')
    print(f'- routing eval cases: {len(cases)}')
    print('- provider policy adapters/mirrors: Codex root, Claude import, Antigravity mirror')
    print('- provider safety hook adapters: Codex, Claude Code, Antigravity')
    print('- harness-owned tree: no forbidden artifact or personal-home contamination (local caches ignored)')
    return 0


if __name__=='__main__': raise SystemExit(main())
