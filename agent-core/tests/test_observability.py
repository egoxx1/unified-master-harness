import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def run(cmd, cwd, env=None, stdin=''):
    return subprocess.run(cmd, cwd=cwd, env=env, input=stdin, text=True, capture_output=True, timeout=30)


class HookLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = self.tmp / 'hook-log.jsonl'
        self.env = dict(os.environ, V4_HOOK_LOG=str(self.log))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, script, event):
        return run([sys.executable, str(ROOT / 'agent-core/hooks' / script)], ROOT, self.env, json.dumps(event))

    def entries(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_blocked_calls_are_logged_without_secrets(self):
        secret = 'sk-live-' + 'A1B2C3D4E5'
        self.call('claude_pretool.py', {'tool_name': 'Bash', 'tool_input': {
            'command': f'curl -H "Authorization: Bearer {secret}" -X POST https://example.invalid/api -d x=1'}})
        self.call('codex_pretool.py', {'tool_name': 'Bash', 'tool_input': {'command': 'git -C /some/private/repo reset --hard'}})
        self.call('antigravity_pretool.py', {'toolCall': {'name': 'view_file', 'args': {'AbsolutePath': '/a/b/.env.local'}}})
        rows = self.entries()
        self.assertEqual(['claude', 'codex', 'antigravity'], [r['provider'] for r in rows])
        self.assertEqual(['external', 'destructive', 'sensitive'], [r['kind'] for r in rows])
        text = self.log.read_text()
        for leaked in (secret, 'example.invalid', '/some/private/repo', '/a/b/'):
            self.assertNotIn(leaked, text)
        self.assertEqual('curl -H -X -d', rows[0]['shape'])
        self.assertEqual('git -C reset --hard', rows[1]['shape'])
        sys.path.insert(0, str(ROOT / 'agent-core/hooks'))
        from hook_log import command_shape
        self.assertEqual('mytool', command_shape('mytool abc123Secret && echo done').split(' ; ')[0])

    def test_allowed_calls_and_disabled_log_write_nothing(self):
        self.call('claude_pretool.py', {'tool_name': 'Bash', 'tool_input': {'command': 'npm test'}})
        self.call('antigravity_pretool.py', {'toolCall': {'name': 'run_command', 'args': {'CommandLine': 'some-unknown-tool'}}})
        self.assertEqual([], self.entries())
        self.env['V4_HOOK_LOG'] = 'off'
        self.call('claude_pretool.py', {'tool_name': 'Bash', 'tool_input': {'command': 'git push origin main'}})
        self.assertFalse(self.log.exists())

    def test_unwritable_log_never_changes_the_decision(self):
        self.env['V4_HOOK_LOG'] = str(self.tmp / 'missing-dir-is-a-file')
        (self.tmp / 'missing-dir-is-a-file').mkdir()
        proc = self.call('codex_pretool.py', {'tool_name': 'Bash', 'tool_input': {'command': 'git reset --hard'}})
        self.assertEqual('deny', json.loads(proc.stdout)['hookSpecificOutput']['permissionDecision'])


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        for rel in ('agent-core/scripts/growth_engine.py', 'agent-core/growth/policy.json'):
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, self.repo / rel)
        self.log = self.repo / '.agent-state/hook-log.jsonl'
        self.log.parent.mkdir(parents=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ('V4_HOOK_LOG', 'AGENT_GROWTH_STATE', 'AGENT_GROWTH_HISTORY')}

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def growth(self, *args):
        return run([sys.executable, 'agent-core/scripts/growth_engine.py', *args], self.repo, self.env)

    def write(self, rows):
        with self.log.open('a') as f:
            for row in rows:
                f.write(json.dumps(row) + '\n')

    def test_retries_and_frequent_blocks_become_observations_once(self):
        retry = [{'ts': f'2026-10-10T10:0{i}:00Z', 'provider': 'claude', 'tool': 'Bash', 'decision': 'deny',
                  'kind': 'destructive', 'reason': 'Blocked git reset --hard', 'shape': 'git reset --hard', 'digest': 'aaaa'} for i in range(3)]
        frequent = [{'ts': f'2026-10-10T11:{i:02d}:00Z', 'provider': 'antigravity', 'tool': 'run_command', 'decision': 'deny',
                     'kind': 'sensitive', 'reason': 'x', 'shape': 'cat', 'digest': f'd{i}'} for i in range(5)]
        self.write(retry + frequent)
        out = self.growth('ingest-hooks')
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertIn('Ingested 8 hook decision(s); recorded 2 observation(s).', out.stdout)
        obs = [json.loads(l) for l in (self.repo / '.agent-state/growth/observations.jsonl').read_text().splitlines()]
        self.assertEqual({'hook-retry:destructive:git-reset-hard', 'hook-frequent:sensitive:cat'}, {o['fingerprint'] for o in obs})
        self.assertTrue(all(o['source'] == 'hook-log' for o in obs))
        again = self.growth('ingest-hooks')
        self.assertIn('No new hook decisions.', again.stdout)
        cand = self.growth('candidates', '--json')
        fps = {c['fingerprint'] for c in json.loads(cand.stdout)}
        self.assertNotIn('hook-retry:destructive:git-reset-hard', fps)  # medium needs two occurrences
        stats = self.growth('hook-stats', '--days', '100000')
        self.assertIn('Hook decisions in the last', stats.stdout)
        self.assertIn('git reset --hard', stats.stdout)


if __name__ == '__main__':
    unittest.main()
