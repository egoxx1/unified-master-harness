#!/usr/bin/env python3
"""Controlled harness-growth ledger and snapshot utility (stdlib only)."""
from __future__ import annotations
import argparse, calendar, hashlib, json, os, re, shutil, subprocess, tarfile, tempfile, time
from collections import Counter, defaultdict
from pathlib import Path

CATEGORIES = ['routing','context','verification','debugging','safety','project-fact','tooling','concurrency','ui','other']
SEVERITIES = ['low','medium','high','critical']
HARNESS_PATHS = ['AGENTS.md','CLAUDE.md','START-HERE.md','.agents','.claude','.codex','.github/workflows/agent-harness.yml','agent-core','docs/agent','templates','install']

def repo_root():
    try:
        return Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True,stderr=subprocess.DEVNULL).strip())
    except Exception:
        return Path.cwd()

def state_root(r: Path) -> Path:
    override=os.getenv('AGENT_GROWTH_STATE')
    return Path(override) if override else r/'.agent-state/growth'

def history_path(r: Path) -> Path:
    override=os.getenv('AGENT_GROWTH_HISTORY')
    return Path(override) if override else r/'agent-core/growth/history.jsonl'

def policy(r):
    return json.loads((r/'agent-core/growth/policy.json').read_text(encoding='utf-8'))

def normalize(s):
    s=s.lower().strip()
    s=re.sub(r'[^a-z0-9가-힣]+','-',s).strip('-')
    return s[:80] or 'observation'

