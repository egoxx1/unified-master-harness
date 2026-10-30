# Efficiency benchmark — what the harness costs and what it buys

**Latest (4.3.0, 2026-10-30, Claude Code 2.1.314, `claude-opus-5-5`):** on all 8 tasks the harness and
bare runs were equally correct; the harness cost +11% to +27% per task and won none. On the larger tasks
about 60% of its extra cost is the Claude Code sandbox; the regression-test rule's share was inside the noise.
Details in the 4.3.0 sections below. Differences under 5% are marked as noise.

The sections up to "If you want fewer tokens" were measured 2026-10-11 with `bench/run_bench.py` on Claude
Code 2.1.296 (default model then, `claude-sonnet-5-5`), macOS. Raw data: `docs/benchmarks/*.json`. Rerun it
yourself: `python3 bench/run_bench.py --reps 3`.

## Setup

Four small tasks on a tiny Python project (`bench/project/`): fix a typo, fix two bugs, add a small
function. Each task runs 3 times in a fresh repository **without** the harness and 3 times **with** it
(installed by `install/apply.py`), same prompt, same CLI flags, same allowed tools. Measured:

- cost and tokens, from Claude Code's own final report;
- changed lines in project files, tests included (harness files excluded);
- correctness, by hidden tests the agent never sees;
- whether the agent ran the test suite, or at least checked its change some other way.

## Results for 4.2.1 (2026-10-11, medians of 3 runs)

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

- Remove the regression-test line from `AGENTS.md` §7: back to about +20% on these tasks (4.2.1), without the tests.
- Turn off the Claude Code sandbox (`"sandbox": {"enabled": false}`): about 2,700 tokens less per turn,
  but secret files and writes outside the project are then guarded only by hooks and permission rules,
  not by the OS.

V4 keeps both on. On the larger tasks (below) the sandbox was the bigger part and the rule was noise.

### What each switch costs on the larger tasks (measured 2026-10-30)

Both switches, one at a time, on `cart` and `listing`, 3 runs per task and arm, all four arms in the same
run (Claude Code 2.1.314, `claude-opus-5-5`; raw data `docs/benchmarks/2026-10-30-switches-cart-listing.json`):

| Arm (6 runs each) | Cost | vs bare | vs full harness | Correct | Left a test file |
|---|---|---|---|---|---|
| bare | $1.86 | — | | 6/6 | 6/6 |
| harness | $2.20 | +18% | — | 6/6 | 6/6 |
| harness, sandbox off | $2.00 | +8% | **−9%** (cart −9%, listing −9%) | 6/6 | 6/6 |
| harness, regression-test rule removed | $2.13 | +15% | −3%, noise (cart −8%, listing +2%) | 6/6 | 6/6 |

Of the $0.34 the harness added over bare here, turning the sandbox off removed $0.20 (about 60%), the same
in both tasks. Removing the regression-test rule removed $0.07, inside the noise: on these tasks the agent
left a test file in every run in every arm, bare included, so the rule had nothing to add. The remaining
~$0.07-0.14 (rest of `AGENTS.md`, skill listing, hooks) was not split further; the switches were measured
one at a time, not together, so they need not add up. With the sandbox off one `cart` run did not run the
test suite (2/3); every other arm ran it 3/3. On the four small tasks (2026-10-11, Sonnet) the rule was the
larger cost; on these larger tasks it is the sandbox.

## Not measured yet

Codex and Antigravity (the benchmark runs Claude Code only). Contributions of tasks to `bench/` are welcome.

## Larger tasks (added in 4.3.0, measured 2026-10-30)

Two multi-file tasks were added because the four above are too small for process discipline to matter:

- `cart`: build `shop/cart.py` on top of the existing helpers. The existing `paginate()` returns one item
  too many and the prompt does not say so; only an agent that tests its cart's paging finds and fixes it.
- `listing`: three symptoms from a bug report, caused by bugs in three files (`pagination.py`, `text.py`
  twice), with edge cases (`truncate` for every limit 0-7) the report only hints at.

Both hidden tests fail on the untouched project (checked by a unit test) and pass on a reference solution
(checked by hand; no reference is stored for these two). Measured with
`python3 bench/run_bench.py --tasks cart,listing --reps 3` on Claude Code 2.1.314 (default model
`claude-opus-5-5`), macOS, 12 runs. Medians:

| Task | Arm | Correct | Ran tests | Lines changed | Cost | Turns | Seconds |
|---|---|---|---|---|---|---|---|
| cart | without | 3/3 | 3/3 | 90 | $0.321 | 8 | 39 |
| cart | with | 3/3 | 3/3 | 108 | $0.409 | 10 | 67 |
| listing | without | 3/3 | 3/3 | 21 | $0.292 | 9 | 34 |
| listing | with | 3/3 | 3/3 | 21 | $0.352 | 13 | 33 |

All 12 runs: $1.85 without, $2.28 with (**+23%**), correct 6/6 on both sides.

**What this shows, plainly: on these tasks the harness bought nothing measurable.** Without the harness
the agent also ran the tests every time and also found the hidden `paginate()` bug in all three `cart`
runs. That differs from the 2026-10-11 runs above, where the agent without the harness ran the test suite
0/9 times; the default model or Claude Code itself now does that unprompted. With the harness the agent
loaded `dev-debug` on every `listing` run and read the project profile, which looked like the source of
the extra turns and tokens (removing both did not change the cost beyond noise; see below). Either these
tasks are still too easy to separate the arms, or the harness's verification rules now duplicate what the
model does by itself. Telling which needs harder tasks (long debugging, a change that breaks a distant
caller) or a cheaper default for small work (both tried below); until then the honest summary is "same results, about a quarter more cost".

