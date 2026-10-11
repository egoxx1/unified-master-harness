import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'agent-core/scripts/worktree.py'


def run(repo: Path,*args):
    return subprocess.run([sys.executable,str(SCRIPT),*args],cwd=repo,text=True,capture_output=True,timeout=15)


class WorktreeTests(unittest.TestCase):
    def test_create_dirty_refusal_and_remove(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); repo=base/'repo'; repo.mkdir()
            subprocess.check_call(['git','init','-q'],cwd=repo)
            subprocess.check_call(['git','config','user.email','test@example.invalid'],cwd=repo)
            subprocess.check_call(['git','config','user.name','Harness Test'],cwd=repo)
            (repo/'README.md').write_text('fixture\n')
            subprocess.check_call(['git','add','README.md'],cwd=repo)
            subprocess.check_call(['git','commit','-qm','init'],cwd=repo)

            created=run(repo,'create','parallel writer')
            self.assertEqual(0,created.returncode,created.stdout+created.stderr)
            m=re.search(r'^WORKTREE=(.+)$',created.stdout,re.MULTILINE)
            self.assertIsNotNone(m,created.stdout)
            wt=Path(m.group(1))
            self.assertTrue(wt.exists())

            listed=run(repo,'list')
            self.assertEqual(0,listed.returncode,listed.stdout+listed.stderr)
            self.assertIn(str(wt),listed.stdout)

            (wt/'dirty.txt').write_text('do not discard\n')
            refused=run(repo,'remove',str(wt))
            self.assertNotEqual(0,refused.returncode)
            self.assertTrue(wt.exists())
            self.assertIn('dirty', (refused.stdout+refused.stderr).lower())

            (wt/'dirty.txt').unlink()
            removed=run(repo,'remove',str(wt))
            self.assertEqual(0,removed.returncode,removed.stdout+removed.stderr)
            self.assertFalse(wt.exists())


if __name__=='__main__': unittest.main()
