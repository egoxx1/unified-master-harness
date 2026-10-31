import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'agent-core/scripts/bootstrap_project.py'
spec=importlib.util.spec_from_file_location('bootstrap_project',SCRIPT)
M=importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


class BootstrapTests(unittest.TestCase):
    def test_node_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); (r/'package.json').write_text(json.dumps({'packageManager':'pnpm@10.1.0','scripts':{'dev':'vite --port 5173','test':'vitest'}}))
            (r/'pnpm-lock.yaml').write_text('lockfileVersion: 9')
            facts=M.detect(r)
            self.assertEqual('pnpm@10.1.0',facts['package_manager'])
            self.assertEqual([5173],facts['explicit_ports'])
            self.assertEqual('vitest',facts['package_scripts']['test'])

    def test_python_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td); (r/'pyproject.toml').write_text('[project]\nname="demo"\nrequires-python=">=3.12"\n[tool.pytest.ini_options]\naddopts="-q"\n')
            facts=M.detect(r)
            self.assertTrue(facts['python_project']['pyproject'])
            self.assertEqual('demo',facts['python_project']['name'])
            self.assertIn('pytest',facts['python_project']['tools'])

    def test_minimal_keeps_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            facts=M.detect(Path(td))
            self.assertIsNone(facts['package_manager'])
            self.assertEqual([],facts['explicit_ports'])
            self.assertEqual({},facts['package_scripts'])


if __name__=='__main__': unittest.main()
