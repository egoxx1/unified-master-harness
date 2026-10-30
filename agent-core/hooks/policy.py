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
import posixpath
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY_VERSION = '4.3.2'  # read by scope.py so a global copy can defer to an equal-or-newer project copy

SAFE_ENV_NAMES = {'.env.example', '.env.sample', '.env.template', '.env.defaults'}
SENSITIVE_BASENAMES = {
    'id_rsa', 'id_ed25519', 'id_ecdsa', 'id_dsa', 'credentials', 'credentials.json',
    'service-account.json', 'service_account.json', '.npmrc', '.pypirc',
    '.envrc', '.netrc', '_netrc', '.pgpass', '.git-credentials', '.dockercfg', 'kubeconfig',
}
SENSITIVE_PATH_SUFFIXES = ('.kube/config', '.docker/config.json', '.config/gh/hosts.yml')
SENSITIVE_SUFFIXES = ('.pem', '.key', '.p12', '.pfx')

# Programs that only test/list a path or load it into the shell without printing it.
PATH_META_PROGRAMS = {'ls', 'test', '[', '[[', 'stat'}  # `source`/`.` load the file's contents, so they are not here
# A variable whose name says it holds a credential; printing it shows the secret even when no file is named.
SECRET_VARIABLE = re.compile(r'\$\{?[A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY|ACCESS_?KEY|CREDENTIAL)[A-Za-z0-9_]*', re.I)
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
# File headers of a Codex apply_patch body ("*** Update File: path", "*** Move to: path", ...).
PATCH_FILE_HEADER = re.compile(r'^\s*\*\*\*\s*(?:(?:Add|Update|Delete)\s+File|Move\s+to)\s*:\s*(.+?)\s*$', re.M)
# Codex runs these itself when a shell command invokes them (also as `cd dir && apply_patch <<'EOF'`).
APPLY_PATCH_CALL = re.compile(r'(?:^|[\s;&|(\'"])(?:apply_patch|applypatch)(?=$|[\s<\'"])', re.M)
APPLY_PATCH_CD = re.compile(r'\bcd\s+("[^"]+"|\'[^\']+\'|[^\s;&|]+)\s*&&\s*(?:apply_patch|applypatch)\b')
# Harness enforcement files relative to the repository root (used when the root is known).
HARNESS_ROOTED = re.compile(
    r'(?:AGENTS\.md|CLAUDE\.md|agent-core/hooks/|agent-core/scripts/|agent-core/evals/|agent-core/growth/policy\.json'
    r'|\.codex/|\.agents/|\.claude/settings[^/]*\.json|\.claude/agents/|\.claude/commands/)', re.I)
HEREDOC = re.compile(r'<<-?\s*[\'"]?([A-Za-z_][\w-]*)[\'"]?')
# Programs that read further commands from stdin when started without a command or script.
REPLS = {'node', 'nodejs'}
PYTHON = re.compile(r'python(?:3(?:\.\d+)?)?')
RUNNERS = {'uv', 'poetry', 'pipenv', 'pdm', 'hatch'}  # `uv run python` starts the same REPL
SESSION_VALUE_FLAGS = {'bash': {'-o', '+o', '-O', '+O'}, 'zsh': {'-o', '+o'}, 'sh': {'-o', '+o'},
                       'python': {'-W', '-X', '-Q'},
                       'redis-cli': {'-h', '-p', '-a', '-n', '-u', '--user', '--pass', '-s'},
                       'sqlite3': {'-cmd', '-separator', '-newline', '-nullvalue'},
                       'tmux': {'-L', '-S', '-f', '-c', '-T'}, 'screen': {'-S', '-c', '-e', '-p', '-t'},
                       'irb': {'-r', '-I'}, 'ghci': {'-i', '-package'},
                       'ssh': {'-B', '-b', '-c', '-D', '-E', '-e', '-F', '-I', '-i', '-J', '-L', '-l', '-m', '-O', '-o',
                               '-p', '-Q', '-R', '-S', '-W', '-w'}}
# REPLs that take their code inline with these flags; without them (and without a script) they wait for input.
REPL_INLINE = {'lua': {'-e'}, 'julia': {'-e', '-E', '--eval', '--print'}, 'R': {'-e', '-f', '--file'},
               'mysqlsh': {'-e', '--execute', '-f', '--file'}}
