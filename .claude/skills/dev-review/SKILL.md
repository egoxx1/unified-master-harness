---
name: dev-review
description: Perform one focused independent review when explicitly requested or when a completed change has high risk involving auth/security, payments, destructive data migration, public API/protocol, concurrency/shared-state, production deployment logic, or large cross-system change. Do not invoke for routine work.
---

# Focused Independent Review

Review concrete correctness and risk, not stylistic preference.

## Scope

Review the complete task diff against requested behavior and existing contracts. Do not turn it into a repository-wide audit.

## High-value checks

Prioritize:
- requirement mismatch,
- data loss or unsafe migration behavior,
- security/trust-boundary mistakes,
- public API/protocol compatibility,
- concurrency, cancellation, retry, cleanup, and shared-state ownership,
- error-path resource leaks,
- persistence/resume mismatches,
- missing verification at the caller-visible boundary,
- UI regressions that contradict the accepted design contract.

## Findings

Every finding must include severity (Critical / Important / Minor), concrete affected path/behavior, why it can fail, evidence, and the narrowest useful fix direction.

Do not report unrelated cleanup, speculative extensibility, equivalent style preferences, or generic requests for more tests without a concrete uncovered failure mode.

Normally perform one cold pass. If fixes are applied, recheck the specific findings and directly affected paths. Do not automatically restart a full review unless fixes materially changed design or blast radius.
