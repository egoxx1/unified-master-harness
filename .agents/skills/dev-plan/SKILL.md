---
name: dev-plan
description: Create a compact product/implementation spec for large, cross-subsystem, migration, architecture, public-contract, significant UX, or materially ambiguous changes before coding. Do not use for small or ordinary localized work.
---

# Development Spec and Plan

Use this skill when a wrong interpretation would be expensive or hard to unwind.

## Goal

Give the human a short document they can review without needing to read code, then give the implementing agent the decisions it cannot safely infer.
Do not turn the plan into a transcript of obvious coding steps.

## 1. Product contract

Capture:

```markdown
## Goal
What changes for the user/system and why.

## Acceptance criteria
Concrete observable outcomes.

## Must preserve
Existing behavior/contracts that cannot regress.

## Out of scope
Tempting adjacent work intentionally excluded.

## Open product decisions
Only choices that would lead to materially different outcomes.
```

If `PROJECT.md` applies, align with it explicitly.
If open product decisions materially change the result, get human confirmation before implementation. Otherwise proceed.

## 2. Technical plan

Inspect affected architecture and record only decisions that matter:

```markdown
## Existing contracts / constraints
## Files and interfaces affected
## Decisions and rationale
## Implementation order
## Verification plan
## Risks / rollback (only when relevant)
```

For long or multi-session work, save to `docs/agent/plans/` or the repository's existing spec system.
For work that will finish in the current session, a compact task artifact under `.agent-state/<task>/` is sufficient.

## Rules

- No speculative extension points.
- Prefer vertical, independently verifiable slices.
- Do not force TDD for copy/styling/static configuration.
- A plan longer than the decisions it captures is too detailed.
- A vague line such as "handle edge cases" is not a decision; name the actual behavior or omit it.
- Planning does not authorize push, merge, deploy, publish, or destructive operations.