RAILS_CONSOLE = {'console', 'c', 'dbconsole', 'db'}
# Code fetched from the network or decoded at runtime and run at once: the guard never sees what runs.
FETCH_TO_INTERPRETER = re.compile(
    r'\b(?:curl|wget|base64\s+(?:-d|-D|--decode)|xxd\s+-r|openssl\s+(?:base64|enc)\b[^|]*\s-d)\b[^|;&]*\|\s*(?:sudo\s+)?'
    r'(?:sh|bash|zsh|dash|ksh|python(?:3(?:\.\d+)?)?|node|perl|ruby)'
    r'(?:\s+(?!-[cmeEp]\b)-\S*)*(?:\s+--(?:\s[^|;&>]*)?)?\s*(?:\d*>[^|;&]*)?(?:$|[;&|)])')  # runs stdin as code; `python3 -m json.tool` reads data
FETCH_SUBSTITUTION = re.compile(r'(?:\$\(|<\(|`)\s*(?:curl|wget)\b')
INTERPRETER_CALL = re.compile(r'(?:^|[;&|(]\s*)(?:sudo\s+)?(?:sh|bash|zsh|dash|ksh|python(?:3(?:\.\d+)?)?|node|perl|ruby|eval|source|\.)\s')
SSH_NO_SHELL = {'-N', '-W', '-O', '-G', '-Q', '-V'}  # forwarding, control and query modes start no remote shell
INTERACTIVE_MODULES = {'code', 'pdb', 'IPython', 'idlelib', 'asyncio'}
NODE_RUN_FLAGS = {'--test', '--watch', '--run', '--check', '--eval', '--print', '-c'}
RUNNER_VALUE_FLAGS = {'--with', '--python', '-p', '--from', '--project', '--directory', '--package', '--extra',
                      '--group', '--env-file', '--index', '-e', '--env'}
# Database shells read statements from stdin unless the command carries them (flags that do so, per client).
DB_SESSION_INLINE = {
    'psql': {'-c', '--command', '-f', '--file', '-l', '--list'},
    'mysql': {'-e', '--execute'}, 'mariadb': {'-e', '--execute'},
    'sqlite3': {'-cmd'},
    'mongosh': {'--eval', '-f', '--file'}, 'mongo': {'--eval', '-f', '--file'},
    'redis-cli': set(),
}
MULTIPLEXERS = {'tmux', 'screen'}
TMUX_ATTACH = {'new', 'new-session', 'attach', 'attach-session', 'a', 'at'}
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
    shell_dump = re.search(r'(^|[;&|]\s*)(?:(?:env|printenv|export\s+-p)(?:\s|$|[|;&])|set\s*(?:$|[|;&]))', low)  # `set -e` is not a dump
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


def _variable_target(target: str) -> bool:
    """A path whose start comes from a variable or substitution; empty or unset, it can mean `/`."""
    return target.startswith(('$', '`')) and not re.match(r'\$\{?HOME\}?(?:/|$)', target)


