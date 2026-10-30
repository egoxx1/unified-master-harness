# Efficiency benchmark — what the harness costs and what it buys

Measured 2026-10-11 with `bench/run_bench.py` on Claude Code 2.1.296 (default model, `claude-sonnet-5-5`),
macOS. Raw data: `docs/benchmarks/2026-10-11-*.json`. Rerun it yourself: `python3 bench/run_bench.py --reps 3`.

## Setup

Four small tasks on a tiny Python project (`bench/project/`): fix a typo, fix two bugs, add a small
function. Each task runs 3 times in a fresh repository **without** the harness and 3 times **with** it
(installed by `install/apply.py`), same prompt, same CLI flags, same allowed tools. Measured:

- cost and tokens, from Claude Code's own final report;
- changed lines in project files, tests included (harness files excluded);
- correctness, by hidden tests the agent never sees;
- whether the agent ran the test suite, or at least checked its change some other way.

## Results for the current version (medians of 3 runs)

| Task | Cost without → with | Input tokens without → with | Lines changed (incl. tests) | Correct |
|---|---|---|---|---|
| typo | $0.087 → $0.102 (+17%) | 92.9k → 107.4k | 2 → 2 | 3/3, 3/3 |
| bugfix | $0.090 → $0.142 (+57%) | 93.4k → 262.6k | 2 → 9 | 3/3, 3/3 |
| slugify | $0.097 → $0.134 (+39%) | 125.3k → 258.2k | 2 → 7 | 3/3, 3/3 |
| discount | $0.090 → $0.130 (+44%) | 93.3k → 220.9k | 7 → 18 | 3/3, 3/3 |
| **All 24 runs** | **$1.08 → $1.53 (+42%)** | | | **12/12, 12/12** |

On the three non-trivial tasks (9 runs per side):

| | Without harness | With harness |
|---|---|---|
| Ran the test suite | 0/9 | **9/9** |
| Checked the change in any way | 6/9 | **9/9** |
| Bug fixes that left a regression test | 0/6 | **6/6** |

## What this means

- **The harness changes behavior, and that behavior costs tokens.** With it, the agent runs the tests
  every time and leaves a regression test after every bug fix. Without it, the agent usually checks the
  fix with a one-off command and never touches the tests. The extra lines are those tests; the product
  code change is the same size in both arms.
- **On these easy tasks both arms were always correct,** so the extra work did not change today's
  result. Its value is the test left behind: the same bug cannot quietly come back.
- **About 4,900 input tokens per turn are fixed context** (measured by removing one part at a time):

  | Part | Tokens per turn |
  |---|---|
  | Claude Code's own sandbox instructions (shown whenever the sandbox is on) | ~2,700 |
  | `AGENTS.md` (51 lines) | ~2,400 |
  | Everything else: `CLAUDE.md` note, secret-file deny rules, skill/subagent/command listing | a few hundred |
  | Hooks | ~0 |

  (Each part was measured by removing it alone; the parts overlap slightly, so they do not add up
  exactly.) Most of it is served from the prompt cache, which is why cost rises less than input tokens.
- The rest of the price buys the safety layer: hooks, secret protection and the sandbox (see
  `VERIFICATION-REPORT.md`).

## How the cost moved between versions

| Version of `AGENTS.md` | Overhead per turn | Cost, 24 runs (without → with) | Tests run on non-trivial tasks (with) |
|---|---|---|---|
| 117 lines (first public draft) | ~5,700 tokens | $1.17 → $1.43 (+22%) | 4/9 |
| 49 lines, same rules, duplicates removed | ~4,800 tokens | $1.12 → $1.34 (+20%) | 1/9 |
| 51 lines, + dependency and regression-test rules (current) | ~4,900 tokens | $1.08 → $1.53 (+42%) | **9/9** |

Trimming the policy made it cheaper without changing behavior. The regression-test rule is the
deliberate exception: it doubles the cost increase in exchange for a tested fix every time.

## If you want fewer tokens

- Remove the regression-test line from `AGENTS.md` §7: back to about +20% on these tasks, without the tests.
- Turn off the Claude Code sandbox (`"sandbox": {"enabled": false}`): about 2,700 tokens less per turn,
  but secret files and writes outside the project are then guarded only by hooks and permission rules,
  not by the OS.

V4 keeps both on.

## Not measured yet

Medium and large tasks (multi-file changes, real debugging), and Codex and Antigravity. Contributions of
such tasks to `bench/` are welcome.

## Larger tasks (added in 4.3.0, not measured yet)

Two multi-file tasks were added because the four above are too small for process discipline to matter:

- `cart`: build `shop/cart.py` on top of the existing helpers. The existing `paginate()` returns one item
  too many and the prompt does not say so; only an agent that tests its cart's paging finds and fixes it.
- `listing`: three symptoms from a bug report, caused by bugs in three files (`pagination.py`, `text.py`
  twice), with edge cases (`truncate` for every limit 0-7) the report only hints at.

Both hidden tests fail on the untouched project and pass on a reference solution (checked by a unit test
and by hand). Measure them with `python3 bench/run_bench.py --tasks cart,listing --reps 3`.

