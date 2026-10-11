#!/usr/bin/env python3
"""Build and verify a clean, reproducible Agent Dev Environment V4 ZIP."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

PACKAGE_NAME='unified-master-harness'
FORBIDDEN_PARTS={'__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','node_modules','.DS_Store','.git',
                 '.agent-state','.agent-worktrees','.agent-migration-backup'}
FORBIDDEN_FILES={'agent-core/project/profile.json','agent-core/project/profile.md'}
REQUIRED_PACKAGE_FILES={
    'AGENTS.md','CLAUDE.md','.agents/AGENTS.md','README.md','LICENSE','START-HERE.md','install/apply.py','install/INSTALLATION-PROMPT.md',
    'agent-core/VERSION','agent-core/scripts/check_agent_config.py','agent-core/scripts/bootstrap_project.py',
    'agent-core/scripts/build_release.py','agent-core/hooks/policy.py',
}


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def release_files(root: Path) -> list[Path]:
    files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(root)
        if FORBIDDEN_PARTS.intersection(rel.parts): continue
        if rel.as_posix()=='MANIFEST.json': continue
        files.append(p)
    return files


def validate_tree(root: Path) -> list[str]:
    errors=[]
    rels={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    for req in sorted(REQUIRED_PACKAGE_FILES):
        if req not in rels: errors.append(f'missing required package file: {req}')
    for rel in sorted(rels):
        if rel in FORBIDDEN_FILES: errors.append(f'project-specific generated profile must not ship: {rel}')
    if (root/'.agents/workflows').exists(): errors.append('V4 package intentionally does not ship Antigravity workflows; use skills for portable task procedures')
    if (root/'.agents/rules/core-policy.md').exists(): errors.append('duplicated Antigravity core policy must not ship')
    if (root/'agent-core/hooks/guard_policy.py').exists(): errors.append('obsolete duplicate guard_policy.py must not ship')
    return errors


def manifest(root: Path) -> dict:
    return {
        'package':PACKAGE_NAME,
        'version':(root/'agent-core/VERSION').read_text().strip(),
        'files':{p.relative_to(root).as_posix():sha256(p) for p in release_files(root)},
    }


def write_manifest(root: Path) -> dict:
    data=manifest(root)
    (root/'MANIFEST.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return data


def verify_manifest(root: Path) -> list[str]:
    errors=validate_tree(root)
    mf=root/'MANIFEST.json'
    if not mf.exists(): return errors+['MANIFEST.json missing']
    try: expected=json.loads(mf.read_text(encoding='utf-8'))
    except Exception as exc: return errors+[f'invalid manifest: {exc}']
    actual=manifest(root)
    if expected.get('package')!=actual['package']: errors.append('manifest package mismatch')
    if expected.get('version')!=actual['version']: errors.append('manifest version mismatch')
    exp=expected.get('files',{})
    if exp!=actual['files']:
        missing=sorted(set(exp)-set(actual['files']))
        extra=sorted(set(actual['files'])-set(exp))
        changed=sorted(k for k in set(exp)&set(actual['files']) if exp[k]!=actual['files'][k])
        if missing: errors.append('manifest missing-on-disk: '+', '.join(missing[:10]))
        if extra: errors.append('manifest untracked files: '+', '.join(extra[:10]))
        if changed: errors.append('manifest hash mismatch: '+', '.join(changed[:10]))
    return errors


def build(root: Path, output: Path) -> None:
    errors=validate_tree(root)
    if errors: raise SystemExit('RELEASE TREE INVALID\n- '+'\n- '.join(errors))
    write_manifest(root)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): output.unlink()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(root.rglob('*')):
            if not p.is_file(): continue
            rel=p.relative_to(root)
            if FORBIDDEN_PARTS.intersection(rel.parts): continue
            z.write(p,Path(PACKAGE_NAME)/rel)
    print(output)


def verify_zip(path: Path) -> list[str]:
    if not path.exists(): return [f'zip missing: {path}']
    with tempfile.TemporaryDirectory() as td:
        dest=Path(td)
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            if any(Path(n).is_absolute() or '..' in Path(n).parts for n in names): return ['zip contains unsafe path']
            z.extractall(dest)
        root=dest/PACKAGE_NAME
        if not root.is_dir(): return [f'zip root {PACKAGE_NAME}/ missing']
        return verify_manifest(root)


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument('--output')
    ap.add_argument('--verify-zip')
    ap.add_argument('--verify-tree',action='store_true')
    args=ap.parse_args(); root=Path(args.root).resolve()
    if args.verify_tree:
        errors=verify_manifest(root)
        if errors:
            print('TREE VERIFY FAILED'); [print('- '+e) for e in errors]; return 1
        print('TREE VERIFY PASSED'); return 0
    if args.verify_zip:
        errors=verify_zip(Path(args.verify_zip).resolve())
        if errors:
            print('ZIP VERIFY FAILED'); [print('- '+e) for e in errors]; return 1
        print('ZIP VERIFY PASSED'); return 0
    if not args.output: ap.error('--output is required unless verifying')
    build(root,Path(args.output).resolve()); return 0


if __name__=='__main__': raise SystemExit(main())