def _classify_segment(tokens: list[str], depth: int) -> Verdict:
    original = list(tokens)
    tokens = _unwrap(tokens)
    if not tokens:
        return ALLOW
    program = Path(tokens[0]).name
    text = ' '.join(tokens)
    from_stdin = any(Path(t).name == 'xargs' for t in original[:len(original) - len(tokens)])

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
    if program == 'rm' and any(t == '--recursive' or (t.startswith('-') and not t.startswith('--') and set(t[1:]) & {'r', 'R'})
                               for t in tokens[1:]):
        if from_stdin:
            return Verdict('ask', 'Recursive rm with targets from stdin (xargs) cannot be checked; needs explicit user approval.', 'destructive')
        if any(_variable_target(t) for t in _rm_targets(tokens)):
            return Verdict('ask', 'Recursive rm of a path built from a variable cannot be checked; needs explicit user approval.', 'destructive')
    if program == 'find' and any(t in {'-delete', '-exec', '-execdir', '-ok'} for t in tokens[1:]) \
            and (t := next((a.strip("\"'") for a in tokens[1:] if not a.startswith(('-', '(', '!'))), '')):
        if any(a in {'-delete'} or a in {'rm', '/bin/rm'} for a in tokens[1:]):
            filtered = any(a in {'-name', '-iname', '-path', '-ipath', '-regex', '-iregex', '-wholename', '-newer', '-mtime', '-mmin'}
                           for a in tokens[1:])
            if _catastrophic_target(t) and not (filtered and t.rstrip('/') in {'.', '..'}):
                return _destructive('Blocked find that deletes everything under the current/parent directory, or under a root or home.')
            if _variable_target(t):
                return Verdict('ask', 'find deleting under a path built from a variable needs explicit user approval.', 'destructive')

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

    if program in {'echo', 'printf', 'print'} and any(SECRET_VARIABLE.search(a) for a in original):
        return _sensitive('Printing a credential variable exposes its value.')

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
    if FETCH_TO_INTERPRETER.search(command) or (FETCH_SUBSTITUTION.search(command) and INTERPRETER_CALL.search(command)):
        verdict = _worst(verdict, _external('Running code fetched from the network or decoded at runtime cannot be checked '
                                            'first; download it to a file, read it, then run the file.'))
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


def patch_targets(patch: str) -> list[str]:
    """Paths an apply_patch body adds, updates, deletes or moves to."""
    return [m.strip().strip("\"'") for m in PATCH_FILE_HEADER.findall(patch or '')]


def strip_heredoc_bodies(command: str) -> str:
    """Drop heredoc body lines (data, not commands) and keep the lines that start and end them."""
    kept: list[str] = []
    pending: list[str] = []
    for line in (command or '').splitlines():
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
                kept.append(line)
            continue
        kept.append(line)
        pending.extend(HEREDOC.findall(line))
    return '\n'.join(kept)


def _patch_target_protected(target: str, base: str, root: str) -> bool:
    raw = target.replace('\\', '/')
    if root:
        full = os.path.normpath(os.path.join(root, base, raw))  # an absolute target ignores root and base
        rel = os.path.relpath(full, root).replace('\\', '/')
        if rel == '..' or rel.startswith('../'):
            return False  # outside this repository: not this harness's files
        return bool(HARNESS_ROOTED.match(rel))
    return bool(HARNESS_PROTECTED.search(posixpath.normpath(posixpath.join(base, raw)) if base else posixpath.normpath(raw)))


def _classify_patch(patch: str, base: str = '', root: str = '', require_headers: bool = True) -> Verdict:
    """Harness verdict for an apply_patch body; base is the patch's directory relative to root."""
    if not patch.strip():
        return ALLOW
    targets = patch_targets(patch)
    if not targets:
        if require_headers:
            return _harness('Patch has no recognizable file headers, so its targets cannot be checked.')
        return ALLOW
    for target in targets:
        if _patch_target_protected(target, base, root):
            return _harness(f'Patch edits harness enforcement file {target}, which needs explicit user approval.')
    return ALLOW


def shell_patch(command: str) -> tuple[str, str] | None:
    """(patch text, cd directory) when a shell command runs apply_patch, which Codex applies itself."""
    if not command or not APPLY_PATCH_CALL.search(command):
        return None
    cd = APPLY_PATCH_CD.search(command)
    return command, (cd.group(1).strip("\"'") if cd else '')


def _session_segments(command: str) -> list[tuple[list[str], bool]]:
    """(tokens, stdin_given) per simple command, respecting quotes; heredoc bodies are skipped."""
    lexer = shlex.shlex(strip_heredoc_bodies(command), posix=True, punctuation_chars=';&|<>()\n')
    lexer.whitespace = ' \t\r'
    lexer.whitespace_split = True
    tokens = list(lexer)
    segments: list[tuple[list[str], bool]] = []
    current: list[str] = []
    stdin_given = skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token and set(token) <= set(';&|<>()\n'):
            if '<' in token or '>' in token:  # a redirection, not a separator
                stdin_given = stdin_given or '<' in token
                if current and current[-1].isdigit():
                    current.pop()  # file descriptor of 2>&1
                skip_next = True
                continue
            if current:
                segments.append((current, stdin_given))
            current, stdin_given = [], token in ('|', '|&')
            continue
        current.append(token)
    if current:
        segments.append((current, stdin_given))
    return segments


