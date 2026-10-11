---
name: dev-verify
description: Verify a code, config or schema change (including refactors and performance work meant to keep behavior the same) before claiming it is complete, fixed, or passing. Select the narrowest evidence that proves the affected behavior, escalating only when blast radius requires it. Not for text-only or docs-only edits.
---

# Verification Before Completion

Evidence before claims.

## Gate

Before a completion claim:

1. Identify the observable evidence that proves the requested outcome.
2. Run the relevant check fresh after the final relevant change.
3. Read output and exit status.
4. Confirm the check actually covered the affected behavior.
5. Report the real result, including failures or material unverified areas.

## Verification ladder

Start with the cheapest check that directly proves behavior:

1. focused reproduction or test,
2. affected integration test,
3. typecheck/lint for affected scope,
4. relevant build,
5. runtime/service verification,
6. broader suite when shared infrastructure or contract blast radius justifies it.

A linter does not prove a build. A build does not prove the original bug is fixed. Unrelated passing tests do not prove requirements were met.

## Avoid redundant execution

For expensive commands, capture useful output once and inspect/search the captured result instead of rerunning unchanged work.
Rerun only after a relevant change or when a new proof requires execution.

If the task materially changed user-facing UI, use `dev-ui-verify` and include its result in completion evidence.