## Cutting fixed process cost on small and medium tasks (4.3.0)

The 4.3.0 runs showed two steps that added turns without changing results: the agent loaded `dev-debug` for
bugs whose cause the report or one read of the code already showed (`bugfix` 3/3, `listing` 3/3), and it
opened `agent-core/project/profile.md` on most tasks, also when the file did not exist (8 of 18 runs).
`AGENTS.md` §5/§6 and the `dev-debug` description now say: `dev-debug` only when the cause is not yet known,
not for spacing, size or color fixes; open the profile only when a needed command is not in the files
already read.

Same day, same CLI and model, 3 runs per task and arm (raw data:
`docs/benchmarks/2026-10-30-{before,after}-fixed-cost.json`):

| Task | Harness cost before → after | Overhead vs bare before → after | `dev-debug` loaded | profile opened | Correct (harness) |
|---|---|---|---|---|---|
| typo | $0.73 → $0.74 (noise) | +17% → +20% | 0 → 0 | 0 → 0 | 3/3, 3/3 |
| bugfix | $0.96 → $0.91 (−5%) | +38% → +23% | 3 → 0 | 0 → 0 | 3/3, 3/3 |
| slugify | $0.84 → $0.85 (noise) | +17% → +18% | 0 → 0 | 2 → 0 | 3/3, 3/3 |
| discount | $0.88 → $0.89 (noise) | +15% → +11% | 0 → 0 | 3 → 1 | 3/3, 3/3 |
| cart | $1.20 → $1.20 (noise) | +25% → +27% | 0 → 0 | 1 → 2 | 3/3, 3/3 |
| listing | $1.08 → $1.01 (−6%) | +21% → +14% | 3 → 0 | 2 → 0 | 3/3, 3/3 |
| **All 18 runs per side** | **$5.69 → $5.60 (−2%, noise)** | **+22% → +19%** | **6 → 0** | **8 → 3** | **18/18, 18/18** |

Costs are sums of 3 runs. The bare arm, which did not change, moved by −3% to +7% per task between the two
runs, so per-task differences under about 5% are noise. What held: `dev-debug` was never loaded for these
obvious bugs, profile reads fell from 8 to 3, correctness stayed 18/18, the tests ran in 15/15 non-typo
runs and every bug fix still left a regression test (9/9). What did not: the cost. Overall it is unchanged
within noise. The two tasks that lost the `dev-debug` step came out 5% and 6% cheaper, barely past the
noise line while the unchanged bare arm drifted by up to 7%, so that is not established either. The rest
of the overhead is the per-turn context (`AGENTS.md`, sandbox instructions) and the testing the harness
asks for, which these wording changes do not touch. A profile read costs almost nothing on its own because the agent bundles it into a
shell call it makes anyway.

Routing evals with the same change (`run_evals.py --repeat 3`, `small-css` now also forbids `dev-debug`):
Claude Code 12/12 before and after; Codex 11/12 before (`small-css` declared `dev-debug` in 3 of 3 runs,
rescored from the earlier 4.3.0 run with the harness unchanged) and 12/12 after. `bug-api-500`, a bug whose
cause is unknown, still routes to `dev-debug` in 3 of 3 runs on both.

## Tasks meant to favor the harness (added in 4.3.0)

Two tasks in a second project (`bench/project2`, a small store working in integer cents) target what the
harness asks for and a lone agent might skip. Stored reference solutions (`bench/reference/<task>/`) pass the
hidden and the visible tests and the untouched project fails them (unit test); partial fixes were checked by
hand to fail.

- `percent`: change `apply_discount` from a fraction (0.1) to a percentage (10). Its callers take their
  rates from `store/config.py` (0.05, 0.1) and `data/promotions.json` (0.15, 0.3). Those stay inside 0-100,
  so after a change to `pricing.py` alone every member and promotion discount silently becomes a fraction
  of a percent, and no existing test notices.
- `refund`: "a $19.99 mug was refunded $19.98". The cause is four files away: `refunds.py` →
  `orders.py` → `catalog.py` → `money.to_cents`, which truncates `float("19.99") * 100`. The same bug hits
  other catalog prices, negative credits and typed-in refunds, which the report does not mention.

Measured 2026-10-30, 3 runs per arm (raw data: `docs/benchmarks/2026-10-30-new-tasks-percent-refund.json`):

| Task | Correct, bare vs harness | Cost bare → harness | Turns (median) |
|---|---|---|---|
| percent | 3/3, 3/3 | $0.96 → $1.21 (+26%) | 7 → 14 |
| refund | 3/3, 3/3 (first scoring: 3/3, 2/3) | $0.98 → $1.08 (+11%) | 10 → 12 |

**The harness did not win either task.** The bare agent found the config and JSON callers in 3 of 3
`percent` runs and fixed `to_cents` at the source in 3 of 3 `refund` runs; the harness reached the same
result for more money. The first scoring had the harness at 2/3 on `refund`: that run fixed `to_cents` with
`Decimal(amount)`, which is exact for every string the docstring describes, but the hidden test also
checked a float argument (`to_cents(19.99)`) that the docstring never promised. That assertion was removed
as a test error, and the run, replayed from its transcript, passes the corrected test. Both scorings are in
the raw data. On current models, a task the harness wins needs to be harder than these; that remains open.