def interactive_session(command: str, depth: int = 0) -> str:
    """Name of a shell or REPL the command starts with no command of its own, if any.

    Such a session takes its real commands later from stdin. On Codex those writes
    (write_stdin) never reach a PreToolUse hook, so the session itself is the last point
    a guard can see. A session whose stdin is given inside the command (piped into it,
    heredoc or redirect) is visible to the guard already and is not interactive.
    """
    if depth > MAX_DEPTH:
        return ''
    try:
        segments = _session_segments(command or '')
    except ValueError:
        return ''
    for tokens, stdin_given in segments:
        tokens = [t for t in tokens if t not in ('{', '}')]
        tokens = _unwrap(tokens)
        if tokens and tokens[0] == 'exec':
            tokens = _unwrap(tokens[1:])
        if len(tokens) > 2 and Path(tokens[0]).name == 'bundle' and tokens[1] == 'exec':
            tokens = tokens[2:]
        while len(tokens) > 1 and Path(tokens[0]).name in RUNNERS and tokens[1] == 'run':
            rest = tokens[2:]
            while rest and rest[0].startswith('-'):
                flag = rest.pop(0)
                if flag in RUNNER_VALUE_FLAGS and rest:
                    rest.pop(0)
            tokens = _unwrap(rest)
        if not tokens or stdin_given:
            continue
        program, args = Path(tokens[0]).name, tokens[1:]
        if any(a in {'--version', '--help'} for a in args):
            continue
        value_flags = SESSION_VALUE_FLAGS.get('python' if PYTHON.fullmatch(program) else program, set())
        flags, positional, skip = [], [], False
        for arg in args:
            if skip:
                skip = False
            elif arg.startswith(('-', '+')) and arg not in ('-', '+'):
                flags.append(arg)
                skip = arg in value_flags
            elif arg != '-':  # '-' means "script from stdin", which is not a script
                positional.append(arg)
        short = ''.join(f[1:] for f in flags if not f.startswith('--'))
        if program in SHELLS:
            if 'c' in short:
                inner = args[next(i for i, a in enumerate(args) if a.startswith('-') and not a.startswith('--') and 'c' in a[1:]) + 1:]
                found = interactive_session(inner[0], depth + 1) if inner else ''
                if found:
                    return found
            elif not positional or 's' in short or 'i' in short:
                return program
        elif PYTHON.fullmatch(program) or program == 'ipython':
            if 'V' in short:
                continue
            if 'i' in short:
                return program
            if 'm' in short:
                module = args[args.index(next(f for f in flags if 'm' in f[1:])) + 1:][:1]
                if module and module[0] in INTERACTIVE_MODULES:
                    return f'{program} -m {module[0]}'
                continue
            if 'c' not in short and not positional:
                return program
        elif program in REPLS:
            if 'v' in short:
                continue
            runs = any(f.split('=', 1)[0] in NODE_RUN_FLAGS for f in flags) or any(f in {'-e', '-p'} for f in flags)
            if '-i' in flags or '--interactive' in flags or (not runs and not positional):
                return program
        elif program in DB_SESSION_INLINE:
            inline = DB_SESSION_INLINE[program]
            names = {f.split('=', 1)[0] for f in flags}
            if names & inline or (program == 'sqlite3' and len(positional) >= 2) \
                    or (program in ('mongosh', 'mongo') and any(a.endswith('.js') for a in positional)) \
                    or (program == 'redis-cli' and positional):
                continue
            return program
        elif program in REPL_INLINE:
            if {f.split('=', 1)[0] for f in flags} & REPL_INLINE[program]:
                continue
            if (positional and program != 'R') or positional[:1] == ['CMD']:
                continue
            return program
        elif program == 'php':
            if '-a' in flags:
                return 'php -a'
        elif program == 'rails':
            if positional[:1] and positional[0] in RAILS_CONSOLE:
                return f'rails {positional[0]}'
        elif program == 'sqlplus':
            if not any(a.startswith('@') for a in args):
                return program
        elif program == 'gdb':
            if not {'-batch', '--batch'} & set(flags):
                return program
        elif program == 'irb':
            if not positional:
                return program
        elif program == 'ghci':
            if '-e' not in flags:  # `ghci File.hs` loads the file, then still waits for input
                return program
        elif program == 'ssh':
            i = 0
            while i < len(args) and args[i].startswith('-'):
                i += 2 if args[i] in SESSION_VALUE_FLAGS['ssh'] else 1
            if {a[:2] for a in args[:i] if a.startswith('-')} & SSH_NO_SHELL:
                continue
            remote = args[i + 1:]  # ssh joins the words after the host into one remote command
            if not remote:
                return 'ssh'
            found = interactive_session(' '.join(remote), depth + 1)
            if found:
                return f'ssh {found}'
        elif program in MULTIPLEXERS:
            sub = positional[0] if positional else ''
            if program == 'tmux' and (not sub or sub in TMUX_ATTACH) and '-d' not in flags:
                return program
            if program == 'screen' and not any(f.startswith('-d') or f in {'-ls', '-list', '-Q'} for f in flags):
                return program
    return ''


