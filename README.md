# Unified Master Harness (V4)

**One work policy, six workflow skills and real safety hooks, shared by Claude Code, Codex and Antigravity.**

Drop it into a repository and every agent you use follows the same rules: size the process to the
task, make the smallest change that solves it, verify before claiming done, and never run the
commands that lose work or leak secrets. The rules are plain files; the safety part is enforced by
hooks that each CLI actually runs, and every claim below was measured on real CLIs
([verification report](docs/VERIFICATION-REPORT.md)).

[한국어 README](README.ko.md)

## What you get

- **`AGENTS.md`, one policy for three agents** (49 lines, about 2,200 tokens, always loaded): task sizing (small /
  medium / large), evidence over guessing, smallest coherent change, no speculative refactors, no
  re-reading unchanged files, verification before completion. Claude reads it through `CLAUDE.md`,
  Antigravity through a generated mirror.
- **Six skills, loaded only when needed:** `project-context`, `dev-plan` (large or ambiguous work
  only), `dev-debug`, `dev-ui-verify` (depth scales with the change), `dev-verify`, `dev-review`.
- **Safety hooks on all three CLIs** from one shared policy (`agent-core/hooks/policy.py`):
  - work-destroying commands: `git reset --hard`, `checkout -- .`, `restore .`, `stash clear`,
    `clean -f`, force push, `rm -rf` on home or system roots, also behind `sh -c`, `sudo`, `env`,
    `xargs` and git global options;
  - secret files: `.env*`, keys, `.netrc`, cloud and container credentials — reading, copying or
    encoding them;
  - external actions: `git push`, package publish, releases, deploys, infrastructure apply,
    database drops;
  - writes to the harness itself.
  Each provider gets the strongest response it can enforce: Claude asks or denies, Codex and
  Antigravity deny (their hooks cannot prompt reliably).
- **A Claude Code layer** on top: permission rules merged into the OS sandbox (secrets stay
  unreadable even from the shell), a loose sandbox (writes limited to the project, temp and package
  caches; network open), a warning when Claude stops after editing code without any check, a
  context snapshot that survives compaction, a read-only review subagent and three slash commands.
- **Tools to keep it honest:** `doctor.py` (finds user settings that silently disable all this),
  `provider_smoke.py` (real CLI runs in a disposable repo), `codex_hook_probe.py` (Codex hook check
  with no account), `run_evals.py` (does each agent pick the right skills?), a secret-blocking
  pre-commit hook, CI, a secret-free block log, and `upgrade_harness.py` that never overwrites your
  own edits.

## Measured results (V4.2.1)

| | Claude Code 2.1.296 | Antigravity 1.3.3 | Codex CLI 0.161.0 |
|---|---|---|---|
| Safety smoke on the real CLI | 6/6 + 8/8 Claude layer | 6/6 | hook runtime PASS (model-free probe) |
| Skill routing, 12 cases | 12/12 | 12/12 | not run |

Details, method, what failed along the way and the known gaps: [docs/VERIFICATION-REPORT.md](docs/VERIFICATION-REPORT.md).

**Cost.** On four small tasks (24 Claude Code runs with vs without the harness) the harness cost about
**20% more** and every run was correct either way: these models already make minimal fixes on easy tasks,
so the harness does not make them shorter. The overhead is mostly fixed context (about 4,800 input tokens
per turn, half of it Claude Code's own sandbox instructions). What it buys is the safety layer and a
consistent self-check before finishing. Full numbers and how to cut the overhead: [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Requirements

- macOS or Linux (Windows: use WSL; native Windows is untested)
- Python 3.10+ and git. No other dependencies.
- At least one of Claude Code, Codex CLI or Antigravity CLI.

## Install

```bash
git clone https://github.com/egoxx1/unified-master-harness.git
python3 unified-master-harness/install/apply.py --target /path/to/your-repo            # dry run
python3 unified-master-harness/install/apply.py --target /path/to/your-repo --apply --create-project-template
```

Then follow `START-HERE.md` in your repository (three commands, and trusting the folder once in
Codex and Antigravity).

- **Repository already has `AGENTS.md`, `CLAUDE.md` or agent settings?** The installer refuses to
  overwrite them (exit code 2, nothing written). Give
  [install/INSTALLATION-PROMPT.md](install/INSTALLATION-PROMPT.md) to an agent to merge them by
  meaning.
- **Upgrading:** `python3 agent-core/scripts/upgrade_harness.py --from /path/to/unified-master-harness`
  in your repository. Files you changed are kept; the new version lands next to them as `.v4-new`.
- Your `README.md`, product code and `PROJECT.md` are never touched.

## How it works

```
PROJECT.md             what the product is (you write it)
AGENTS.md              how agents work (shared policy)
.agents/skills/        on-demand procedures (canonical; mirrored to .claude/skills/)
agent-core/hooks/      policy.py + one small adapter per CLI
.claude/  .codex/  .agents/hooks.json   provider wiring
agent-core/scripts/    deterministic tools: doctor, smoke, evals, upgrade, sync, checks
.agent-state/          local task state and block log (gitignored)
```

More: [START-HERE.md](START-HERE.md), [docs/agent/ARCHITECTURE.md](docs/agent/ARCHITECTURE.md).

## Limits

The command policy is a narrow guard, not a shell firewall: it does not see secrets printed through
variables, targets passed through stdin, or paths built in variables. Code correctness still rests
on tests and the agent's own verification and review, which can miss things; the harness makes
skipping verification visible, not impossible. See the report for the full list.

## Contributing, security, license

- [CONTRIBUTING.md](CONTRIBUTING.md): every policy change needs a block test and an allow test;
  skill changes need eval scores before and after.
- [SECURITY.md](SECURITY.md): report bypasses privately.
- [MIT License](LICENSE). Ideas were adapted from openai/codex, openai/openai-agents-python,
  vercel/next.js, obra/superpowers, addyosmani/agent-skills, multica-ai/andrej-karpathy-skills and
  jbarbier/CLAUDE.md; pinned revisions are in `agent-core/sources.lock.json`.
