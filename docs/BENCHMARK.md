# Efficiency benchmark — what the harness costs and what it buys

Measured 2026-10-11 with `bench/run_bench.py` on Claude Code 2.1.296 (default model, `claude-sonnet-5-5`),
macOS. Raw data: `docs/benchmarks/2026-10-11-*.json`. Rerun it yourself: `python3 bench/run_bench.py --reps 3`.

## Setup

Four small tasks on a tiny Python project (`bench/project/`): fix a typo, fix two bugs, add a small
function. Each task runs 3 times in a fresh repository **without** the harness and 3 times **with** it
(installed by `install/apply.py`), same prompt, same CLI flags, same allowed tools. Measured:

- cost and tokens, from Claude Code's own final report;
- changed lines in project files (harness files excluded);
- correctness, by hidden tests the agent never sees;
- whether the agent checked its own change (ran tests or a Python check).

## Results (medians of 3 runs, after the AGENTS.md trim below)

| Task | Cost without → with | Input tokens without → with | Product lines changed | Correct |
|---|---|---|---|---|
| typo | $0.087 → $0.101 (+17%) | 92.9k → 107.0k | 2 → 2 | 3/3, 3/3 |
| bugfix | $0.091 → $0.115 (+26%) | 93.4k → 144.7k | 2 → 2 | 3/3, 3/3 |
| slugify | $0.095 → $0.118 (+24%) | 125.1k → 180.7k | 2 → 2 | 3/3, 3/3 |
| discount | $0.102 → $0.118 (+16%) | 156.6k → 180.6k | 7 → 7 | 3/3, 3/3 |
| **All 24 runs** | **$1.12 → $1.34 (+20%)** | | | **12/12, 12/12** |

Self-checks on the three non-trivial tasks: with the harness 9/9 runs checked their change, without it
8/9 (7/9 in the earlier run). Running the actual test suite was rare in both arms.

## What this means

- **On small tasks the harness costs about 20% more, and does not make code shorter or more
  correct**, because without it the model already solves these tasks with minimal diffs. These tasks
  are too easy to show differences in correctness; they measure overhead.
- The overhead is mostly fixed context, not extra work: about **4,800 input tokens per turn**
  (measured by removing one part at a time):

  | Part | Tokens per turn |
  |---|---|
  | Claude Code's own sandbox instructions (shown whenever the sandbox is on) | ~2,700 |
  | `AGENTS.md` | ~2,200 |
  | Everything else: `CLAUDE.md` note, secret-file deny rules, skill/subagent/command listing | a few hundred |
  | Hooks | ~0 |

  (Each part was measured by removing it alone; the parts overlap slightly, so they do not add up exactly.)

  Most of it is served from the prompt cache, which is why cost rises less than input tokens.
- What the 20% buys is not visible in these numbers: the safety hooks, secret protection and the
  sandbox (see `VERIFICATION-REPORT.md`), plus a consistent self-check before finishing.

## Trimming AGENTS.md (done)

The first run used a 117-line `AGENTS.md` (9.4 KB). It repeated what the skills already say. It was
rewritten to 49 lines (6.6 KB) with every rule kept: per-turn overhead fell from about 5,700 to about
4,800 tokens. Total cost over 24 runs went from +22% to +20%. Skill routing stayed 12/12 on Claude Code
after the change.

| | before trim | after trim |
|---|---|---|
| Harness overhead per turn | ~5,700 tokens | ~4,800 tokens |
| Cost, 24 runs (without → with) | $1.17 → $1.43 (+22%) | $1.12 → $1.34 (+20%) |

## If you want fewer tokens

Turning off the Claude Code sandbox (`"sandbox": {"enabled": false}`) saves about 2,700 tokens per
turn, but then secret files and writes outside the project are guarded only by hooks and permission
rules, not by the OS. V4 keeps it on.

## Not measured yet

Medium and large tasks (multi-file changes, real debugging), where process discipline should matter
more, and Codex and Antigravity. Contributions of such tasks to `bench/` are welcome.
