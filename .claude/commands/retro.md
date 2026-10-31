---
description: V4 harness retrospective — turn hook decisions into observations and show improvement candidates
disable-model-invocation: true
---

Run from the repository root, in order, and read each output:

1. `python3 -B agent-core/scripts/growth_engine.py ingest-hooks`
2. `python3 -B agent-core/scripts/growth_engine.py hook-stats --days 14`
3. `python3 -B agent-core/scripts/growth_engine.py candidates`

Report to the user, in their language: what was blocked or warned about and how often, each qualified candidate with your assessment of whether it is a false positive or a correct block the agent keeps hitting, and the smallest harness change you would propose for each (eval first, per docs/agent/GROWTH-ENGINE.md). Do not edit any harness file: proposals only. Changes to policy, hooks or permissions need the user's explicit approval.
