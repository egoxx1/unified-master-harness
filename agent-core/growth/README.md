# Controlled Harness Growth

Raw task observations are runtime state and live under `.agent-state/growth/`; they are not committed by default.
Accepted improvements are recorded in `agent-core/growth/history.jsonl` without sensitive task data.

## What qualifies

A change candidate is created when:
- one critical/high-severity harness failure is observed, or
- a medium issue repeats twice, or
- a low-severity inefficiency repeats three times.

Examples:
- the agent repeatedly rediscovers a stable command,
- a simple task repeatedly triggers `dev-plan`,
- UI verification repeatedly misses horizontal overflow,
- a safety boundary failed once in a way that could destroy data.

One unusual, harmless mistake is evidence to record, not a reason to grow the harness.

## Promotion loop

1. **Observe** — record the concrete failure/waste and evidence.
2. **Qualify** — the engine groups repeated fingerprints and applies thresholds.
3. **Propose** — identify root cause and the narrowest target: project profile, eval, skill, script, policy, hook, provider config.
4. **Eval first** — add/update a positive or negative case that would have caught the problem when practical.
5. **Snapshot** — snapshot the current harness.
6. **Mutate minimally** — make the smallest candidate change, preferably in an isolated branch/worktree.
7. **Verify** — run config/unit tests and relevant fresh-session routing/behavior evals.
8. **Compare** — confirm the targeted issue improved without meaningful regression.
9. **Promote or reject** — keep the patch only if evidence supports it; record the result.

## Promotion authority

Low/medium changes can be prepared and locally validated automatically. They still flow through the normal project diff/PR process when committed.

Changes to any of these require human review before promotion:
- root `AGENTS.md` policy,
- safety hooks,
- provider permissions/sandbox,
- push/merge/deploy/publish authority,
- credential/trust boundaries.

The engine must never weaken safety just to reduce friction.
