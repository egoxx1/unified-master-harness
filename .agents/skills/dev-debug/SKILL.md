---
name: dev-debug
description: Diagnose bugs, failing tests, crashes, regressions, and unexplained behavior before proposing a fix. Use when there is an observed failure or mismatch; do not use for ordinary feature implementation.
---

# Systematic Debugging

Fix causes, not symptoms.

## 1. Establish evidence

- Read the actual error, trace, or output.
- Reproduce the failure when practical.
- Record the smallest reliable trigger.
- Check relevant recent changes, configuration, and environment differences.

If reproduction is unreliable, gather more evidence instead of guessing.

## 2. Localize the failing boundary

For multi-component flows inspect boundaries in order: input → caller → service/API → persistence/external dependency → output.
Determine the earliest boundary where actual behavior diverges from expected behavior.
Trace bad values backward until their source is identified.

## 3. Compare with working patterns

Find the closest working path in the same repository.
List meaningful differences before editing.
Check configuration, lifecycle, async/concurrency, retry, and cleanup assumptions.

## 4. Form one hypothesis

State a concrete causal hypothesis: X causes the failure because evidence Y shows divergence at boundary Z.
Test one variable at a time with the smallest useful experiment.
If it fails, return to evidence. Do not stack speculative fixes.

## 5. Implement the narrowest correct fix

Fix where incorrect state or decision originates.
Avoid unrelated refactoring.
Add a regression test when it meaningfully protects behavior; do not manufacture tests for trivial copy/style/static guarantees.

## 6. Verify

Use `dev-verify` and specifically verify the original symptom or regression test.
If several distinct hypotheses fail and reveal deeper coupling, reassess architecture instead of adding fallback layers.
