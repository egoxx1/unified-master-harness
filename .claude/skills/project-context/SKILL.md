---
name: project-context
description: Establish or refresh verified project commands, runtime facts, and repository layout when those facts are unknown, stale, or explicitly requested. Do not use for routine tasks when the existing project profile already answers the question.
---

# Project Context

Use this skill to avoid rediscovering stable project facts every session.

## Trigger

Use when:
- first bootstrapping this environment in a repository,
- `agent-core/project/profile.md` is missing,
- commands/runtime facts are stale or contradicted by the repository,
- a task depends on a project fact that the profile does not establish.

Do not run it ritualistically before every edit.

## Procedure

1. Read `agent-core/project/profile.md` if present.
2. If the needed fact is present and still consistent with the relevant files, use it.
3. Otherwise run:

   ```bash
   python3 agent-core/scripts/bootstrap_project.py --write
   ```

4. Inspect only source files needed to resolve remaining unknowns: manifests, lockfiles, task-runner files, compose files, relevant README/AGENTS files, and CI workflows when CI behavior matters.
5. Record only facts supported by repository evidence or a command actually run.
6. Leave unknown values unknown rather than filling conventional defaults.

Keep the profile compact. Never store secrets or environment values.
