# START HERE — Unified Master Harness (V4)

This repository uses one work policy (`AGENTS.md`), six workflow skills and the same safety hooks for
Claude Code, Codex and Antigravity. People own **intent, acceptance criteria, risky decisions and
merges**; agents own implementation detail. (한국어: `START-HERE.ko.md`)

## 1. First-time setup (once per repository)

```bash
python3 agent-core/scripts/bootstrap_project.py --write   # record repo facts (commands, ports) from evidence only
python3 agent-core/scripts/install_git_hooks.py           # pre-commit: block secret files + check harness config
python3 agent-core/scripts/doctor.py                      # find user-level settings that weaken the harness
```

Fix `RISK` findings first and read every `WARN`. `doctor.py` never changes anything.

Each tool must trust this folder once before the project settings apply:

- **Codex:** open `codex` here, trust the project, then review and trust the V4 hook in `/hooks`.
  After that `.codex/config.toml` (workspace-write sandbox) applies.
- **Antigravity:** approve the workspace-trust prompt the first time you open `agy` here.
- **Claude Code:** no extra step; `.claude/settings.json` hooks and permission rules apply at once.

Then check that the tools really read the policy and block through the hooks (a few minutes, a little
usage per tool):

```bash
python3 agent-core/scripts/provider_smoke.py
python3 agent-core/scripts/codex_hook_probe.py   # Codex hooks only, no account or usage needed
```

When real work starts, fill in `PROJECT.md` (see `templates/PROJECT.md`): purpose, users and
non-negotiables. Agents judge product trade-offs against it.

## 2. What changes in Claude Code

`.claude/settings.json` turns on enforcement that only Claude Code supports.

- **Sandbox (loose):** shell commands may write only inside this project, temp folders and package
  caches (`~/.npm`, `~/.cache`, ...). Network is open. If a tool must write elsewhere, add the path to
  `sandbox.filesystem.allowWrite`. Retrying outside the sandbox is disabled.
- **Secret files:** Claude cannot read `.env`, key files and similar (the OS also blocks `cat .env`
  from the shell). `.env.example` stays readable. Open secrets yourself when you need them.
- **Harness protection:** editing `AGENTS.md`, `CLAUDE.md`, `agent-core/hooks|scripts|evals`, `.codex`
  or `.agents` asks for approval, and the shell cannot write them at all. Run harness maintenance
  (`sync_agent_config.py`, `upgrade_harness.py`, `install_git_hooks.py`) **in your own terminal**.
- **Verification warning:** if Claude edits code and stops without a test, build or run check, you see
  "V4 verification warning". It does not block; ask for verification when you see it.
- **Long tasks:** just before context compaction, the request, edited files and verification state are
  saved, and handed back to Claude right after.
- **Commands:** `/harness-check`, `/retro` (harness retrospective), `/smoke` (all-tool smoke test).
  Independent review of risky changes goes to the `dev-reviewer` subagent.

## 3. Everyday use

Ask for outcomes. The process scales with the task: small changes are made directly, large ones
start with acceptance criteria via `dev-plan`. For large work, `templates/TASK-REQUEST.md` keeps the
request complete. PRs come with a `templates/PR-BODY.md` summary (what changed, what was verified,
risk), so you judge intent, behaviour, evidence and risk.

## 4. Regular checks

| When | Command | Why |
|---|---|---|
| Every 3–5 meaningful tasks | `python3 agent-core/scripts/growth_engine.py ingest-hooks`, then `candidates` | Turn repeated blocks and false positives into observations and improvement candidates |
| Same time | `python3 agent-core/scripts/growth_engine.py hook-stats` | Recent blocks |
| After updating an agent CLI | `python3 agent-core/scripts/provider_smoke.py` | Catch hook behaviour changed by the update |
| After updating Codex (no account needed) | `python3 agent-core/scripts/codex_hook_probe.py` | Codex really runs the safety hook (zero usage) |
| After changing skills or policy | `python3 agent-core/scripts/run_evals.py --provider claude` | Skill routing did not regress (one model call per case) |
| Any time | `python3 agent-core/scripts/doctor.py` | Global settings and secret files |

A person decides whether a candidate improvement is adopted. Policy, safety-hook and permission
changes always need human review (`docs/agent/GROWTH-ENGINE.md`).

## 5. Upgrading the harness

From this repository, with a newer harness checkout at `/path/to/unified-master-harness`:

```bash
python3 agent-core/scripts/upgrade_harness.py --from /path/to/unified-master-harness           # preview
python3 agent-core/scripts/upgrade_harness.py --from /path/to/unified-master-harness --apply   # apply (backs up first)
```

Harness files you changed here are not overwritten: the new version is written next to them as
`<file>.v4-new`. Merge, delete the `.v4-new` file and rerun `check_agent_config.py`.
`PROJECT.md`, the project profile and growth history are never touched.

## 6. Do not

- Bypass the pre-commit check with `git commit --no-verify` (and do not let agents do it).
- Let agents edit `AGENTS.md`, the safety hooks or permission settings on their own.
- Make global auto-approval the default here (Claude `bypassPermissions`, Codex
  `approval_policy = "never"` with `danger-full-access`, Antigravity `always-proceed`); `doctor.py` warns.
- Keep real secrets in a `.env` inside the repository for agents to handle; inject them at run time.

## 7. Map

- `AGENTS.md` — shared work policy (always loaded)
- `PROJECT.md` — product source of truth (you write it)
- `docs/agent/ARCHITECTURE.md` — structure and the safety decision table
- `docs/agent/OPERATING-GUIDE.md` — who does what, people and agents
- `docs/agent/GROWTH-ENGINE.md` — how the harness improves
- `docs/agent/VERIFICATION.md` — checks before a release
- `agent-core/evals/provider-smoke.md` — per-tool runtime notes
