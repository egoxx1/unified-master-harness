# Changelog

## 4.2.1 — 2026-10-11

- `dev-ui-verify` now applies to any change in how the UI looks or behaves, scaled to the change: a
  one-line style fix gets one screenshot, not the full checklist. Text-only copy edits are excluded.
- Skill-routing eval: 12 cases (added `small-color`, `copy-error-message`). Cases where the agent ends
  without its final answer line are reported as `NOANS` instead of a routing failure.
- `codex_hook_probe.py`: checks that the real Codex CLI runs the PreToolUse hook, using a local
  stand-in model (no account or usage), with a `--control` run that must fail.
- `install/apply.py` and `install/INSTALLATION-PROMPT.md`: install into new or existing repositories;
  existing agent configuration is merged, never overwritten.
- Stop-hook warning is now in English. `bootstrap_project.py` reads `pyproject.toml` on Python 3.10.
- `AGENTS.md` rewritten from 117 to 49 lines with the same rules (about 900 fewer input tokens per
  turn); Claude Code routing eval still 12/12.
- `dev-verify` now triggers for any code, config or schema change, including refactors and
  performance work meant to keep behavior the same (found by the Antigravity eval: an index
  optimization was judged "not behavior-changing" and left unverified).
- `AGENTS.md`: new rules for dependencies (add one only when needed; ask before a new runtime
  dependency) and regression tests (a bug fix in a repository with tests adds a test that fails before
  and passes after). §8 now says to ask before planning or starting work that needs approval, and that
  "don't ask me" is not approval (fixed a case that failed in 2 of 6 repeated runs).
- `bench/`: with/without-harness efficiency benchmark on Claude Code; results in `docs/BENCHMARK.md`.
- Public release files: README (English, Korean), MIT license, contributing and security guides,
  verification report.

## 4.2.0 — 2026-10-10

Claude Code layer: secret-file `Read` deny rules (merged into the sandbox), loose sandbox (writes
limited to the project, temp and package caches; network open; no unsandboxed retry), harness
self-protection (edit asks, shell write denied), Stop warning after unverified edits, PreCompact
snapshot re-injected on SessionStart, `dev-reviewer` subagent, `/harness-check`, `/retro`, `/smoke`.
Shared policy gained a `harness` kind (shell writes to harness files are denied on Codex and
Antigravity). A user-level copy of the hooks defers to an equal-or-newer project copy.

## 4.1.0 — 2026-10-10

Secret-free hook log and Growth Engine ingestion, `doctor.py` (read-only settings audit),
`.codex/config.toml` (workspace-write sandbox), `provider_smoke.py`, `run_evals.py`,
`upgrade_harness.py` with `HARNESS-MANIFEST.json`, pre-commit secret block, CI workflow.

## 4.0.2 — 2026-10-10

Blocks deleting home or system roots by absolute path, and work-discarding git commands
(`checkout -- .`, `restore .`, `switch --discard-changes`, `stash clear/drop`).

## 4.0.1 — 2026-10-10

Policy hardening: shell wrappers (`sh -c`, `eval`, `sudo`, `xargs`, `env`, ...), git global options,
more secret files and secret-exfiltration commands, database destruction as an external action,
one push/publish boundary for all providers, fail-closed Antigravity hook lookup, no bytecode writes.
