import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'growth_engine.py'
ROOT=Path(__file__).resolve().parents[2]

class GrowthEngineTests(unittest.TestCase):
    def run_cmd(self,*args,env=None):
        e=os.environ.copy(); e.update(env or {})
        return subprocess.run([sys.executable,str(SCRIPT),*args],cwd=ROOT,text=True,capture_output=True,env=e,timeout=5)

    def test_medium_requires_two(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)/'state'; hist=Path(td)/'history.jsonl'; env={'AGENT_GROWTH_STATE':str(state),'AGENT_GROWTH_HISTORY':str(hist)}
            self.assertEqual(0,self.run_cmd('record','--category','routing','--severity','medium','--fingerprint','x','--summary','one',env=env).returncode)
            p=self.run_cmd('candidates','--json',env=env); self.assertEqual([],json.loads(p.stdout))
            self.run_cmd('record','--category','routing','--severity','medium','--fingerprint','x','--summary','two',env=env)
            p=self.run_cmd('candidates','--json',env=env); self.assertEqual(1,len(json.loads(p.stdout)))

    def test_critical_qualifies_once(self):
        with tempfile.TemporaryDirectory() as td:
            env={'AGENT_GROWTH_STATE':str(Path(td)/'state'),'AGENT_GROWTH_HISTORY':str(Path(td)/'h.jsonl')}
            self.run_cmd('record','--category','safety','--severity','critical','--fingerprint','danger','--summary','danger',env=env)
            p=self.run_cmd('candidates','--json',env=env); self.assertEqual(1,len(json.loads(p.stdout)))

    def test_high_risk_accept_requires_human_review(self):
        with tempfile.TemporaryDirectory() as td:
            env={'AGENT_GROWTH_STATE':str(Path(td)/'state'),'AGENT_GROWTH_HISTORY':str(Path(td)/'h.jsonl')}
            p=self.run_cmd('accept','--candidate','x','--target','root-policy','--summary','x','--verification','tests pass',env=env)
            self.assertNotEqual(0,p.returncode)
            p=self.run_cmd('accept','--candidate','x','--target','root-policy','--summary','x','--verification','tests pass','--human-reviewed',env=env)
            self.assertEqual(0,p.returncode)

    def test_low_requires_three(self):
        with tempfile.TemporaryDirectory() as td:
            env={'AGENT_GROWTH_STATE':str(Path(td)/'state'),'AGENT_GROWTH_HISTORY':str(Path(td)/'h.jsonl')}
            for i in range(2): self.run_cmd('record','--category','context','--severity','low','--fingerprint','low-x','--summary',f'obs{i}',env=env)
            self.assertEqual([],json.loads(self.run_cmd('candidates','--json',env=env).stdout))
            self.run_cmd('record','--category','context','--severity','low','--fingerprint','low-x','--summary','obs3',env=env)
            self.assertEqual(1,len(json.loads(self.run_cmd('candidates','--json',env=env).stdout)))

    def test_reject_records_decision(self):
        with tempfile.TemporaryDirectory() as td:
            hist=Path(td)/'h.jsonl'; env={'AGENT_GROWTH_STATE':str(Path(td)/'state'),'AGENT_GROWTH_HISTORY':str(hist)}
            p=self.run_cmd('reject','--candidate','x','--summary','regressed','--verification','eval failed',env=env)
            self.assertEqual(0,p.returncode,p.stderr)
            row=json.loads(hist.read_text().splitlines()[0]); self.assertEqual('rejected',row['decision'])

    def test_rollback_apply_requires_human_review(self):
        with tempfile.TemporaryDirectory() as td:
            state=Path(td)/'state'; env={'AGENT_GROWTH_STATE':str(state),'AGENT_GROWTH_HISTORY':str(Path(td)/'h.jsonl')}
            p=self.run_cmd('snapshot','--name','gate',env=env); self.assertEqual(0,p.returncode,p.stderr)
            snap=Path(p.stdout.strip())
            dry=self.run_cmd('rollback','--snapshot',str(snap),env=env); self.assertEqual(0,dry.returncode,dry.stderr); self.assertIn('DRY RUN',dry.stdout)
            blocked=self.run_cmd('rollback','--snapshot',str(snap),'--apply',env=env); self.assertNotEqual(0,blocked.returncode)

if __name__=='__main__': unittest.main()