def append_jsonl(path: Path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f: f.write(json.dumps(obj,ensure_ascii=False)+'\n')

def load_jsonl(path: Path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        try: out.append(json.loads(line))
        except json.JSONDecodeError: pass
    return out

def record_observation(r, category, severity, summary, fingerprint=None, evidence='', task='', source='manual'):
    p=state_root(r)/'observations.jsonl'
    fp=fingerprint or f'{category}:{normalize(summary)}'
    obj={'id':f"obs-{int(time.time())}-{hashlib.sha1((fp+summary).encode()).hexdigest()[:7]}",
         'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'category':category,'severity':severity,
         'fingerprint':fp,'summary':summary,'evidence':evidence or '', 'task':task or '', 'source':source}
    append_jsonl(p,obj); return obj

def cmd_record(a):
    obj=record_observation(repo_root(),a.category,a.severity,a.summary,a.fingerprint,a.evidence,a.task)
    print(json.dumps(obj,ensure_ascii=False,indent=2)); return 0

def hook_log_path(r: Path) -> Path:
    override=os.getenv('V4_HOOK_LOG','')
    return Path(override) if override and override.lower()!='off' else r/'.agent-state/hook-log.jsonl'

def _epoch(ts):
    try: return calendar.timegm(time.strptime(ts,'%Y-%m-%dT%H:%M:%SZ'))
    except (TypeError,ValueError): return 0

def cmd_ingest_hooks(a):
    """Turn raw hook decisions into Growth Engine observations (never into harness changes)."""
    r=repo_root(); cursor_path=state_root(r)/'hook-cursor.json'
    cursor=''
    if cursor_path.exists():
        try: cursor=json.loads(cursor_path.read_text(encoding='utf-8')).get('ts','')
        except json.JSONDecodeError: cursor=''
    rows=[x for x in load_jsonl(hook_log_path(r)) if x.get('ts','')>cursor]
    if not rows:
        print('No new hook decisions.'); return 0
    found=[]
    by_digest=defaultdict(list)
    for x in rows: by_digest[x.get('digest','')].append(x)
    for items in by_digest.values():
        times=[_epoch(i.get('ts')) for i in items]
        if len(items)>=2 and max(times)-min(times)<=a.retry_window*60:
            x=items[-1]
            found.append(('safety','medium',f"hook-retry:{x.get('kind') or 'policy'}:{normalize(x.get('shape',''))}",
                          f"Agent repeated a blocked call {len(items)} times: {x.get('shape','')}",
                          f"{len(items)} identical {x.get('decision')} decisions within {a.retry_window} min; reason: {x.get('reason','')}"))
    for (kind,shape),count in Counter((x.get('kind',''),x.get('shape','')) for x in rows).items():
        if count>=a.frequent:
            found.append(('tooling','low',f"hook-frequent:{kind or 'policy'}:{normalize(shape)}",
                          f"{count} blocked/asked calls for '{shape}'",
                          f"kind={kind or 'policy'}; possible false positive or recurring friction"))
    for category,severity,fp,summary,evidence in found:
        record_observation(r,category,severity,summary,fp,evidence,source='hook-log')
    cursor_path.parent.mkdir(parents=True,exist_ok=True)
    cursor_path.write_text(json.dumps({'ts':max(x.get('ts','') for x in rows)})+'\n',encoding='utf-8')
    print(f'Ingested {len(rows)} hook decision(s); recorded {len(found)} observation(s).')
    return 0

def cmd_hook_stats(a):
    r=repo_root(); since=time.time()-a.days*86400
    rows=[x for x in load_jsonl(hook_log_path(r)) if _epoch(x.get('ts'))>=since]
    print(f'Hook decisions in the last {a.days} day(s): {len(rows)}')
    for (decision,kind),count in sorted(Counter((x.get('decision'),x.get('kind') or 'policy') for x in rows).items()):
        print(f'  {decision:10} {kind:12} {count}')
    for (provider,shape),count in Counter((x.get('provider'),x.get('shape')) for x in rows).most_common(a.top):
        print(f'  {count:4}  {provider}: {shape}')
    return 0

def qualified(r, rows):
    pol=policy(r); groups=defaultdict(list)
    for x in rows: groups[x.get('fingerprint','unknown')].append(x)
    ans=[]
    rank={'low':0,'medium':1,'high':2,'critical':3}
    for fp, items in groups.items():
        sev=max((x.get('severity','low') for x in items),key=lambda x:rank.get(x,0))
        threshold=pol['qualification'][sev]['min_occurrences']
        if len(items)>=threshold:
            ans.append({'fingerprint':fp,'severity':sev,'count':len(items),'threshold':threshold,
                        'latest_summary':items[-1].get('summary',''),'latest_evidence':items[-1].get('evidence',''),
                        'observation_ids':[x.get('id') for x in items]})
    return sorted(ans,key=lambda x:(rank.get(x['severity'],0),x['count']),reverse=True)

def cmd_candidates(a):
    r=repo_root(); rows=load_jsonl(state_root(r)/'observations.jsonl'); ans=qualified(r,rows)
    if a.json: print(json.dumps(ans,ensure_ascii=False,indent=2))
    elif not ans: print('No qualified growth candidates.')
    else:
        for x in ans:
            print(f"[{x['severity'].upper()}] {x['fingerprint']} — {x['count']} occurrence(s); threshold {x['threshold']}")
            print(f"  latest: {x['latest_summary']}")
            if x['latest_evidence']: print(f"  evidence: {x['latest_evidence']}")
    return 0

def cmd_snapshot(a):
    r=repo_root(); d=state_root(r)/'snapshots'; d.mkdir(parents=True,exist_ok=True)
    name=a.name or time.strftime('%Y%m%d-%H%M%S'); dest=d/f'{normalize(name)}.tar.gz'
    with tarfile.open(dest,'w:gz') as tf:
        for rel in HARNESS_PATHS:
            p=r/rel
            if p.exists(): tf.add(p,arcname=rel,recursive=True)
    print(dest); return 0

def cmd_accept(a):
    r=repo_root(); pol=policy(r); target=pol['targets'].get(a.target)
    if not target: raise SystemExit(f'Unknown target: {a.target}')
    if target.get('human_review_before_promotion') and not a.human_reviewed:
        raise SystemExit(f'{a.target} requires --human-reviewed before promotion.')
    obj={'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'candidate':a.candidate,'target':a.target,
         'summary':a.summary,'verification':a.verification,'human_reviewed':bool(a.human_reviewed)}
    append_jsonl(history_path(r),obj); print(json.dumps(obj,ensure_ascii=False,indent=2)); return 0


def cmd_reject(a):
    r=repo_root()
    obj={'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'candidate':a.candidate,'decision':'rejected',
         'summary':a.summary,'verification':a.verification or ''}
    append_jsonl(history_path(r),obj); print(json.dumps(obj,ensure_ascii=False,indent=2)); return 0


def _safe_snapshot_members(tf: tarfile.TarFile):
    allowed=[Path(x) for x in HARNESS_PATHS]
    members=[]
    for m in tf.getmembers():
        p=Path(m.name)
        valid=any(p == a or a in p.parents for a in allowed)
        if p.is_absolute() or '..' in p.parts or not p.parts or not valid:
            raise SystemExit(f'Unsafe or unexpected snapshot member: {m.name}')
        members.append(m)
    return members


def cmd_rollback(a):
    r=repo_root(); snapshots=(state_root(r)/'snapshots').resolve(); snap=Path(a.snapshot).expanduser()
    if not snap.is_absolute(): snap=snapshots/snap
    snap=snap.resolve()
    if snapshots != snap.parent or not snap.is_file():
        raise SystemExit('Rollback snapshot must be an existing file directly under the Growth Engine snapshots directory.')
    with tarfile.open(snap,'r:gz') as tf:
        members=_safe_snapshot_members(tf)
        roots=sorted(rel for rel in HARNESS_PATHS if any(Path(m.name)==Path(rel) or Path(rel) in Path(m.name).parents for m in members))
        if not a.apply:
            print('ROLLBACK DRY RUN')
            print(f'Snapshot: {snap}')
            print('Harness roots to restore: '+', '.join(roots))
            print('Re-run with --apply --human-reviewed after reviewing the diff/impact.')
            return 0
        if not a.human_reviewed:
            raise SystemExit('Rollback mutates shared harness files; --apply requires --human-reviewed.')
        # Preserve the pre-rollback harness first.
        emergency=state_root(r)/'snapshots'/f"pre-rollback-{int(time.time())}.tar.gz"
        emergency.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(emergency,'w:gz') as out:
            for rel in HARNESS_PATHS:
                current=r/rel
                if current.exists(): out.add(current,arcname=rel,recursive=True)
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td); tf.extractall(tmp,members=members)
            for rel in HARNESS_PATHS:
                dst=r/rel
                src=tmp/rel
                if src.exists():
                    if dst.is_dir(): shutil.rmtree(dst)
                    elif dst.exists(): dst.unlink()
                    if src.is_dir(): shutil.copytree(src,dst)
                    elif src.exists(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
                elif dst.exists():
                    if dst.is_dir(): shutil.rmtree(dst)
                    else: dst.unlink()
        obj={'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'decision':'rollback','snapshot':str(snap),
             'pre_rollback_snapshot':str(emergency),'human_reviewed':True}
        append_jsonl(history_path(r),obj); print(json.dumps(obj,ensure_ascii=False,indent=2)); return 0

def cmd_status(a):
    r=repo_root(); rows=load_jsonl(state_root(r)/'observations.jsonl'); hist=load_jsonl(history_path(r)); cand=qualified(r,rows)
    print(f'Observations: {len(rows)}'); print(f'Qualified candidates: {len(cand)}'); print(f'Decision history entries: {len(hist)}'); return 0

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('record'); p.add_argument('--category',choices=CATEGORIES,required=True); p.add_argument('--severity',choices=SEVERITIES,required=True); p.add_argument('--summary',required=True); p.add_argument('--fingerprint'); p.add_argument('--evidence'); p.add_argument('--task'); p.set_defaults(fn=cmd_record)
    p=sub.add_parser('candidates'); p.add_argument('--json',action='store_true'); p.set_defaults(fn=cmd_candidates)
    p=sub.add_parser('snapshot'); p.add_argument('--name'); p.set_defaults(fn=cmd_snapshot)
    p=sub.add_parser('accept'); p.add_argument('--candidate',required=True); p.add_argument('--target',required=True); p.add_argument('--summary',required=True); p.add_argument('--verification',required=True); p.add_argument('--human-reviewed',action='store_true'); p.set_defaults(fn=cmd_accept)
    p=sub.add_parser('reject'); p.add_argument('--candidate',required=True); p.add_argument('--summary',required=True); p.add_argument('--verification'); p.set_defaults(fn=cmd_reject)
    p=sub.add_parser('rollback'); p.add_argument('--snapshot',required=True); p.add_argument('--apply',action='store_true'); p.add_argument('--human-reviewed',action='store_true'); p.set_defaults(fn=cmd_rollback)
    p=sub.add_parser('status'); p.set_defaults(fn=cmd_status)
    p=sub.add_parser('ingest-hooks'); p.add_argument('--retry-window',type=int,default=30,help='minutes'); p.add_argument('--frequent',type=int,default=5); p.set_defaults(fn=cmd_ingest_hooks)
    p=sub.add_parser('hook-stats'); p.add_argument('--days',type=int,default=7); p.add_argument('--top',type=int,default=10); p.set_defaults(fn=cmd_hook_stats)
    a=ap.parse_args(); return a.fn(a)
if __name__=='__main__': raise SystemExit(main())
