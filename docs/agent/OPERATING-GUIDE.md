# Operating Guide — Human + AI Development

This environment is designed so a non-specialist project owner can control **intent, acceptance, risk, and merge decisions** while AI handles most implementation mechanics.

## Human responsibilities

1. Define what outcome is wanted.
2. Review/approve the product spec for large or subjective changes.
3. Judge the actual finished behavior/UI.
4. Approve high-risk boundaries and merge/release decisions.

You do not need to line-review every implementation detail. For important code, ask the agent to explain: previous behavior, new behavior, why the chosen ownership boundary is correct, likely failure mode, and evidence.

## AI responsibilities

- inspect relevant repository context,
- produce a compact spec/plan when warranted,
- implement,
- write/use appropriate tests,
- debug root causes,
- self-check,
- run development QA,
- perform browser QA for UI,
- prepare QA evidence and PR body,
- request one fresh review for high-risk changes,
- record harness-growth observations only when justified.

## Normal task flow

```text
Request
  ↓
Small? ── yes → implement → targeted verify → handoff
  │
  no
  ↓
Medium / Large
  ↓
Product acceptance criteria / dev-plan when needed
  ↓
Human checks intent only when the outcome is materially subjective/high-impact
  ↓
Primary AI implements
  ↓
AI tests/debugs/self-checks
  ↓
AI QA (+ browser QA for UI)
  ↓
High-risk? → one fresh review
  ↓
QA report + PR body
  ↓
Human acceptance
  ↓
CI / PR approval / merge
```

## What to review as a non-developer

For a PR, focus on:

1. **Intent** — is this actually what you asked for?
2. **Behavior** — do important existing flows still work?
3. **Evidence** — what tests/build/browser checks actually ran?
4. **Risk** — did it touch auth, money, data migration, public APIs, concurrency, deploy/release logic?
5. **Visual result** — for UI, is the real desktop/mobile result good?

For high-risk PRs, require `dev-review` from a fresh context/agent before your final approval.

## Harness evolution cadence

Do not tune the harness from intuition after every task.

- Record repeated friction during real work.
- Run a harness retrospective through the Growth Engine after several tasks, or immediately after a serious harness failure.
- Promote only eval-backed improvements.
- Keep high-risk policy/safety changes human-reviewed.

A good cadence is **after 3–5 meaningful tasks**, unless a critical issue justifies immediate review.
