import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
INSTALL=ROOT/'install/apply.py'


def run(*args,cwd=None):
    return subprocess.run([sys.executable,str(INSTALL),*args],cwd=cwd,text=True,capture_output=True,timeout=15)


@unittest.skipUnless((ROOT / 'install/apply.py').exists(), 'package-only installer tests')
class InstallerTests(unittest.TestCase):
    def init_repo(self,path: Path):
        subprocess.check_call(['git','init','-q'],cwd=path)

    def test_clean_repo_apply(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.init_repo(r)
            p=run('--target',str(r),'--apply','--create-project-template')
            self.assertEqual(0,p.returncode,p.stdout+p.stderr)
            self.assertTrue((r/'AGENTS.md').exists())
            self.assertTrue((r/'.agents/skills/dev-debug/SKILL.md').exists())
            self.assertTrue((r/'.agents/hooks.json').exists())
            self.assertTrue((r/'PROJECT.md').exists())
            self.assertIn('.agent-state/',(r/'.gitignore').read_text())

    def test_existing_agent_config_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.init_repo(r); (r/'AGENTS.md').write_text('# Existing\n')
            p=run('--target',str(r),'--apply')
            self.assertEqual(2,p.returncode)
            self.assertEqual('# Existing\n',(r/'AGENTS.md').read_text())
            self.assertIn('MIGRATION REQUIRED',p.stdout)

    def test_existing_product_readme_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); self.init_repo(r); (r/'README.md').write_text('product readme\n')
            p=run('--target',str(r),'--apply')
            self.assertEqual(0,p.returncode,p.stdout+p.stderr)
            self.assertEqual('product readme\n',(r/'README.md').read_text())


if __name__=='__main__': unittest.main()
