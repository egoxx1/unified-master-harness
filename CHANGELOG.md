# Changelog

## 4.3.0 — 2026-10-30

Codex gaps found by checking the hook against the current Codex source. Unit-tested, reviewed once by a
fresh-context reviewer. On Codex CLI 0.165.0 with a real model: safety smoke 8/8, skill routing 12/12 with
every case passing in 3 of 3 runs.

**Upgrading from 4.2:** open Codex in the project and review the new `apply_patch` hook in `/hooks`.
Codex runs only hooks it has trusted. The existing shell hook is unchanged, so its trust carries over
and all 4.2 protection keeps running; until the new hook is reviewed, edits through `apply_patch` are
unguarded exactly as in 4.2. `doctor.py` warns while a V4 hook has no trust record.

- `apply_patch` is guarded on Codex. Codex edits files with `apply_patch`, which the hook did not match,
  so a Codex agent could rewrite `AGENTS.md` or the hook's own `policy.py`. A second hook group in
  `.codex/hooks.json` now matches `apply_patch` (the shell group is left byte-identical so its trust
  survives the upgrade). The policy reads the patch's file headers and denies edits of harness
  enforcement files (Codex hooks cannot ask); a patch with no readable header is denied.
- Shell-routed patches are checked too: Codex applies `apply_patch <<'EOF' …`, `cd dir && apply_patch …`
  and `bash -lc "apply_patch …"` itself while the hook only sees `Bash`.
- Patch paths are resolved against the event's `cwd` and the repository root, so `hooks/policy.py` from
  inside `agent-core/` is caught, while a nested `packages/web/AGENTS.md` (ordinary Codex guidance) and
  files in other repositories are allowed.
- Bare interactive sessions are denied on Codex. Input sent later through `write_stdin` never reaches a
  PreToolUse hook, so `bash`, `python3`, `python3 -`, `python3 -m pdb`, `node`, `ipython`, `uv run python`
  and the same inside `bash -lc "…"`, `( … )` or `{ …; }` were a way around every check. Commands that
  carry their own input stay allowed: `bash -lc "…"`, scripts, `-c`/`-m`/`-e`, `node --test`, heredocs,
  `… | bash`, `< file`. Other providers check every command and keep allowing these.
- The same rule covers database shells and multiplexers started without inline work (`psql`, `mysql`,
  `sqlite3 db`, `mongosh`, `redis-cli`, `tmux`, `tmux attach`, `screen -r`); `psql -c`, `mysql -e`,
  `sqlite3 db "select …"`, `tmux new -d …` and `screen -dmS …` stay allowed.
- The Codex hook fails closed: unparsable input, a non-object `tool_input` and any internal error print a
  deny, and the `apply_patch` hook falls back to a deny when the script cannot start. Codex runs the tool
  when a hook errors or exits with a code other than 0 or 2.
- Hook log: patches (tool or shell-routed) are logged as `apply_patch <file names>`, and heredoc bodies
  are no longer part of any logged command shape.
- `provider_smoke.py` for Codex: probe (b) reads the secret with `cat` (Codex has no file-reading tool,
  so the old wording could only produce a false FAIL), and new probes (f) `apply_patch` on `AGENTS.md`
  and (g) a bare `bash` session must be blocked, logged and leave `AGENTS.md` unchanged.
- `run_evals.py --repeat N` runs every routing case N times; a case passes only when all N runs pass, and
  cases that pass only sometimes are listed as unstable (a single pass hid a 2-in-6 failure before).
- Benchmark: two multi-file tasks, `cart` (a feature built on a helper with a hidden off-by-one) and
  `listing` (three bugs in three files from one symptom-level report). Not measured yet; a unit test
  checks that every hidden acceptance test fails on the untouched project.
- `POLICY_VERSION` 4.3.0, so a global 4.3 copy keeps guarding projects that still ship 4.2 hooks.

## 4.2.2 — 2026-10-11

- `check_agent_config.py`: in an installed project it now scans only harness code for personal-home paths.
  Before, `AGENTS.md`, `docs/agent/` and templates were scanned too, so a project's own notes with real
  paths made the check fail. The harness source and release tree are still scanned in full.
- Upgrade path from 4.0.0 (no manifest) verified on two real projects: harness-owned files replaced,
  customized `AGENTS.md` / `CLAUDE.md` merged by hand, 101 tests pass in both.

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
