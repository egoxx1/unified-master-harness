# Agent Development Environment V4 Architecture

## Design goal

Make a strong coding agent behave like a disciplined software engineer without turning every task into a multi-agent ceremony.

## Authority layers

- `PROJECT.md`: what the product is and what good means.
- `AGENTS.md`: durable cross-provider work policy.
- `.agents/skills/`: on-demand procedures.
- `agent-core/project/profile.*`: stable repository facts supported by evidence.
- scripts: deterministic repeated mechanics.
- hooks/permissions/sandbox: hard safety enforcement.
- `.agent-state/`: minimal long-task state only.
- Growth Engine: controlled harness evolution.

## Provider architecture

The providers are adapters around the same policy, not separate competing policy systems.

- Codex: root `AGENTS.md` + repo skills + `.codex/hooks.json`.
- Claude Code: root `CLAUDE.md` is a thin `@AGENTS.md` import adapter; `.claude/skills/` mirrors canonical skills; `.claude/settings.json` supplies provider-specific hook/memory settings. Existing ancestor/local Claude instructions must be audited during installation.
- Antigravity 2.0: generated `.agents/AGENTS.md` mirror + `.agents/skills/` + `.agents/hooks.json`. No provider-specific workflow is required by V4.

## Safety architecture

`agent-core/hooks/policy.py` classifies dangerous commands, sensitive reads and external actions. Provider adapters translate that decision into each runtime's supported hook contract. This avoids pretending every provider supports the same `ask/deny` semantics.

Each verdict carries a `kind`, and adapters map it as follows (measured on 2026-10-10):

| kind | Example | Claude Code | Codex | Antigravity |
|---|---|---|---|---|
| destructive | `git reset --hard`, `git checkout -- .`, `git restore .`, `git stash clear/drop`, `rm -rf ~/` or `/Users/<name>` or system roots, force push, env dump | deny | deny | deny |
| sensitive | reading/copying `.env*`, keys, `.netrc`, kube config | ask | deny (hooks cannot ask) | deny |
| external | `git push`, publish, deploy, prod DB drop, mutating `curl` | ask (+ `permissions.ask` rules) | deny (hooks cannot ask) | deny (`force_ask` is auto-approved under `toolPermission: always-proceed`) |
| harness | shell writes to `AGENTS.md`, `CLAUDE.md`, `agent-core/{hooks,scripts,evals}`, `.codex`, `.agents`, `.claude/settings*` | ask (also blocked at OS level by the sandbox) | deny | deny |
| other | ordinary dev commands | no output (normal permission flow) | no output | allow only for a small read-only/dev-check list, otherwise ask |

The policy unwraps `sh/bash/zsh -c`, `eval`, `sudo`, `timeout`, `xargs`, `env` and leading `VAR=` assignments, and skips git global options (`-C`, `-c`, `--git-dir`, ...) before matching.

The guard is deliberately narrow. It complements provider sandbox/permissions; it is not a complete shell firewall.

## Claude Code layer (primary provider)

Claude Code is the primary provider, so it gets enforcement the others cannot offer. Everything lives in `.claude/` and `agent-core/hooks/claude_session.py`; the shared policy, skills and the other providers are unchanged.

- **Permission rules** (`.claude/settings.json`): `Read` deny for secret files (`.env`, `.env.local`, `.env.*.local`, `.env.production` and the other listed variants, keys, `.netrc`, ...). Claude merges these into the sandbox, so `cat .env` from the shell is blocked by the OS as well. The variants are listed explicitly because `!` carve-outs are not carried into the sandbox (measured on 2.1.296): a broad `.env.*` rule would make `.env.example` unreadable from the shell. Unlisted variants remain guarded by the hook (ask). `Edit` ask rules for every harness enforcement file. Push/publish ask rules as before.
- **Sandbox, "loose" profile**: shell commands may write only inside the project, the per-user temp dir, `/tmp` and common package caches; the harness enforcement files are write-denied even inside the project; network is open (`allowedDomains: ["*"]`). `allowUnsandboxedCommands: false` closes the retry-outside-the-sandbox escape hatch, which together with a user-level `Bash(*)` allow rule would otherwise bypass the sandbox. `provider_smoke.py` and `run_evals.py` are excluded because they launch other agent CLIs; their files are write-protected, so they cannot be swapped out from the shell.
- **Lifecycle hooks** (`claude_session.py`): PostToolUse records code edits and verification runs per session; Stop warns the user (warning only, never blocks) when code was edited after the last verification; PreCompact saves a snapshot that SessionStart re-injects after compaction; SessionStart also briefs Claude on recent task state and hook decisions. Hooks run outside the sandbox.
- **Fresh-context review**: `.claude/agents/dev-reviewer.md` (read-only tools) carries out `dev-review`.
- **Commands** (`/harness-check`, `/retro`, `/smoke`) are user-invoked only (`disable-model-invocation`) so they never affect skill routing.
- **Global copy**: adapters installed at user level defer to a project's own hooks when its `POLICY_VERSION` is equal or newer (`scope.py`), and keep guarding older projects and folders without a harness.

## Observability and growth input

Every call the shared policy does not allow is appended to `.agent-state/hook-log.jsonl` (gitignored) by `agent-core/hooks/hook_log.py`: provider, tool, decision, kind, reason, a command *shape* (program, plain lowercase subcommand, option names) and a short digest. Argument values, paths and anything that might be a secret are never written. `growth_engine.py ingest-hooks` turns repeated retries and frequent blocks into observations; promotion still follows the Growth Engine and its human gates.

## Verification outside the agent

- `provider_smoke.py`: real CLI runs in a disposable fixture repo with harmless probes; evidence is the fixture's hook log. Results and CLI versions go to `.agent-state/provider-versions.json`.
- `codex_hook_probe.py`: model-free check that the real Codex CLI runs the PreToolUse hook (local stand-in model, throwaway `CODEX_HOME`, negative control with `--control`).
- `run_evals.py`: skill-routing cases against a real CLI (declared + loaded skills).
- `doctor.py`: user-level settings and repository state that weaken the harness (read-only).
- `precommit_check.py` (installed by `install_git_hooks.py`) and `.github/workflows/agent-harness.yml`: checks that run without any agent.
- `.codex/config.toml`: project-level Codex sandbox (`workspace-write`, `on-request`) that overrides unsafe user defaults once the project is trusted.

## Installation model

The package contains no target-project profile. Installation first inspects the target repository, preserves unknown user work, refuses blind overwrites, then generates a profile from explicit evidence. Unknown facts remain unknown.

Upgrades use `upgrade_harness.py`: `agent-core/HARNESS-MANIFEST.json` records the template each project last received, so files the project never touched are updated, project-only edits are kept, and edits on both sides become `<file>.v4-new` conflicts. Generated mirrors are re-synced instead of merged.
