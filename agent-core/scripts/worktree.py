#!/usr/bin/env python3
"""Safe git worktree helper for concurrent agent writers."""
from __future__ import annotations
import argparse,re,subprocess,time
from pathlib import Path

def out(cmd,cwd=None): return subprocess.check_output(cmd,cwd=cwd,text=True,stderr=subprocess.DEVNULL).strip()
def call(cmd,cwd=None): subprocess.check_call(cmd,cwd=cwd)
def root(): return Path(out(['git','rev-parse','--show-toplevel']))
def slug(s):
    s=re.sub(r'[^a-zA-Z0-9]+','-',s).strip('-').lower()
    if not s: raise SystemExit('Empty task slug.')
    return s[:48]
def base(r):
    cand=[]
    try: cand.append(out(['git','symbolic-ref','-q','--short','refs/remotes/origin/HEAD'],r))
    except Exception: pass
    cand += ['origin/main','origin/master','main','master','HEAD']
    for c in cand:
        if not c: continue
        try: out(['git','rev-parse','--verify',c],r); return c
        except Exception: pass
    raise SystemExit('Could not resolve base ref.')
def managed(r): return r.parent/'.agent-worktrees'/r.name

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    c=sp.add_parser('create'); c.add_argument('task'); rm=sp.add_parser('remove'); rm.add_argument('path'); sp.add_parser('list'); a=ap.parse_args(); r=root()
    if a.cmd=='list': call(['git','worktree','list'],r); return
    if a.cmd=='create':
        s=slug(a.task); stamp=time.strftime('%Y%m%d-%H%M%S'); branch=f'agent/{s}-{stamp}'; p=managed(r)/f'{s}-{stamp}'; p.parent.mkdir(parents=True,exist_ok=True); b=base(r)
        call(['git','worktree','add','-b',branch,str(p),b],r)
        print(f'WORKTREE={p}\nBRANCH={branch}\nBASE={b}\nIsolate shared ports/databases/containers/browser profiles separately when needed.'); return
    p=Path(a.path).expanduser().resolve(); mr=managed(r).resolve()
    if mr not in p.parents: raise SystemExit(f'Refusing to remove unmanaged worktree: {p}')
    if out(['git','status','--porcelain'],p): raise SystemExit('Refusing to remove dirty worktree.')
    call(['git','worktree','remove',str(p)],r); print(f'Removed {p}')
if __name__=='__main__': main()
