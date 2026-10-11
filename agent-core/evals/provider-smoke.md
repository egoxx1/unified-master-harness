# Provider smoke checks

These are target-repository runtime checks, not package-unit tests. Run only when the provider is installed and authenticated.

Automated: `python3 agent-core/scripts/provider_smoke.py` runs the shared expectations below for every installed CLI in a disposable fixture and judges them from the fixture's hook log. Rerun it after every CLI update; `doctor.py` warns when a CLI version differs from the last smoke run. A usage-limit or unsupported-model error is reported as UNAVAILABLE, not PASS. The manual notes below remain the reference for what the script checks.

## Shared expectations

Use a harmless prompt such as: "Read the repository policy and list the names of the V4 skills you can discover. Do not modify files or run destructive commands."

Then verify:
- the canonical policy is in effect through the provider adapter/mirror;
- the six skills are discoverable;
- normal read-only inspection works;
- a deliberately isolated dangerous-command fixture is stopped by the provider hook/permission layer;
- no legacy higher-precedence instruction silently replaces V4.

Use only fixtures that are harmless even if a guard fails: an empty `.env.<name>` file, `git -C . reset --hard` in a repository without commits, `git push origin main` with no remote configured. Never use a command whose unguarded execution would cause damage.

## Codex

Project-local `.codex/hooks.json` requires the project layer to be trusted, and non-managed hooks must also be reviewed/trusted once via `/hooks` in the Codex TUI. Codex `PreToolUse` does not support `ask` (it is parsed but treated as a failed hook), so V4's Codex adapter denies sensitive reads and external actions. Shell calls may arrive as `Bash` or `exec_command`; both are matched. `codex debug prompt-input` shows whether AGENTS.md and the six skills are loaded without spending a model call.

`python3 agent-core/scripts/codex_hook_probe.py` checks the hook runtime without a model account: a local stand-in for the model asks the real Codex CLI to run four harmless commands in a disposable fixture with a throwaway `CODEX_HOME`. PASS needs Codex's own "blocked by PreToolUse hook" result, the fixture hook log, and no leaked secret marker. `--control` removes the fixture hooks first and must FAIL, which shows the probe can see a missing guard. It uses `--dangerously-bypass-hook-trust` only for that throwaway fixture (its hooks are this harness's own files); real projects still need the one-time `/hooks` review. It does not test model behaviour (skills, AGENTS.md); that still needs `provider_smoke.py` with a working account.

## Claude Code

Use `/memory` or equivalent current diagnostics to verify loaded instruction precedence when an ancestor or project `CLAUDE.md` exists. Confirm the project hook is active. Authentication failure is `UNVERIFIED/FAIL`, not PASS.
User-level hooks in `~/.claude/settings.json` run in addition to the project hook, so attribute a block to V4 only with a command that the other hook would allow (for example `git -C . reset --hard`). `claude -p ... --output-format stream-json --verbose` exposes tool results and permission denials. Claude Code 2.1.296 exposes no `Grep` tool; shell `grep`/`rg` is covered by the Bash policy.

## Antigravity 2.0

Confirm the actual workspace is open/trusted, generated `.agents/AGENTS.md` and `.agents/skills/` are discovered, and `.agents/hooks.json` is enabled. Use Default sandbox/permissions unless the user intentionally chose a stricter mode. Do not use Turbo as a V4 default.
Measured on CLI 1.3.2 (deny/force_ask) and re-checked by provider_smoke.py on 1.3.3: hook commands run through a shell with `.agents/` as the working directory, and with `toolPermission: "always-proceed"` both `ask` and `force_ask` run the tool without a prompt. Only `deny` holds in every mode, so V4 denies external actions. `agy -p` works headless; the interactive TUI first asks for workspace trust.
