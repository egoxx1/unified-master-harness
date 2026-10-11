#!/usr/bin/env python3
"""Pure V4 safety classification shared by provider adapters.

This is a narrow guardrail, not a shell parser or sandbox. It blocks known
high-impact destructive patterns and broad secret/environment exposure, and
marks external/production actions that need explicit user approval, while
leaving ordinary development commands autonomous.

Verdict.action is allow | ask | deny. Verdict.kind explains *why* so each
provider adapter can map it onto what its hook contract actually supports:

- destructive: unrecoverable local/remote damage            -> always deny
- sensitive:   may expose credentials                       -> ask (or deny)
- external:    push/publish/deploy/prod-DB mutation          -> needs approval
- harness:     shell writes to the harness's own enforcement files -> needs approval
"""
from __future__ import annotations

import fnmatch
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY_VERSION = '4.2.0'  # read by scope.py so a global copy can defer to an equal-or-newer project copy

SAFE_ENV_NAMES = {'.env.example', '.env.sample', '.env.template', '.env.defaults'}
SENSITIVE_BASENAMES = {
    'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa', 'credentials', 'credentials.json',
    'service-account.json', 'service_account.json', '.npmrc', '.pypirc',
    '.envrc', '.netrc', '_netrc', '.pgpass', '.git-credentials', '.dockercfg', 'kubeconfig',
}
SENSITIVE_PATH_SUFFIXES = ('.kube/config', '.docker/config.json', '.config/gh/hosts.yml')
SENSITIVE_SUFFIXES = ('.pem', '.key', '.p12', '.pfx')

