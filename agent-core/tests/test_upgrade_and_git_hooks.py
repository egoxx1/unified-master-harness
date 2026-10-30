import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agent-core/scripts'))
from harness_files import make_fixture  # noqa: E402


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=60)


class UpgradeTests(unittest.TestCase):
    def test_template_manifest_is_current(self):
        # A stale manifest makes an unzipped template treat changed harness files as project edits on upgrade.
        import upgrade_harness
        committed = json.loads((ROOT / 'agent-core/HARNESS-MANIFEST.json').read_text())
        self.assertEqual(upgrade_harness.build_manifest(ROOT), committed,
                         'run: python3 agent-core/scripts/upgrade_harness.py --write-manifest')

    def setUp(self):
        self.project = make_fixture(ROOT)
        self.template = make_fixture(ROOT)
        run([sys.executable, '-B', 'agent-core/scripts/upgrade_harness.py', '--write-manifest'], self.project)

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)
        shutil.rmtree(self.template, ignore_errors=True)

    def upgrade(self, *extra):
        return run([sys.executable, '-B', str(self.project / 'agent-core/scripts/upgrade_harness.py'),
                    '--from', str(self.template), '--target', str(self.project), *extra], self.project)

    def test_updates_untouched_files_and_protects_project_changes(self):
        # project customised its policy; template changed policy, a skill and the hook and added a file
        (self.project / 'AGENTS.md').write_text((self.project / 'AGENTS.md').read_text() + '\nProject rule.\n')
        (self.project / 'PROJECT.md').write_text('# my product\n')
        (self.template / 'AGENTS.md').write_text((self.template / 'AGENTS.md').read_text() + '\nTemplate rule.\n')
        (self.template / '.agents/skills/dev-plan/SKILL.md').write_text(
            (self.template / '.agents/skills/dev-plan/SKILL.md').read_text() + '\nNew step.\n')
        (self.template / 'agent-core/hooks/policy.py').write_text(
            (self.template / 'agent-core/hooks/policy.py').read_text() + '\n# template change\n')
        (self.template / 'docs/agent/NEW.md').write_text('new doc\n')

        dry = self.upgrade()
        self.assertIn('CONFLICT AGENTS.md', dry.stdout)
        self.assertIn('UPDATE   agent-core/hooks/policy.py', dry.stdout)
        self.assertIn('UPDATE   .agents/skills/dev-plan/SKILL.md', dry.stdout)
        self.assertIn('ADD      docs/agent/NEW.md', dry.stdout)
        self.assertFalse((self.project / 'docs/agent/NEW.md').exists(), 'dry run must not write')

        applied = self.upgrade('--apply')
        self.assertEqual(0, applied.returncode, applied.stderr)
        self.assertIn('Project rule.', (self.project / 'AGENTS.md').read_text())
        self.assertIn('Template rule.', (self.project / 'AGENTS.md.v4-new').read_text())
        self.assertIn('# template change', (self.project / 'agent-core/hooks/policy.py').read_text())
        self.assertIn('New step.', (self.project / '.claude/skills/dev-plan/SKILL.md').read_text(), 'mirror re-synced')
        self.assertEqual('# my product\n', (self.project / 'PROJECT.md').read_text())
        self.assertTrue(list((self.project / '.agent-state/upgrade-backup').rglob('policy.py')))
        self.assertEqual(self.project.joinpath('AGENTS.md').read_bytes(), self.project.joinpath('.agents/AGENTS.md').read_bytes())
        (self.project / 'AGENTS.md.v4-new').unlink()
        again = self.upgrade()  # same template again: the project's own policy edit is kept, nothing else to do
        self.assertIn('KEEP     AGENTS.md', again.stdout)
        self.assertIn('ADD 0, UPDATE 0, KEEP 1, CONFLICT 0, REMOVE 0', again.stdout)
        (self.template / 'AGENTS.md').write_text((self.template / 'AGENTS.md').read_text() + '\nSecond template rule.\n')
        self.assertIn('CONFLICT AGENTS.md', self.upgrade().stdout)  # both sides changed again

    def test_without_manifest_differences_are_conflicts_unless_taken(self):
        (self.project / 'agent-core/HARNESS-MANIFEST.json').unlink()
        (self.template / 'agent-core/hooks/policy.py').write_text(
            (self.template / 'agent-core/hooks/policy.py').read_text() + '\n# template change\n')
        self.assertIn('CONFLICT agent-core/hooks/policy.py', self.upgrade().stdout)
        self.assertIn('UPDATE   agent-core/hooks/policy.py', self.upgrade('--take-template', 'agent-core/hooks/policy.py').stdout)


class GitHookTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_fixture(ROOT)
        run(['git', 'config', 'user.email', 't@example.invalid'], self.repo)
        run(['git', 'config', 'user.name', 't'], self.repo)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_precommit_blocks_staged_secrets_and_allows_normal_commits(self):
        self.assertEqual(0, run([sys.executable, '-B', 'agent-core/scripts/install_git_hooks.py'], self.repo).returncode)
        (self.repo / 'app.py').write_text('print(1)\n')
        (self.repo / '.env.example').write_text('KEY=\n')
        run(['git', 'add', 'app.py', '.env.example'], self.repo)
        ok = run(['git', 'commit', '-qm', 'normal'], self.repo)
        self.assertEqual(0, ok.returncode, ok.stderr)
        (self.repo / '.env.production').write_text('')
        run(['git', 'add', '-f', '.env.production'], self.repo)
        blocked = run(['git', 'commit', '-qm', 'secret'], self.repo)
        self.assertNotEqual(0, blocked.returncode)
        self.assertIn('.env.production', blocked.stderr)

    def test_installer_does_not_clobber_foreign_hooks(self):
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\necho mine\n')
        self.assertEqual(1, run([sys.executable, '-B', 'agent-core/scripts/install_git_hooks.py'], self.repo).returncode)
        self.assertIn('echo mine', hook.read_text())
        self.assertEqual(0, run([sys.executable, '-B', 'agent-core/scripts/install_git_hooks.py', '--force'], self.repo).returncode)
        self.assertIn('echo mine', (self.repo / '.git/hooks/pre-commit.before-v4').read_text())


class CiTemplateTests(unittest.TestCase):
    def test_workflow_runs_the_harness_checks(self):
        text = (ROOT / '.github/workflows/agent-harness.yml').read_text()
        for needle in ('check_agent_config.py', 'unittest discover -s agent-core/tests', 'doctor.py --repo-only --strict'):
            self.assertIn(needle, text)

    def test_codex_project_config_overrides_unsafe_user_defaults(self):
        text = (ROOT / '.codex/config.toml').read_text()
        self.assertIn('sandbox_mode = "workspace-write"', text)
        self.assertIn('approval_policy = "on-request"', text)


if __name__ == '__main__':
    unittest.main()
