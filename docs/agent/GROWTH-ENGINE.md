# Growth Engine

The harness improves from real project evidence without uncontrolled self-modification.

## Separation of concerns

- Raw observations: `.agent-state/growth/observations.jsonl` (local/runtime, gitignored).
- Candidate proposals/snapshots: `.agent-state/growth/` (local/runtime).
- Accepted sanitized history: `agent-core/growth/history.jsonl` (tracked).
- Behavioral regression cases: `agent-core/evals/` (tracked).

## Automatic observations from hook decisions

Hooks log every call the policy does not allow to `.agent-state/hook-log.jsonl` (no argument values or secrets). During a retrospective:

```bash
python3 agent-core/scripts/growth_engine.py ingest-hooks   # retries of a blocked call -> safety/medium; >=5 blocks of one shape -> tooling/low
python3 agent-core/scripts/growth_engine.py hook-stats --days 14
python3 agent-core/scripts/growth_engine.py candidates
```

Ingestion only records observations. A frequent block may be a false positive *or* a correct block the agent keeps hitting; decide which with evidence, add an eval or test that captures it, then follow the normal candidate flow.

## Recording an observation

Example:

```bash
python3 agent-core/scripts/growth_engine.py record \
  --category routing \
  --severity medium \
  --fingerprint dev-plan-overtrigger-small-ui \
  --summary "dev-plan triggered for a one-file spacing change" \
  --evidence "task 42: plan created, no design/contract decision existed"
```

Use stable fingerprints for the same failure pattern so repetition is measurable.

## Candidate thresholds

- critical/high: one occurrence can qualify,
- medium: two occurrences,
- low: three occurrences.

Qualification means "worth evaluating", not "automatically correct".

## Candidate target mapping

- missing/stale project fact → project profile,
- wrong skill trigger → eval + skill description,
- bad task procedure → eval + skill procedure,
- repeatable mechanical waste → script,
- durable general principle → root policy (high-risk),
- dangerous action gap → hook/permission (high-risk).

## Rollback

Before every candidate mutation:

```bash
python3 agent-core/scripts/growth_engine.py snapshot --name <candidate>
```

If regression appears, reject the candidate and restore the snapshot when needed:

```bash
python3 agent-core/scripts/growth_engine.py reject --candidate <fingerprint> --summary "regressed routing" --verification "negative eval failed"
python3 agent-core/scripts/growth_engine.py rollback --snapshot <candidate>.tar.gz
# After reviewing the dry run:
python3 agent-core/scripts/growth_engine.py rollback --snapshot <candidate>.tar.gz --apply --human-reviewed
```

Rollback is deliberately human-reviewed because it overwrites shared harness files. It creates a pre-rollback emergency snapshot first.

## Promotion

After verification:

```bash
python3 agent-core/scripts/growth_engine.py accept \
  --candidate <fingerprint> \
  --target skill-description \
  --summary "narrowed dev-plan trigger to exclude mechanical UI edits" \
  --verification "static checks + 8 routing cases + provider smoke cases passed"
```

For `root-policy`, `safety-hook`, `provider-permission`, or `external-authority`, add `--human-reviewed` only after actual human review.
