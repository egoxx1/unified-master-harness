import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agent-core/scripts'))
sys.path.insert(0, str(ROOT / 'agent-core/hooks'))
from harness_files import make_fixture  # noqa: E402
import policy  # noqa: E402

ENV = dict(os.environ, V4_HOOK_LOG='off')


def run_hook(root: Path, script: str, event: dict, env=None):
    proc = subprocess.run([sys.executable, '-B', str(root / 'agent-core/hooks' / script)], input=json.dumps(event),
                          text=True, capture_output=True, timeout=10, cwd=root, env=env or ENV)
    return proc.stdout.strip()


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.s = json.loads((ROOT / '.claude/settings.json').read_text())

    def test_secret_reads_denied_and_examples_stay_readable(self):
        deny = self.s['permissions']['deny']
        for rule in ('Read(.env)', 'Read(.env.local)', 'Read(.env.production)', 'Read(*.pem)', 'Read(*.key)', 'Read(.netrc)'):
            self.assertIn(rule, deny)
        # Read deny rules are merged into the sandbox, but '!' carve-outs are not (measured on 2.1.296):
        # a broad .env.* rule would make .env.example unreadable from the shell, so variants are listed.
        self.assertNotIn('Read(.env.*)', deny)
        self.assertFalse([r for r in deny if r.startswith('Read(!')])

    def test_harness_files_need_approval_to_edit_and_are_shell_write_protected(self):
        ask = self.s['permissions']['ask']
        deny_write = self.s['sandbox']['filesystem']['denyWrite']
        for rel in ('AGENTS.md', 'CLAUDE.md', 'agent-core/hooks', 'agent-core/scripts', '.codex', '.agents'):
            self.assertTrue(any(rel in rule for rule in ask if rule.startswith('Edit(')), rel)
            self.assertTrue(any(rel in path for path in deny_write), rel)

    def test_sandbox_off_by_default_and_ask_rules_still_apply(self):
        # Off by default: the sandbox blocked too much ordinary work. Hooks, deny and ask rules remain;
        # ask/deny rules take precedence over the broad allow rules.
        sandbox = self.s['sandbox']
        self.assertFalse(sandbox['enabled'])
        self.assertIn('Bash', self.s['permissions']['allow'])
        self.assertIn('Bash(git push *)', self.s['permissions']['ask'])
        self.assertFalse(sandbox['allowUnsandboxedCommands'], 'the retry escape hatch plus a user Bash(*) rule would bypass the sandbox')
        self.assertEqual(['*'], sandbox['network']['allowedDomains'])
        for excluded in sandbox['excludedCommands']:
            script = re.search(r'agent-core/scripts/\S+\.py', excluded).group(0)
            self.assertTrue((ROOT / script).exists(), excluded)

    def test_lifecycle_hooks_registered(self):
        hooks = self.s['hooks']
        for event in ('PreToolUse', 'PostToolUse', 'Stop', 'PreCompact', 'SessionStart'):
            self.assertIn(event, hooks)
        self.assertIn('claude_session.py', json.dumps(hooks['Stop']))
        self.assertTrue(re.search(hooks['PostToolUse'][0]['matcher'], 'Edit'))
        self.assertTrue(re.search(hooks['PostToolUse'][0]['matcher'], 'mcp__playwright__browser_navigate'))
        self.assertFalse(re.search(hooks['PostToolUse'][0]['matcher'], 'Read'))

    def test_subagent_and_commands(self):
        agent = (ROOT / '.claude/agents/dev-reviewer.md').read_text()
        self.assertIn('name: dev-reviewer', agent)
        self.assertIn('tools: Read, Bash', agent)
        for name in ('harness-check', 'retro', 'smoke'):
            text = (ROOT / f'.claude/commands/{name}.md').read_text()
            self.assertIn('disable-model-invocation: true', text, name)


class SessionHookTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_fixture(ROOT)
        self.sid = 'test-session'

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def event(self, name, **extra):
        return run_hook(self.repo, 'claude_session.py', {'hook_event_name': name, 'session_id': self.sid, **extra})

    def edit(self, rel):
        return self.event('PostToolUse', tool_name='Edit', tool_input={'file_path': str(self.repo / rel)})

    def bash(self, command):
        return self.event('PostToolUse', tool_name='Bash', tool_input={'command': command})

    def test_stop_warns_once_after_unverified_code_edit(self):
        self.edit('src/app.py')
        out = self.event('Stop')
        self.assertIn('V4 verification warning', json.loads(out)['systemMessage'])
        self.assertIn('src/app.py', out)
        self.assertEqual('', self.event('Stop'), 'same state must not warn twice')
        self.assertNotIn('decision', out, 'warning only: never blocks')

    def test_verification_after_edit_clears_warning(self):
        self.edit('src/app.py')
        self.bash('cd src && python3 -m pytest -q tests/test_app.py')
        self.assertEqual('', self.event('Stop'))
        self.edit('src/other.ts')
        self.assertIn('src/other.ts', self.event('Stop'))
        self.bash('npm run typecheck')
        self.assertEqual('', self.event('Stop'))

    def test_docs_only_and_outside_edits_do_not_warn(self):
        self.edit('README.md')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': '/somewhere/else/x.py'})
        self.assertEqual('', self.event('Stop'))

    def test_verify_skill_and_browser_tools_count_as_verification(self):
        self.edit('web/page.tsx')
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'dev-ui-verify'})
        self.assertEqual('', self.event('Stop'))
        self.edit('web/page.tsx')
        self.event('PostToolUse', tool_name='mcp__playwright__browser_snapshot', tool_input={})
        self.assertEqual('', self.event('Stop'))

    def test_precompact_snapshot_is_reinjected_after_compaction(self):
        transcript = self.repo / 't.jsonl'
        transcript.write_text('\n'.join(json.dumps(x) for x in [
            {'type': 'user', 'message': {'content': 'Fix the login redirect bug'}},
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'ok'}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': 'x'}]}},
            {'type': 'user', 'message': {'content': [{'type': 'text', 'text': 'Also keep the remember-me flag'}]}},
        ]))
        self.edit('src/auth.py')
        self.event('PreCompact', trigger='auto', transcript_path=str(transcript))
        ctx = json.loads(self.event('SessionStart', source='compact'))['hookSpecificOutput']['additionalContext']
        for needle in ('Fix the login redirect bug', 'remember-me', 'src/auth.py', 'still unverified'):
            self.assertIn(needle, ctx)

    def test_session_start_is_silent_without_state_and_lists_active_tasks(self):
        self.assertEqual('', self.event('SessionStart', source='startup'))
        task = self.repo / '.agent-state/payment-refactor'
        task.mkdir(parents=True)
        (task / 'progress.md').write_text('# Goal: move payments to the new gateway\n- step 2 of 4\n')
        ctx = json.loads(self.event('SessionStart', source='startup'))['hookSpecificOutput']['additionalContext']
        self.assertIn('payment-refactor', ctx)
        self.assertIn('move payments to the new gateway', ctx)
        self.assertLessEqual(len(ctx), 1800)

    def test_broken_input_never_fails(self):
        proc = subprocess.run([sys.executable, '-B', str(self.repo / 'agent-core/hooks/claude_session.py')], input='not json',
                              text=True, capture_output=True, timeout=10)
        self.assertEqual(0, proc.returncode)
        self.assertEqual('', proc.stdout)


class HarnessProtectionTests(unittest.TestCase):
    def test_shell_writes_to_harness_files_need_approval(self):
        for command in ("sed -i 's/a/b/' agent-core/hooks/policy.py", 'echo x > AGENTS.md', 'cp /tmp/x .claude/settings.json',
                        'rm -f .codex/hooks.json', 'tee CLAUDE.md', 'mv agent-core/scripts/doctor.py /tmp/', "bash -c 'echo > CLAUDE.md'"):
            with self.subTest(command=command):
                verdict = policy.classify_command(command)
                self.assertEqual(('ask', 'harness'), (verdict.action, verdict.kind))

    def test_reading_or_copying_harness_files_is_fine(self):
        for command in ('cat AGENTS.md', "sed 's/a/b/' AGENTS.md", 'cp AGENTS.md /tmp/a', 'echo x > docs/notes.md', 'grep -r policy agent-core/hooks'):
            with self.subTest(command=command):
                self.assertEqual('allow', policy.classify_command(command).action)

    def test_codex_and_antigravity_fail_closed_on_harness_writes(self):
        out = run_hook(ROOT, 'codex_pretool.py', {'tool_name': 'Bash', 'tool_input': {'command': 'echo x > AGENTS.md'}})
        self.assertEqual('deny', json.loads(out)['hookSpecificOutput']['permissionDecision'])
        out = run_hook(ROOT, 'antigravity_pretool.py', {'toolCall': {'name': 'run_command', 'args': {'CommandLine': 'echo x > AGENTS.md'}}})
        self.assertEqual('deny', json.loads(out)['decision'])


class GlobalDeferralTests(unittest.TestCase):
    def setUp(self):
        self.global_copy = make_fixture(ROOT)  # stands in for ~/agent-core installed at user level
        self.project = make_fixture(ROOT)

    def tearDown(self):
        shutil.rmtree(self.global_copy, ignore_errors=True)
        shutil.rmtree(self.project, ignore_errors=True)

    def global_decision(self, cwd):
        return run_hook(self.global_copy, 'claude_pretool.py',
                        {'tool_name': 'Bash', 'cwd': str(cwd), 'tool_input': {'command': 'git reset --hard'}})

    def set_version(self, root, version):
        path = root / 'agent-core/hooks/policy.py'
        path.write_text(re.sub(r"POLICY_VERSION = '[^']+'", f"POLICY_VERSION = '{version}'", path.read_text()))

    def test_defers_to_equal_or_newer_project_hooks(self):
        self.assertEqual('', self.global_decision(self.project / 'src'))
        self.set_version(self.project, '9.0.0')
        self.assertEqual('', self.global_decision(self.project))

    def test_keeps_guarding_older_projects_and_plain_folders(self):
        self.set_version(self.project, '4.0.0')
        self.assertIn('"deny"', self.global_decision(self.project))
        plain = Path(tempfile.mkdtemp())
        try:
            self.assertIn('"deny"', self.global_decision(plain))
        finally:
            shutil.rmtree(plain, ignore_errors=True)

    def test_project_copy_never_defers_to_itself(self):
        out = run_hook(self.project, 'claude_pretool.py', {'tool_name': 'Bash', 'cwd': str(self.project), 'tool_input': {'command': 'git reset --hard'}})
        self.assertIn('"deny"', out)


if __name__ == '__main__':
    unittest.main()
