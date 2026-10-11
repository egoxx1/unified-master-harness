import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / 'agent-core/scripts/doctor.py'


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.repo = Path(tempfile.mkdtemp())
        subprocess.run(['git', 'init', '-q'], cwd=self.repo, check=True)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.repo, ignore_errors=True)

    def doctor(self, *extra):
        proc = subprocess.run([sys.executable, str(DOCTOR), '--repo', str(self.repo), '--home', str(self.home),
                               '--no-versions', '--json', *extra], text=True, capture_output=True, timeout=30)
        return proc.returncode, json.loads(proc.stdout or '[]')

    def put(self, rel, text):
        path = self.home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def levels(self, findings, area):
        return [(f['level'], f['message']) for f in findings if f['area'] == area]

    def test_reports_the_settings_found_on_a_real_machine(self):
        old = self.home / 'agent-core'
        (old / 'hooks').mkdir(parents=True)
        (old / 'VERSION').write_text('4.0.0\n')
        (old / 'hooks/policy.py').write_text('# old policy without a version marker\n')
        self.put('.claude/settings.json', json.dumps({'permissions': {'defaultMode': 'acceptEdits', 'allow': ['Bash', 'Read']},
                                                      'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [{'type': 'command',
                                                          'command': 'python3 -B "$HOME/agent-core/hooks/claude_pretool.py"'}]}]}}))
        self.put('.codex/config.toml', 'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n')
        self.put('.gemini/antigravity-cli/settings.json', json.dumps({'toolPermission': 'always-proceed', 'trustedWorkspaces': []}))
        code, findings = self.doctor()
        self.assertEqual(0, code)
        claude = self.levels(findings, 'claude')
        self.assertTrue(any(l == 'WARN' and 'every Bash command' in m for l, m in claude))
        self.assertTrue(any(l == 'WARN' and 'older harness copy' in m for l, m in claude))
        (old / 'hooks/policy.py').write_text((ROOT / 'agent-core/hooks/policy.py').read_text())
        _, findings = self.doctor()
        self.assertTrue(any(l == 'INFO' and 'defers' in m for l, m in self.levels(findings, 'claude')))
        codex = self.levels(findings, 'codex')
        self.assertTrue(any(l == 'WARN' and 'not trusted' in m for l, m in codex))
        self.assertTrue(any(l == 'RISK' and 'danger-full-access' in m for l, m in codex))
        self.assertTrue(any(l == 'WARN' and 'always-proceed' in m for l, m in self.levels(findings, 'antigravity')))
        code, _ = self.doctor('--strict')
        self.assertEqual(1, code)

    def test_trusted_project_sandbox_override_downgrades_codex_risk(self):
        self.put('.codex/config.toml', f'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n\n[projects."{self.repo}"]\ntrust_level = "trusted"\n')
        (self.repo / '.codex').mkdir()
        (self.repo / '.codex/config.toml').write_text('sandbox_mode = "workspace-write"\napproval_policy = "on-request"\n')
        _, findings = self.doctor()
        codex = self.levels(findings, 'codex')
        self.assertFalse(any(l == 'RISK' for l, _ in codex), codex)
        self.assertTrue(any('overrides it with sandbox_mode=workspace-write' in m for _, m in codex))

    def test_tracked_and_unignored_secrets(self):
        (self.repo / '.env').write_text('')
        (self.repo / 'server.key').write_text('')
        subprocess.run(['git', 'add', 'server.key'], cwd=self.repo, check=True)
        code, findings = self.doctor('--repo-only', '--strict')
        repo = self.levels(findings, 'repo')
        self.assertEqual(1, code)
        self.assertTrue(any(l == 'RISK' and 'server.key' in m for l, m in repo))
        self.assertTrue(any(l == 'WARN' and '.env' in m for l, m in repo))
        self.assertFalse([f for f in findings if f['area'] != 'repo'])

    def test_clean_repo_passes_strict(self):
        (self.repo / '.gitignore').write_text('.env\n')
        (self.repo / '.env').write_text('')
        code, findings = self.doctor('--repo-only', '--strict')
        self.assertEqual(0, code, findings)


if __name__ == '__main__':
    unittest.main()