def _glob_targets_sensitive(pattern: str) -> bool:
    probes = ('.env', '.env.local', '.env.production', 'id_rsa', 'server.pem', 'private.key', '.netrc', '.envrc')
    return any(fnmatch.fnmatch(probe, pattern) and sensitive_path(probe) for probe in probes) or sensitive_path(pattern)


def _relative_base(cwd: str | None, root: str | None) -> str:
    if not cwd or not root:
        return ''
    try:
        rel = os.path.relpath(os.path.realpath(cwd), os.path.realpath(root)).replace('\\', '/')
    except ValueError:
        return ''
    return '' if rel == '.' or rel.startswith('..') else rel


def classify_generic(tool_name: str, tool_input: dict[str, Any], cwd: str | None = None, root: str | None = None) -> Verdict:
    """cwd and root (the repository the hooks belong to) anchor patch paths when the provider gives them."""
    tool_input = tool_input or {}
    if isinstance(tool_input, str):
        tool_input = {'command': tool_input}
    if not isinstance(tool_input, dict):
        return _sensitive(f'{tool_name} input has an unexpected shape and cannot be checked.')
    base = _relative_base(cwd, root)
    if tool_name == 'apply_patch':
        return _classify_patch(_first_value(tool_input, ('command', 'patch', 'input')), base, root or '')
    if tool_name in {'Bash', 'PowerShell', 'run_command', 'execute_command', 'exec_command', 'shell', 'local_shell'}:
        command = _first_value(tool_input, ('command', 'CommandLine', 'cmd', 'script'))
        verdict = classify_command(command)
        routed = shell_patch(command)
        if routed and verdict.action != 'deny':
            patch, cd = routed
            verdict = _worst(verdict, _classify_patch(patch, posixpath.join(base, cd) if cd else base, root or '', require_headers=False))
        return verdict
    if tool_name in {'Read', 'view_file', 'read_file'}:
        path = _first_value(tool_input, ('file_path', 'path', 'AbsolutePath', 'TargetFile', 'Path'))  # Path: Antigravity 1.4 read_file
        if sensitive_path(path):
            return _sensitive(f'Reading sensitive file {Path(path).name} may expose credentials.')
    if tool_name in {'edit_file', 'write_file'}:  # Antigravity 1.4 file edits: {Path, Target, Replacement} / {Path, Content}
        path = _first_value(tool_input, ('Path', 'TargetFile', 'file_path', 'path'))
        if path and _patch_target_protected(path, base, root or ''):
            return _harness(f'Editing harness enforcement file {Path(path).name} needs explicit user approval.')
        if sensitive_path(path):
            return _sensitive(f'Writing sensitive file {Path(path).name} needs explicit user approval.')
    if tool_name == 'Grep':
        path = _first_value(tool_input, ('path',))
        glob = _first_value(tool_input, ('glob',))
        if sensitive_path(path) or (glob and _glob_targets_sensitive(glob)):
            target = Path(path).name if sensitive_path(path) else glob
            return _sensitive(f'Searching sensitive file {target} may expose credentials.')
    return ALLOW
