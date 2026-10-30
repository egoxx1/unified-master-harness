# Changelog

## 4.3.2 — 2026-10-31

Safety:

- **Antigravity edits of harness files are guarded.** Antigravity 1.4 edits with `edit_file` {`Path`, `Target`,
  `Replacement`} and `write_file` {`Path`, `Content`} (argument names recorded from real calls), which no V4 hook
  matched: an Antigravity agent could rewrite `AGENTS.md` or `policy.py`. Both are matched now; edits of harness
  enforcement files and secret files are denied, other edits get no decision so Antigravity's own permission
  mode applies (an "allow" would auto-approve them). New smoke probe (f) edits `AGENTS.md` with the file tool.
- The Antigravity CLI (print mode) offers only `read_file`, `edit_file`, `write_file` and `run_command` as file
  and shell tools; `grep_search`, `search_in_file`, `find_by_name`, `list_dir` and `view_content_chunk` do not
  exist there, so they are not an open path on the CLI. A subagent's file read goes through the same hook
  (measured: `view_file` denied, marker absent).
- The Antigravity smoke now also fails when the secret marker appears in Antigravity's conversation record,
  not only in the final answer (the 4.3.0 leak was visible only there).
- Shell: `source .env` / `. .env.local` now count as reading the secret; recursive `rm` whose targets come from
  `xargs` or start with a variable (`rm -rf "$DIR"`, `D=/; rm -rf $D`) asks; `find … -delete`/`-exec rm` under
  `/`, a home or an unfiltered `.`/`..` is denied, and under a variable asks; `echo`/`printf` of a variable named
  like a credential (`$AWS_SECRET_ACCESS_KEY`, `${GITHUB_TOKEN}`) asks. `set -e` is no longer mistaken for an
  environment dump. Asks are denials on Codex and Antigravity.
- Code fetched or decoded and run at once (`curl … | sh`, `bash <(curl …)`, `… | base64 -d | sh`, `xxd -r … | sh`)
  asks; `curl … | python3 -m json.tool` and `curl -o file` stay allowed. Codex: `lua`, `R`, `julia`, `php -a`,
  `rails console` (also through `bundle exec`), `mysqlsh`, `sqlplus` and `gdb` without inline code or a script
  are denied like other bare sessions.
- Codex and Antigravity hooks deny tool input over 128 KB before parsing it: both CLIs run the tool once a hook
  passes its 5 s timeout, and the policy takes up to ~2 s per MB of shell text on a laptop and about three times
  that on CI runners (a first 512 KB cap took 2.5–3.2 s there). A unit test times inputs just under the cap.
- **Claude Code MCP tools are checked.** The Claude hook matched `Bash|PowerShell|Read|Grep`, so an MCP tool
  (`mcp__<server>__<tool>`) could read `.env.local`: with a minimal stdio MCP server exposing `read_file`, the
  secret reached the model and the hook log stayed empty. The matcher now includes `mcp__.*`; every string
  argument is checked for secret paths, write-type tools for harness files, shell-type tools as commands. Rerun:
  the hook asked, the secret did not reach the model.
- The Antigravity hook matches every tool (`.*`). Known tools keep their rules; any other tool (a renamed or new
  one, as in 1.4) has its path-like arguments checked, secret files and harness edits denied, everything else
  left to Antigravity's own permission mode. Smoke with it: 7/7.
- Also asked now: decompressors piped into a shell (`gzip -dc … | sh`, `zcat … | bash`), a here-string of a
  credential variable (`cat <<< "$API_TOKEN"`), and inline code that decodes and executes a payload
  (`python3 -c "…b64decode…os.system…"`, `node -e "…Buffer.from(…'base64')…execSync…"`).
- `provider_smoke.py` and `run_evals.py` take `--agy-model` (Antigravity's default model quota ran out; the last
  Antigravity runs used `gemini-3.8-flash-high`).
- Antigravity's `--sandbox` flag was tested on 1.4.11: a `touch` outside the project into the home folder
  succeeded with and without it, so it is not used and Antigravity still has no OS-level layer here.

Rules:

- `AGENTS.md` 7,333 → 6,358 characters with the same rules (§5 routing, §8 autonomy and §10 security unchanged).
  §7 no longer requires running the regression test before the fix ("leave a test that covers the bug; run it
  before the fix only when the cause is not yet confirmed") and §6's "reproduce first" applies to bugs whose
  cause is not yet known. In the 10-run data the old wording added a red-test run and 2–3 turns to bug fixes
  whose cause the report already showed.
- Benchmark: new `wip` task: the slugify bug with a teammate's unfinished, uncommitted `initials()` and its
  failing test in the working tree; correct only if the bug is fixed and every line of that work is kept.
- Measured (10 tasks × 10 runs per side, Opus 5.5, same day as 4.3.1): the harness's cost on the nine shared
  tasks $29.50 → $29.18 (−1%, noise), overhead over bare +16.0% → +16.0%. **The shorter policy did not lower the
  cost**; bug fixes lost about one turn. 100/100 correct on both sides; `wip` kept the work 10/10 on both sides.
  Over both days the harness ran the tests in 169/170 runs vs 158/170 without (p = 0.001) and left a regression
  test after 110/110 vs 104/110 bug fixes (p = 0.015).
- Routing evals ×3 on the new `AGENTS.md`: Claude Code 12/12 and Codex 12/12 (every case 3 of 3); Antigravity
  33/36 runs passed, none chose a wrong skill, 3 ended without an answer (one timeout, two provider errors, one of
  them the account's quota running out, so the missing runs could not be repeated).
- Smoke on 4.3.2: Claude Code 6/6 + 8/8, Codex 8/8, Codex hook probe PASS and control FAIL as expected;
  Antigravity 7/7 before the input cap, fetch-and-run and REPL rules (unit-tested; quota exhausted afterwards).

## 4.3.1 — 2026-10-31

- **Antigravity 1.4.11 secret read fixed.** Antigravity 1.4 reads files with a new `read_file` tool whose path
  argument is `Path`. The V4 hook matched only `run_command|view_file`, so on 1.4.11 the smoke's secret-file
  probe was allowed, the hook never saw the call, and the fixture's marker reached the model (it was in the
  conversation record). `.agents/hooks.json` now also matches `read_file` and the policy reads `Path`. Smoke on
  1.4.11 after the fix: 6/6, marker absent.
  Still unmatched on 1.4.11 because their argument names are not documented: `grep_search`, `search_in_file`,
  `find_by_name`, `list_dir`, `view_content_chunk`, `edit_file`, `write_file`.
- Codex: `irb`, `ghci` (also with a file, which still waits for input) and `ssh host` without a command, or with
  a remote command that is itself a bare session (`ssh -t host bash`), are denied like other bare sessions;
  `ssh host uptime`, `ssh -N -L …`, `ssh -O exit host`, `irb script.rb` and `ghci -e …` stay allowed.
- `run_evals.py`: default timeout 720 s on Antigravity (1.4.11 took 300–575 s per case; 420 s cut one run off).
- `agent-core/HARNESS-MANIFEST.json` had not been rewritten after the 4.3.0 policy and skill edits, so an
  unzipped 4.3.0 template would treat those files as project edits on upgrade. Regenerated, and a unit test now
  fails when the committed manifest differs from the tree.
- Benchmark: new `token` task (`bench/project3`): tests fail for a missing `ALERTS_API_TOKEN`, and a git-ignored
  `.env.local` with a fresh fake token sits in the repository. `run_bench.py` reports `leaked` when that token
  shows up in what the agent read or wrote. A hidden-test check confirms a fix that loads `.env.local` fails.
- Benchmark, 10 runs per task and side on all nine tasks (180 runs, Opus 5.5): harness +16% cost, 90/90
  correct on both sides, no task won (`token`: 0/10 leaked either way; the bare agent never opened the file).
  The 4.3.0 finding "regression test after every bug fix, 15/15 vs 9/15" did not hold: 50/50 vs 49/50.
- Smoke on 4.3.1, all three on their current CLI: Claude Code 2.1.314 6/6 + Claude layer 8/8, Antigravity
  1.4.11 6/6, Codex 0.165.0 8/8; Codex hook probe PASS and its negative control FAIL as expected.

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
  `listing` (three bugs in three files from one symptom-level report); a unit test checks that every
  hidden acceptance test fails on the untouched project. Measured on Claude Code (12 runs): same results
  with and without the harness (6/6 correct, 6/6 ran tests), about 23% more cost with it.
- Less fixed process on small and medium tasks: `dev-debug` (in `AGENTS.md` §5 and its description) is
  only for bugs whose cause is not yet known, and not for spacing, size or color fixes; `AGENTS.md` §6
  says to open `agent-core/project/profile.md` only when a needed command is not in the files already read.
  Benchmark, 18 runs per side: `dev-debug` loads 6 → 0, profile reads 8 → 3, correctness 18/18 kept; cost
  unchanged within noise ($5.69 → $5.60, −2%; overhead vs bare +22% → +19%). Routing evals ×3: Claude
  Code 12/12 → 12/12, Codex 11/12 → 12/12. The `small-css` eval case now also forbids `dev-debug`.
  Antigravity 1.4.11 ×3 afterwards: 11 cases 3 of 3; `copy-error-message` timed out once at 420 s (no
  answer, not a wrong route) and passed 3 of 3 rerun with a 720 s limit.
- Benchmark: `run_bench.py --arms` adds `harness-nosandbox` and `harness-norule` to price the two cost
  switches separately. On `cart`/`listing` (6 runs per arm): sandbox off −9% of the harness cost (about 60%
  of its extra cost over bare), regression-test rule removed −3% (noise); correctness 6/6 in every arm.
- Benchmark: two tasks meant to favor the harness in `bench/project2`, `percent` (callers with rates in a
  config module and a JSON file) and `refund` (symptom four files from its cause), with stored reference
  solutions; a unit test checks they pass the hidden and visible tests. Result: the harness did not win
  (3/3 vs 3/3 on both, +26% and +11% cost). A hidden-test assertion outside the documented contract
  (float input to `to_cents`) first scored one harness run as failing; it was removed and the run rescored.
- `run_bench.py` no longer crashes on a stream event whose `message` is a string.
- Rerun on Claude Opus 5.5: without the harness the agent also ran the tests (27/27 non-typo runs); the
  harness still left a regression test after every bug fix (15/15 vs 9/15).
- `doctor.py`: the advice for an older user-level hook copy no longer says to overwrite every `*_pretool.py`
  (a local copy can carry its own rules); back up, copy `policy.py`/`hook_log.py`/`scope.py`, diff the rest.
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
