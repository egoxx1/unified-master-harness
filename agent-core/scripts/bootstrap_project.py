#!/usr/bin/env python3
"""Generate compact project facts from explicit repository evidence only."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from pathlib import Path


def output(cmd, cwd):
    try: return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return ''


def resolve_root(explicit: str | None) -> Path:
    if explicit: return Path(explicit).expanduser().resolve()
    top=output(['git','rev-parse','--show-toplevel'],Path.cwd())
    return Path(top) if top else Path.cwd()


def jread(path: Path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return None


def make_targets(path: Path) -> list[str]:
    if not path.exists(): return []
    ans=[]
    for line in path.read_text(encoding='utf-8',errors='ignore').splitlines():
        if not line or line[0].isspace() or line.startswith(('#','.')): continue
        match=re.match(r'^([A-Za-z0-9_.-]+)\s*:(?![=])',line)
        if match: ans.append(match.group(1))
    return sorted(set(ans))


def detect(root: Path) -> dict:
    facts={
        'package_manager':None,'package_manager_evidence':None,'package_scripts':{},'explicit_ports':[],
        'python_project':{},'make_targets':[],'compose_files':[],'ci_workflows':[],'directories':[],
        'framework_dependencies':[],'runtime_files':[],'notes':[],
    }
    pkg=jread(root/'package.json')
    if isinstance(pkg,dict):
        pm=pkg.get('packageManager')
        if isinstance(pm,str) and pm:
            facts['package_manager']=pm; facts['package_manager_evidence']='package.json#packageManager'
        if isinstance(pkg.get('scripts'),dict):
            facts['package_scripts']={str(k):str(v) for k,v in sorted(pkg['scripts'].items())}
            for value in pkg['scripts'].values():
                for pattern in (r'--port(?:=|\s+)(\d{2,5})',r'\bPORT=(\d{2,5})\b'):
                    facts['explicit_ports'] += re.findall(pattern,str(value))
        deps={}
        for key in ('dependencies','devDependencies'):
            if isinstance(pkg.get(key),dict): deps.update(pkg[key])
        known=['next','react','vite','vue','svelte','express','fastify','playwright','vitest','jest','typescript']
        facts['framework_dependencies']=sorted(k for k in known if k in deps)
    if not facts['package_manager']:
        for name,lock in [('pnpm','pnpm-lock.yaml'),('yarn','yarn.lock'),('npm','package-lock.json'),('bun','bun.lockb'),('bun','bun.lock')]:
            if (root/lock).exists(): facts['package_manager']=name; facts['package_manager_evidence']=lock; break

    pyproject=root/'pyproject.toml'
    if pyproject.exists():
        facts['python_project']['pyproject']=True
        try:
            try:
                import tomllib  # Python 3.11+
                data=tomllib.loads(pyproject.read_text(encoding='utf-8'))
            except ModuleNotFoundError:  # Python 3.10: the doctor's small reader covers the keys used here
                import sys
                sys.path.insert(0,str(Path(__file__).resolve().parent))
                from doctor import load_toml
                data=load_toml(pyproject)
            project=data.get('project',{}) if isinstance(data,dict) else {}
            if isinstance(project,dict):
                for key in ('name','requires-python'):
                    if key in project: facts['python_project'][key]=project[key]
                if isinstance(project.get('scripts'),dict): facts['python_project']['scripts']=sorted(project['scripts'])
            tool=data.get('tool',{}) if isinstance(data,dict) else {}
            if isinstance(tool,dict): facts['python_project']['tools']=sorted(tool)
        except Exception:
            facts['python_project']['parsed']=False

    facts['make_targets']=make_targets(root/'Makefile')
    for name in ('compose.yml','compose.yaml','docker-compose.yml','docker-compose.yaml'):
        if (root/name).exists(): facts['compose_files'].append(name)
    for name in ('Dockerfile','Procfile','.tool-versions','.python-version','.node-version','mise.toml'):
        if (root/name).exists(): facts['runtime_files'].append(name)
    workflows=root/'.github/workflows'
    if workflows.exists(): facts['ci_workflows']=sorted(str(p.relative_to(root)) for p in workflows.glob('*') if p.is_file())
    for directory in ('src','app','apps','frontend','backend','server','api','tests','test','e2e','packages','workers','scripts','docs'):
        if (root/directory).is_dir(): facts['directories'].append(directory)
    facts['explicit_ports']=sorted(set(int(x) for x in facts['explicit_ports']))
    return facts


def markdown(facts: dict) -> str:
    def fmt(value): return '`unknown`' if value in (None,'',[],{}) else f'`{value}`'
    lines=[
        '# Project Profile','',
        '> Generated from explicit repository evidence. Unknown values are intentionally not guessed.','',
        f"- Package manager: {fmt(facts['package_manager'])}",
        f"- Evidence: {fmt(facts['package_manager_evidence'])}",
        f"- Explicit ports: {fmt(facts['explicit_ports'])}",
        f"- Framework/tool dependencies: {fmt(facts['framework_dependencies'])}",
        f"- Existing directories: {fmt(facts['directories'])}",
        f"- Compose files: {fmt(facts['compose_files'])}",
        f"- Runtime files: {fmt(facts['runtime_files'])}",
        f"- CI workflows: {fmt(facts['ci_workflows'])}",'','## Package scripts',
    ]
    lines += [f'- `{k}` → `{v}`' for k,v in facts['package_scripts'].items()] or ['- none detected']
    lines += ['','## Make targets'] + ([f'- `{x}`' for x in facts['make_targets']] or ['- none detected'])
    lines += ['','## Python metadata','```json',json.dumps(facts['python_project'],indent=2,ensure_ascii=False),'```','']
    return '\n'.join(lines)


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',help='Repository root (defaults to current git root)')
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(); root=resolve_root(args.root); facts=detect(root)
    dest=root/'agent-core/project'; js=json.dumps(facts,indent=2,sort_keys=True,ensure_ascii=False)+'\n'; md=markdown(facts)
    if args.check:
        path=dest/'profile.json'
        if not path.exists() or path.read_text(encoding='utf-8') != js:
            print('Project profile drift detected. Run bootstrap_project.py --write.'); return 1
        print('Project profile is current.'); return 0
    if args.write:
        dest.mkdir(parents=True,exist_ok=True)
        (dest/'profile.json').write_text(js,encoding='utf-8')
        (dest/'profile.md').write_text(md,encoding='utf-8')
        print(f'Wrote {dest / "profile.md"}'); return 0
    print(md); return 0


if __name__=='__main__': raise SystemExit(main())
