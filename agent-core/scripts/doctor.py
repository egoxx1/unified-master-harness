#!/usr/bin/env python3
"""Read-only check for settings outside the repository that weaken the V4 harness.

The harness can only enforce what the providers let it enforce. User-level settings
(auto-approve modes, blanket allow rules, other global hooks, disabled sandboxes) and
repository state (tracked secret files) decide how much of that protection is real.
This script reports them; it never changes anything and never prints secret values.

Exit code: 0 normally; with --strict, 1 when any RISK finding exists.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'agent-core/hooks'))
from policy import sensitive_path  # noqa: E402

LEVELS = {'OK': 0, 'INFO': 1, 'WARN': 2, 'RISK': 3}


@dataclass
class Finding:
    level: str
    area: str
    message: str
    fix: str = ''


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def load_toml(path: Path) -> dict:
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(path.read_text(encoding='utf-8'))
    except ModuleNotFoundError:
        data: dict = {}
        section = data
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.split('#', 1)[0].strip()
            header = re.fullmatch(r'\[(.+)\]', line)
            if header:
                section = data
                for part in re.findall(r'"[^"]*"|[^.]+', header.group(1)):
                    section = section.setdefault(part.strip('"'), {})
                continue
            pair = re.fullmatch(r'([A-Za-z0-9_.-]+)\s*=\s*(.+)', line)
            if pair:
                value = pair.group(2).strip()
                section[pair.group(1)] = {'true': True, 'false': False}.get(value, value.strip('"'))
        return data
    except Exception:
        return {}


def git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(['git', *args], cwd=repo, text=True, capture_output=True, timeout=10).stdout
    except Exception:
        return ''


def version_of(cmd: list[str]) -> str:
    if not shutil.which(cmd[0]):
        return ''
    try:
        out = subprocess.run(cmd, text=True, capture_output=True, timeout=15)
        return (out.stdout or out.stderr).strip().splitlines()[0][:80] if (out.stdout or out.stderr).strip() else ''
    except Exception:
        return ''


def policy_version(policy_file: Path) -> tuple[int, ...]:
    try:
        match = re.search(r"^POLICY_VERSION\s*=\s*['\"](\d+(?:\.\d+)*)['\"]", policy_file.read_text(encoding='utf-8'), re.M)
    except OSError:
        return ()
    return tuple(int(x) for x in match.group(1).split('.')) if match else ()


PROVIDER_VERSION_CMDS = {'claude': ['claude', '--version'], 'codex': ['codex', '--version'], 'antigravity': ['agy', '--version']}


# --------------------------------------------------------------------------- checks

def check_claude(home: Path, repo: Path) -> list[Finding]:
    path = home / '.claude/settings.json'
    data = load_json(path)
    if data is None:
        return [Finding('INFO', 'claude', f'No readable user settings at {path}.')]
    out: list[Finding] = []
    perms = data.get('permissions') or {}
    if perms.get('defaultMode') == 'bypassPermissions':
        out.append(Finding('RISK', 'claude', 'User defaultMode is bypassPermissions: Claude Code never prompts.',
                           'Use "default" or "acceptEdits"; set permissions.disableBypassPermissionsMode = "disable".'))
    allow = perms.get('allow') or []
    if any(rule in ('Bash', 'Bash(*)', 'Bash(* *)') for rule in allow):
        out.append(Finding('WARN', 'claude', 'User settings allow every Bash command (Bash / Bash(*)).',
                           'V4 project ask rules and hooks still prompt for push/publish (verified on 2.1.296), '
                           'but everything else runs unprompted. Prefer narrower allow rules such as Bash(npm run *).'))
    if data.get('skipDangerousModePermissionPrompt'):
        out.append(Finding('WARN', 'claude', 'skipDangerousModePermissionPrompt is enabled.', 'Remove it from user settings.'))
    own = policy_version(ROOT / 'agent-core/hooks/policy.py')
    for group in (data.get('hooks') or {}).get('PreToolUse', []) or []:
        for hook in group.get('hooks', []) or []:
            command = str(hook.get('command', ''))
            match = re.search(r'([^\s"\']*agent-core)/hooks/', command.replace('$HOME', str(home)).replace('~', str(home)))
            if not match:
                continue
            other = Path(match.group(1))
            if other.resolve() == (ROOT / 'agent-core').resolve():
                continue
            theirs = policy_version(other / 'hooks/policy.py')
            if theirs and own and theirs >= own:
                out.append(Finding('INFO', 'claude', f'A user-level hook runs a global harness copy ({other}/hooks, policy {".".join(map(str, theirs))}); '
                                   'it defers to this project\'s own hooks and keeps guarding folders without a harness.'))
            else:
                shown = '.'.join(map(str, theirs)) if theirs else 'pre-4.2 (no POLICY_VERSION)'
                out.append(Finding('WARN', 'claude', f'A user-level PreToolUse hook runs an older harness copy ({other}/hooks, policy {shown}) in every project.',
                                   'Both hooks run; the stricter answer wins. Back up that folder, copy agent-core/hooks/{policy,hook_log,scope}.py from this template into it, and diff each *_pretool.py before replacing it: a local copy may carry its own rules.'))
    if not out:
        out.append(Finding('OK', 'claude', 'No user-level Claude Code setting weakens the project hooks.'))
    return out


def _project_trust(projects: dict, repo: Path) -> str:
    best, best_len = '', -1
    for key, value in (projects or {}).items():
        try:
            path = Path(key).expanduser().resolve()
        except Exception:
            continue
        if (repo == path or path in repo.parents) and len(str(path)) > best_len and isinstance(value, dict):
            best, best_len = str(value.get('trust_level', '')), len(str(path))
    return best


def _codex_trusted_hook_groups(cfg: dict, repo: Path) -> set[int]:
    """PreToolUse group indexes of this repo's .codex/hooks.json that Codex has a trust record for.

    Codex stores trust under [hooks.state."<path>:pre_tool_use:<group>:<handler>"] with the hash of the
    matcher and handler. A record whose hash no longer matches counts here but is shown as "Modified"
    in /hooks and does not run; doctor cannot recompute Codex's hash.
    """
    target = (repo / '.codex/hooks.json').resolve()
    found: set[int] = set()
    for key, value in (((cfg.get('hooks') or {}).get('state')) or {}).items():
        match = re.fullmatch(r'(.+):pre_tool_use:(\d+):0', str(key).strip('"'))
        if not match or not isinstance(value, dict) or not value.get('trusted_hash') or value.get('enabled') is False:
            continue
        try:
            if Path(match.group(1)).expanduser().resolve() == target:
                found.add(int(match.group(2)))
        except Exception:
            continue
    return found


def check_codex(home: Path, repo: Path) -> list[Finding]:
    path = home / '.codex/config.toml'
    if not path.exists():
        return [Finding('INFO', 'codex', f'No user config at {path}.')]
    cfg = load_toml(path)
    project_cfg = load_toml(repo / '.codex/config.toml') if (repo / '.codex/config.toml').exists() else {}
    trust = _project_trust(cfg.get('projects', {}), repo)
    out: list[Finding] = []
    if trust != 'trusted':
        out.append(Finding('WARN', 'codex', 'This repository is not trusted in Codex, so .codex/hooks.json and .codex/config.toml are ignored.',
                           'Open Codex here once, trust the project, then review/trust the V4 hook with /hooks.'))
    else:
        hooks = load_json(repo / '.codex/hooks.json') or {}
        groups = ((hooks.get('hooks') or {}).get('PreToolUse')) or []
        trusted = _codex_trusted_hook_groups(cfg, repo)
        missing = [g.get('matcher', '?') for i, g in enumerate(groups) if isinstance(g, dict) and i not in trusted]
        if groups and missing:
            out.append(Finding('WARN', 'codex', 'Codex has not trusted these V4 hooks, so they do not run: ' + ', '.join(missing) + '.',
                               'Open Codex in this project, run /hooks and review the V4 hooks (needed again after an upgrade adds a hook).'))
        else:
            out.append(Finding('INFO', 'codex', 'Project is trusted and every V4 hook has a trust record. If /hooks shows one as '
                               '"Modified", review it again: Codex skips modified hooks.'))
    if (cfg.get('features') or {}).get('hooks') is False or (cfg.get('features') or {}).get('codex_hooks') is False:
        out.append(Finding('RISK', 'codex', 'Hooks are disabled in [features]; the V4 safety hook never runs.', 'Remove hooks = false.'))
    user_open = cfg.get('approval_policy') == 'never' and cfg.get('sandbox_mode') == 'danger-full-access'
    project_sandbox = project_cfg.get('sandbox_mode')
    if user_open and trust == 'trusted' and project_sandbox and project_sandbox != 'danger-full-access':
        out.append(Finding('INFO', 'codex', f'User default is approval_policy=never + danger-full-access, but this project overrides it with sandbox_mode={project_sandbox}.'))
    elif user_open:
        out.append(Finding('RISK', 'codex', 'approval_policy=never with sandbox_mode=danger-full-access: the hook is the only guard and Codex hooks cannot ask.',
                           'Trust this project so its .codex/config.toml (workspace-write, on-request) applies, or change the user default.'))
    if not out:
        out.append(Finding('OK', 'codex', 'Codex settings look compatible with V4.'))
    return out


def check_antigravity(home: Path, repo: Path) -> list[Finding]:
    path = home / '.gemini/antigravity-cli/settings.json'
    data = load_json(path)
    if data is None:
        return [Finding('INFO', 'antigravity', f'No readable CLI settings at {path}.')]
    out: list[Finding] = []
    if data.get('toolPermission') == 'always-proceed':
        out.append(Finding('WARN', 'antigravity', 'toolPermission is "always-proceed": ask/force_ask hook decisions run without a prompt (measured on CLI 1.3.2).',
                           'V4 already denies external actions there. For prompts on other commands, switch toolPermission to the default/ask mode.'))
    trusted = [str(x) for x in (data.get('trustedWorkspaces') or [])]
    if trusted and not any(Path(t).expanduser() in (repo, *repo.parents) for t in trusted):
        out.append(Finding('INFO', 'antigravity', 'This repository is not in trustedWorkspaces yet; the interactive CLI will ask once.'))
    global_hooks = home / '.gemini/config/hooks.json'
    if global_hooks.exists():
        names = list((load_json(global_hooks) or {}).keys())
        out.append(Finding('INFO', 'antigravity', f'Global Antigravity hooks also run: {", ".join(names) or "(none named)"}.'))
    if not out:
        out.append(Finding('OK', 'antigravity', 'Antigravity CLI settings look compatible with V4.'))
    return out


def check_repo(repo: Path) -> list[Finding]:
    out: list[Finding] = []
    if not (repo / '.git').exists():
        return [Finding('INFO', 'repo', 'Not a git repository; tracked-secret and branch checks skipped.')]
    tracked = [f for f in git(repo, 'ls-files').splitlines() if sensitive_path(f)]
    if tracked:
        out.append(Finding('RISK', 'repo', f'Sensitive-looking files are tracked by git: {", ".join(tracked[:10])}.',
                           'Remove them from the index (git rm --cached), rotate any exposed secret, and add them to .gitignore.'))
    candidates = [p for p in repo.iterdir() if p.is_file() and sensitive_path(p.name)]
    unignored = [p.name for p in candidates if not git(repo, 'check-ignore', p.name).strip()]
    if unignored:
        out.append(Finding('WARN', 'repo', f'Sensitive-looking files are not gitignored: {", ".join(unignored)}.', 'Add them to .gitignore.'))
    hook = repo / '.git/hooks/pre-commit'
    if not hook.exists() or 'precommit_check.py' not in hook.read_text(errors='ignore'):
        out.append(Finding('INFO', 'repo', 'The V4 pre-commit check is not installed.', 'python3 agent-core/scripts/install_git_hooks.py'))
    if not out:
        out.append(Finding('OK', 'repo', 'No tracked or unignored secret files; pre-commit check installed.'))
    return out


def check_github(repo: Path) -> list[Finding]:
    if not shutil.which('gh'):
        return [Finding('INFO', 'github', 'gh CLI not found; branch protection not checked.')]
    remote = git(repo, 'remote', 'get-url', 'origin').strip()
    match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', remote)
    if not match:
        return [Finding('INFO', 'github', 'No GitHub origin remote; branch protection not checked.')]
    owner, name = match.groups()
    try:
        default = subprocess.run(['gh', 'api', f'repos/{owner}/{name}', '--jq', '.default_branch'], text=True, capture_output=True, timeout=20).stdout.strip() or 'main'
        prot = subprocess.run(['gh', 'api', f'repos/{owner}/{name}/branches/{default}/protection'], text=True, capture_output=True, timeout=20)
    except Exception as exc:
        return [Finding('INFO', 'github', f'Could not query GitHub: {exc}')]
    if prot.returncode != 0:
        return [Finding('WARN', 'github', f'{default} has no branch protection (or it is not readable): an agent push lands directly on {default}.',
                        'Require pull requests and passing CI for the default branch.')]
    return [Finding('OK', 'github', f'{default} is protected.')]


def check_versions(repo: Path) -> list[Finding]:
    record = load_json(repo / '.agent-state/provider-versions.json') or {}
    out: list[Finding] = []
    for provider, cmd in PROVIDER_VERSION_CMDS.items():
        current = version_of(cmd)
        if not current:
            continue
        previous = (record.get(provider) or {}).get('version')
        if not previous:
            out.append(Finding('INFO', 'versions', f'{provider} {current}: never smoke-tested in this repository.',
                               'python3 agent-core/scripts/provider_smoke.py'))
        elif previous != current:
            out.append(Finding('WARN', 'versions', f'{provider} changed since the last smoke test ({previous} -> {current}); hook behaviour may have changed.',
                               'python3 agent-core/scripts/provider_smoke.py'))
        else:
            result = (record.get(provider) or {}).get('result', 'unknown')
            out.append(Finding('OK' if result == 'PASS' else 'WARN', 'versions', f'{provider} {current}: last smoke result {result}.'))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--repo', default=str(ROOT))
    ap.add_argument('--home', default=str(Path.home()))
    ap.add_argument('--repo-only', action='store_true', help='only repository checks (CI)')
    ap.add_argument('--github', action='store_true', help='also query GitHub branch protection via gh')
    ap.add_argument('--no-versions', action='store_true', help='skip running provider --version commands')
    ap.add_argument('--strict', action='store_true', help='exit 1 when any RISK finding exists')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    repo, home = Path(args.repo).resolve(), Path(args.home)

    findings = check_repo(repo)
    if not args.repo_only:
        findings += check_claude(home, repo) + check_codex(home, repo) + check_antigravity(home, repo)
        if not args.no_versions:
            findings += check_versions(repo)
    if args.github:
        findings += check_github(repo)

    if args.json:
        print(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in sorted(findings, key=lambda f: -LEVELS[f.level]):
            print(f'[{f.level:4}] {f.area:11} {f.message}')
            if f.fix and f.level != 'OK':
                print(f'{"":19}fix: {f.fix}')
        counts = {lvl: sum(f.level == lvl for f in findings) for lvl in LEVELS}
        print('Summary: ' + ', '.join(f'{k} {v}' for k, v in counts.items() if v))
    return 1 if args.strict and any(f.level == 'RISK' for f in findings) else 0


if __name__ == '__main__':
    raise SystemExit(main())
