import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'agent-core/scripts/build_release.py'
spec=importlib.util.spec_from_file_location('build_release',SCRIPT)
M=importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


@unittest.skipUnless((ROOT/'install/apply.py').exists(), 'package-only release tests')
class ReleaseTests(unittest.TestCase):
    def test_release_tree_has_no_generated_project_profile(self):
        self.assertFalse((ROOT/'agent-core/project/profile.json').exists())
        self.assertFalse((ROOT/'agent-core/project/profile.md').exists())
        self.assertEqual([],M.validate_tree(ROOT))

    def test_manifest_matches_source_tree_after_generation(self):
        M.write_manifest(ROOT)
        self.assertEqual([],M.verify_manifest(ROOT))

    def test_zip_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            z=Path(td)/'v4.zip'
            M.build(ROOT,z)
            self.assertEqual([],M.verify_zip(z))
            with zipfile.ZipFile(z) as archive:
                names=archive.namelist()
            self.assertFalse(any('__pycache__' in n or '.pytest_cache' in n for n in names))


if __name__=='__main__': unittest.main()
