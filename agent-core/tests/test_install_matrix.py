import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
INSTALL=ROOT/'install/apply.py'


def cmd(args,cwd=None,timeout=20):
    return subprocess.run(args,cwd=cwd,text=True,capture_output=True,timeout=timeout)


@unittest.skipUnless(INSTALL.exists(), 'package-only install matrix')
class InstallMatrixTests(unittest.TestCase):
    def init(self,r: Path):
        cmd(['git','init','-q'],r)

    def apply_and_profile(self,r: Path):
        p=cmd([sys.executable,str(INSTALL),'--target',str(r),'--apply','--create-project-template'])
        self.assertEqual(0,p.returncode,p.stdout+p.stderr)
        p=cmd([sys.executable,str(r/'agent-core/scripts/sync_agent_config.py')],r)
        self.assertEqual(0,p.returncode,p.stdout+p.stderr)
        p=cmd([sys.executable,str(r/'agent-core/scripts/bootstrap_project.py'),'--write'],r)
        self.assertEqual(0,p.returncode,p.stdout+p.stderr)
        p=cmd([sys.executable,str(r/'agent-core/scripts/bootstrap_project.py'),'--check'],r)
        self.assertEqual(0,p.returncode,p.stdout+p.stderr)
        p=cmd([sys.executable,str(r/'agent-core/scripts/check_agent_config.py')],r)
        self.assertEqual(0,p.returncode,p.stdout+p.stderr)
        return json.loads((r/'agent-core/project/profile.json').read_text())

    def test_node_repo(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.init(r)
            (r/'package.json').write_text(json.dumps({'packageManager':'pnpm@10.2.0','scripts':{'dev':'vite --port 4173','test':'vitest run'}}))
            (r/'pnpm-lock.yaml').write_text('lockfileVersion: 9\n')
            facts=self.apply_and_profile(r)
            self.assertEqual('pnpm@10.2.0',facts['package_manager'])
            self.assertEqual([4173],facts['explicit_ports'])

    def test_python_repo(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.init(r)
            (r/'pyproject.toml').write_text('[project]\nname="fixture"\nrequires-python=">=3.11"\n[tool.pytest.ini_options]\naddopts="-q"\n')
            facts=self.apply_and_profile(r)
            self.assertEqual('fixture',facts['python_project']['name'])
            self.assertIn('pytest',facts['python_project']['tools'])

    def test_minimal_repo_keeps_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.init(r)
            facts=self.apply_and_profile(r)
            self.assertIsNone(facts['package_manager'])
            self.assertEqual([],facts['explicit_ports'])

    def test_existing_agent_config_requires_semantic_migration(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.init(r)
            existing='# Existing repository policy\nDo not lose this fact.\n'
            (r/'AGENTS.md').write_text(existing)
            p=cmd([sys.executable,str(INSTALL),'--target',str(r),'--apply'])
            self.assertEqual(2,p.returncode)
            self.assertEqual(existing,(r/'AGENTS.md').read_text())
            self.assertIn('MIGRATION REQUIRED',p.stdout)


if __name__=='__main__': unittest.main()