# Programs that only test/list a path or load it into the shell without printing it.
PATH_META_PROGRAMS = {'ls', 'test', '[', '[[', 'stat', 'source', '.'}
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'fish'}
WRAPPERS = {'sudo', 'command', 'builtin', 'nohup', 'nice', 'timeout', 'time', 'stdbuf', 'noglob', 'xargs', 'env'}
WRAPPER_VALUE_FLAGS = {
    'sudo': {'-u', '-g', '-C', '-D', '-h', '-p', '-r', '-t', '-U'},
    'nice': {'-n'},
    'timeout': {'-s', '-k', '--signal', '--kill-after'},
    'stdbuf': {'-i', '-o', '-e'},
    'xargs': {'-I', '-n', '-P', '-L', '-d', '-E', '-s', '-a'},
    'env': {'-u', '-C', '-S'},
}
GIT_VALUE_OPTIONS = {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path', '--config-env', '--super-prefix'}
DB_CLIENTS = {'psql', 'mysql', 'mariadb', 'sqlite3', 'mongosh', 'mongo', 'redis-cli', 'cockroach', 'clickhouse-client', 'sqlcmd'}
DB_DESTRUCTIVE = re.compile(
    r'\b(?:drop\s+(?:database|schema|table|collection)|truncate\b|flushall\b|flushdb\b|dropdatabase\s*\()', re.I)
PUBLISH_SUBCOMMANDS = {
    # program: subcommands that publish, deploy or mutate shared remote state
    'npm': {'publish', 'unpublish', 'deprecate'}, 'pnpm': {'publish'}, 'yarn': {'publish', 'npm'}, 'bun': {'publish'},
    'cargo': {'publish', 'yank'}, 'twine': {'upload'}, 'poetry': {'publish'}, 'gem': {'push', 'yank'},
    'docker': {'push'}, 'podman': {'push'}, 'flyctl': {'deploy'}, 'fly': {'deploy'}, 'netlify': {'deploy'},
    'firebase': {'deploy'}, 'wrangler': {'deploy', 'publish'}, 'serverless': {'deploy', 'remove'}, 'sls': {'deploy', 'remove'},
    'vercel': {'deploy', '--prod', 'promote', 'remove', 'rm'}, 'heroku': {'releases:rollback'},
    'kubectl': {'apply', 'create', 'delete', 'patch', 'replace', 'scale', 'set', 'rollout'},
    'terraform': {'apply', 'destroy', 'import'}, 'helm': {'install', 'upgrade', 'uninstall', 'rollback'},
}
PACKAGE_RUNNERS = {'npm', 'pnpm', 'yarn', 'bun'}
EXTERNAL_SCRIPT = re.compile(r'(?:deploy|release|publish)(?:[:_-].*)?', re.I)
CURL_MUTATION = re.compile(
    r'(?:-X\s*(?:POST|PUT|PATCH|DELETE)\b|--request[=\s]+(?:POST|PUT|PATCH|DELETE)\b|--data\b|--data-\w+|(?:^|\s)-d(?:\s|$)|--upload-file\b|(?:^|\s)-T(?:\s|$)|(?:^|\s)-F(?:\s|$)|--form\b)', re.I)
EMBEDDED_SECRET = re.compile(
    r'(?:^|[\s\'"(=,:/])((?:\.env(?:\.[\w-]+)*|\.envrc|\.netrc|\.pgpass|\.git-credentials|id_rsa|id_ed25519|'
    r'credentials\.json|service[-_]account\.json|[\w-]+\.(?:pem|key|p12|pfx)))(?=$|[\s\'")\],;:])', re.I)
# Deleting any of these (or a single user's home such as /Users/<name>) is catastrophic.
SYSTEM_ROOTS = {
    '/Users', '/home', '/root', '/etc', '/usr', '/var', '/bin', '/sbin', '/opt', '/lib', '/boot',
    '/System', '/Library', '/Applications', '/private', '/Volumes',
}
HOME_DIR_PATTERN = re.compile(r'(?:/Users|/home)/[^/]+|/root|~[A-Za-z0-9._-]+')
BROAD_PATHSPECS = {'.', ':', ':/', ':/*', '*', ':(top)', ':(top)*', '-A', '--all'}
# Files that enforce the harness itself. Agents may read them but must not rewrite them unasked.
HARNESS_PROTECTED = re.compile(
    r'(?:^|/)(?:AGENTS\.md|CLAUDE\.md|agent-core/hooks/|agent-core/scripts/|agent-core/evals/|agent-core/growth/policy\.json'
    r'|\.codex/|\.agents/|\.claude/settings[^/]*\.json|\.claude/agents/|\.claude/commands/)')
FILE_WRITERS = {'tee', 'truncate', 'rm', 'unlink', 'mv', 'cp', 'install', 'ln', 'dd', 'chmod', 'chown'}
SEVERITY = {'allow': 0, 'ask': 1, 'deny': 2}
MAX_DEPTH = 3


@dataclass(frozen=True)
class Verdict:
    action: str  # allow | ask | deny
    reason: str = ''
    kind: str = ''  # '' | destructive | sensitive | external


ALLOW = Verdict('allow', '')


def _destructive(reason: str) -> Verdict:
    return Verdict('deny', reason, 'destructive')


def _sensitive(reason: str) -> Verdict:
    return Verdict('ask', reason, 'sensitive')


def _external(reason: str) -> Verdict:
    return Verdict('ask', reason, 'external')


def _harness(reason: str) -> Verdict:
    return Verdict('ask', reason, 'harness')


def _worst(a: Verdict, b: Verdict) -> Verdict:
    if SEVERITY[b.action] > SEVERITY[a.action]:
        return b
    if SEVERITY[b.action] == SEVERITY[a.action] and a.kind == 'sensitive' and b.kind in ('external', 'harness'):
        return b  # approval for an action is the stronger requirement among asks
    return a


def sensitive_path(path: str) -> bool:
    if not path:
        return False
    raw = path.strip().strip("\"'").replace('\\', '/')
    name = Path(raw).name.lower()
    if name in SAFE_ENV_NAMES:
        return False
    if name == '.env' or name.startswith('.env.'):
        return True
    if name in SENSITIVE_BASENAMES:
        return True
    if raw.lower().endswith(SENSITIVE_PATH_SUFFIXES):
        return True
    return name.endswith(SENSITIVE_SUFFIXES)


def _embedded_sensitive(text: str) -> str | None:
    for match in EMBEDDED_SECRET.finditer(text):
        if sensitive_path(match.group(1)):
            return match.group(1)
    return None


def _shell_words(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return re.findall(r'(?:"[^"]*"|\'[^\']*\'|\S+)', command)


def _segments(command: str) -> list[list[str]]:
    """Split on shell control operators while respecting quotes."""
    segments: list[list[str]] = []
    for line in command.splitlines() or ['']:
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=';&|')
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            tokens = []
            for part in re.split(r'(?:&&|\|\||;|\|)', line):
                tokens.extend(_shell_words(part) + [';'])
        current: list[str] = []
        for token in tokens:
            if token and set(token) <= set(';&|'):
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(token)
        if current:
            segments.append(current)
    return segments


def _unwrap(tokens: list[str]) -> list[str]:
    """Drop leading VAR=value assignments and transparent wrappers (sudo, timeout, xargs, env ...)."""
    tokens = list(tokens)
    changed = True
    while tokens and changed:
        changed = False
        while tokens and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', tokens[0]):
            tokens = tokens[1:]
            changed = True
        if tokens and Path(tokens[0]).name in WRAPPERS:
            name = Path(tokens[0]).name
            if name == 'env' and len(tokens) == 1:
                return tokens  # bare `env` is an environment dump, keep it visible
            tokens = tokens[1:]
            value_flags = WRAPPER_VALUE_FLAGS.get(name, set())
            while tokens and (tokens[0].startswith('-') or (name == 'env' and '=' in tokens[0])):
                flag = tokens.pop(0)
                if flag in value_flags and tokens:
                    tokens.pop(0)
            if name == 'timeout' and tokens and re.fullmatch(r'\d+(?:\.\d+)?[smhd]?', tokens[0]):
                tokens = tokens[1:]
            changed = True
    return tokens


def _has_force_flag(tokens: list[str]) -> bool:
    for token in tokens:
        if token in {'--force', '--force-with-lease', '--force-if-includes', '-f'}:
            return True
        if token.startswith('--force=') or token.startswith('--force-with-lease='):
            return True
        if token.startswith('-') and not token.startswith('--') and 'f' in token[1:]:
            return True
    return False


def _rm_is_recursive_force(tokens: list[str]) -> bool:
    recursive = False
    force = False
    for token in tokens[1:]:
        if token == '--':
            break
        if token == '--recursive':
            recursive = True
        elif token == '--force':
            force = True
        elif token.startswith('-') and not token.startswith('--'):
            flags = token[1:]
            recursive = recursive or ('r' in flags or 'R' in flags)
            force = force or ('f' in flags)
    return recursive and force


def _rm_targets(tokens: list[str]) -> list[str]:
    targets: list[str] = []
    after_double_dash = False
    for token in tokens[1:]:
        if token == '--':
            after_double_dash = True
            continue
        if not after_double_dash and token.startswith('-'):
            continue
        targets.append(token.strip("\"'"))
    return targets


def _catastrophic_target(target: str) -> bool:
    value = target.strip()
    if re.fullmatch(r'/+(?:\*|\.)?', value):
        return True
    # `~/`, `$HOME/`, `../` and `./` mean the same directory as their slash-less forms.
    if not re.fullmatch(r'/+', value):
        value = value.rstrip('/')
        if value.endswith('/*'):
            value = value[:-2].rstrip('/') or '/'
    exact = {'', '/', '.', '..', '~', '$HOME', '${HOME}', '*', '.*'}
    if value in exact or value in SYSTEM_ROOTS or HOME_DIR_PATTERN.fullmatch(value):
        return True
    home = os.path.expanduser('~').rstrip('/')
    return bool(home) and home != '~' and value == home


def _broad_env_dump(command: str) -> bool:
    low = command.strip().lower()
    shell_dump = re.search(r'(^|[;&|]\s*)(env|printenv|set|export\s+-p)(?:\s|$|[|;&])', low)
    env_wrapper = re.search(r'(^|[;&|]\s*)env\s+[a-z_][a-z0-9_]*=', low)
    if shell_dump and not env_wrapper:
        return True

    python = r'\bpython(?:3(?:\.\d+)?)?\b'
    if re.search(python, low) and 'os.environ' in low:
        if any(marker in low for marker in ('print(', 'pprint', 'json.dumps', '.items()', '.keys()', '.values()', 'dict(os.environ)', 'repr(', 'sys.stdout.write')):
            return True

    if re.search(r'\bnode\b', low) and 'process.env' in low:
        if any(marker in low for marker in ('console.log', 'console.dir', 'json.stringify', 'object.entries', 'object.keys', 'object.values', 'process.stdout')):
            return True
    return False


def _git_subcommand(tokens: list[str]) -> tuple[str, list[str]]:
    """Return (subcommand, args) after skipping git global options such as -C <dir> or -c k=v."""
    rest = tokens[1:]
    while rest and rest[0].startswith('-'):
        option = rest.pop(0)
        if option in GIT_VALUE_OPTIONS and rest:
            rest.pop(0)
    if not rest:
        return '', []
    return rest[0].lower(), rest[1:]


def _classify_git(tokens: list[str]) -> Verdict:
    sub, args = _git_subcommand(tokens)
    if sub == 'reset' and any(a == '--hard' or a.startswith('--hard=') for a in args):
        return _destructive('Blocked git reset --hard because it can discard user or other-agent work.')
    if sub == 'clean' and _has_force_flag(args):
        return _destructive('Blocked forced git clean because it can delete untracked user work.')
    if sub == 'push':
        forced_refspec = any(a.startswith('+') and len(a) > 1 for a in args)
        if _has_force_flag(args) or '--mirror' in args or forced_refspec:
            return _destructive('Blocked force push because remote history rewrites require explicit handling.')
        return _external('git push publishes work to a remote and needs explicit user approval.')
    discard = _git_discard_reason(sub, args)
    if discard:
        return _destructive(discard)
    return ALLOW


def _pathspecs(args: list[str]) -> list[str]:
    if '--' in args:
        return args[args.index('--') + 1:]
    return [a for a in args if not a.startswith('-') or a in BROAD_PATHSPECS]


def _git_discard_reason(sub: str, args: list[str]) -> str:
    """Commands that throw away uncommitted or stashed work in bulk."""
    broad = any(a in BROAD_PATHSPECS for a in _pathspecs(args))
    forced = any(a in {'-f', '--force', '--discard-changes'} for a in args)
    if sub == 'checkout' and (broad or forced):
        return 'Blocked git checkout that discards uncommitted changes across the tree.'
    if sub == 'switch' and forced:
        return 'Blocked git switch --discard-changes/--force because it discards uncommitted changes.'
    if sub == 'restore':
        staged_only = any(a in {'--staged', '-S'} for a in args) and not any(a in {'--worktree', '-W'} for a in args)
        if broad and not staged_only:
            return 'Blocked broad git restore because it discards uncommitted changes across the tree.'
    if sub == 'stash' and args[:1] and args[0] in {'clear', 'drop'}:
        return f'Blocked git stash {args[0]} because it permanently discards stashed work.'
    return ''


def _external_action(program: str, tokens: list[str]) -> str:
    args = [t for t in tokens[1:]]
    words = [a.lower() for a in args if not a.startswith('-')]
    if program in PACKAGE_RUNNERS and words[:1] == ['run'] and len(words) > 1 and EXTERNAL_SCRIPT.fullmatch(words[1]):
        return f'{program} run {words[1]} looks like a publish/deploy script and needs explicit user approval.'
    if program in PACKAGE_RUNNERS and words and EXTERNAL_SCRIPT.fullmatch(words[0]) and words[0] not in {'publish'}:
        return f'{program} {words[0]} looks like a publish/deploy script and needs explicit user approval.'
    subs = PUBLISH_SUBCOMMANDS.get(program)
    if subs:
        lowered = [a.lower() for a in args]
        first = words[0] if words else ''
        if first in subs or (program == 'vercel' and '--prod' in lowered) or (program == 'yarn' and lowered[:2] == ['npm', 'publish']):
            return f'{program} {first or " ".join(lowered[:1])} publishes or mutates shared remote state and needs explicit user approval.'
    if program == 'gh' and len(words) >= 2 and (words[0], words[1]) in {
            ('pr', 'merge'), ('release', 'create'), ('release', 'upload'), ('release', 'delete'), ('workflow', 'run'),
            ('issue', 'create'), ('repo', 'create'), ('repo', 'delete'), ('pr', 'create')}:
        return f'gh {words[0]} {words[1]} acts on GitHub and needs explicit user approval.'
    if program == 'aws' and len(words) >= 2 and words[0] == 's3' and words[1] in {'cp', 'mv', 'rm', 'sync', 'rb'}:
        return f'aws s3 {words[1]} mutates remote storage and needs explicit user approval.'
    if program in {'curl', 'wget', 'http', 'https'} and CURL_MUTATION.search(' '.join(args)):
        return 'Mutating HTTP request needs explicit user approval.'
    return ''


def _harness_write(program: str, tokens: list[str], raw: str) -> str:
    """Name of a protected harness file this shell segment would modify, if any."""
    args = [t for t in tokens[1:] if not t.startswith('-')]
    targets: list[str] = []
    if program in ('sed', 'perl') and any(t == '-i' or t.startswith('-i') or t.startswith('--in-place') for t in tokens[1:]):
        targets = args
    elif program in ('cp', 'install', 'ln'):
        targets = args[-1:]
    elif program in FILE_WRITERS:
        targets = args
    targets += re.findall(r'>{1,2}\s*([^\s;&|]+)', raw)
    for target in targets:
        if HARNESS_PROTECTED.search(target.strip("\"'")):
            return target
    return ''


def _classify_segment(tokens: list[str], depth: int) -> Verdict:
    tokens = _unwrap(tokens)
    if not tokens:
        return ALLOW
    program = Path(tokens[0]).name
    text = ' '.join(tokens)

    if program in SHELLS or program == 'eval':
        if program == 'eval':
            return classify_command(' '.join(tokens[1:]), depth + 1)
        for index, token in enumerate(tokens[1:], start=1):
            if token.startswith('-') and not token.startswith('--') and 'c' in token[1:] and index + 1 < len(tokens):
                return classify_command(tokens[index + 1], depth + 1)

    if program == 'git':
        verdict = _classify_git(tokens)
        if verdict.action != 'allow':
            return verdict

    if program == 'rm' and _rm_is_recursive_force(tokens):
        if any(_catastrophic_target(t) for t in _rm_targets(tokens)):
            return _destructive('Blocked broad recursive forced deletion of root/current/parent/home/wildcard target.')

    protected = _harness_write(program, tokens, text)
    if protected:
        return _harness(f'Shell write to harness enforcement file {protected} needs explicit user approval.')

    if program in DB_CLIENTS and DB_DESTRUCTIVE.search(text):
        return _external('Destructive database statement needs explicit user approval.')
    if program in {'dropdb', 'dropuser'}:
        return _external(f'{program} destroys database state and needs explicit user approval.')

    if program not in PATH_META_PROGRAMS:
        for token in tokens[1:]:
            candidate = token.split('=', 1)[1] if token.startswith('-') and '=' in token else token
            if not candidate.startswith('-') and sensitive_path(candidate):
                return _sensitive(f'Command references sensitive file {Path(candidate).name}, which may expose credentials.')
            embedded = _embedded_sensitive(token)
            if embedded:
                return _sensitive(f'Command references sensitive file {embedded}, which may expose credentials.')

    external = _external_action(program, tokens)
    if external:
        return _external(external)
    return ALLOW


def classify_command(command: str, depth: int = 0) -> Verdict:
    command = (command or '').strip()
    if not command:
        return ALLOW
    if depth > MAX_DEPTH:
        return _sensitive('Deeply nested shell wrapping cannot be analysed safely.')

    verdict = ALLOW
    if _broad_env_dump(command):
        verdict = _destructive('Blocked broad environment dump because it can expose credentials.')
    for segment in _segments(command):
        verdict = _worst(verdict, _classify_segment(segment, depth))
        if verdict.action == 'deny':
            return verdict
    return verdict


def _first_value(obj: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
            return ' '.join(value)
    return ''


def _glob_targets_sensitive(pattern: str) -> bool:
    probes = ('.env', '.env.local', '.env.production', 'id_rsa', 'server.pem', 'private.key', '.netrc', '.envrc')
    return any(fnmatch.fnmatch(probe, pattern) and sensitive_path(probe) for probe in probes) or sensitive_path(pattern)


def classify_generic(tool_name: str, tool_input: dict[str, Any]) -> Verdict:
    tool_input = tool_input or {}
    if tool_name in {'Bash', 'PowerShell', 'run_command', 'execute_command', 'exec_command', 'shell', 'local_shell'}:
        command = _first_value(tool_input, ('command', 'CommandLine', 'cmd', 'script'))
        return classify_command(command)
    if tool_name in {'Read', 'view_file', 'read_file'}:
        path = _first_value(tool_input, ('file_path', 'path', 'AbsolutePath', 'TargetFile'))
        if sensitive_path(path):
            return _sensitive(f'Reading sensitive file {Path(path).name} may expose credentials.')
    if tool_name == 'Grep':
        path = _first_value(tool_input, ('path',))
        glob = _first_value(tool_input, ('glob',))
        if sensitive_path(path) or (glob and _glob_targets_sensitive(glob)):
            target = Path(path).name if sensitive_path(path) else glob
            return _sensitive(f'Searching sensitive file {target} may expose credentials.')
    return ALLOW
