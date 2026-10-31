---
description: V4 provider smoke test — prove each installed agent CLI loads the policy and its safety hooks actually block
disable-model-invocation: true
---

Run `python3 -B agent-core/scripts/provider_smoke.py` from the repository root. It runs each installed CLI in a disposable fixture with harmless probes and takes a few minutes; it is listed in the sandbox's excludedCommands because it launches other agent CLIs.

Report to the user, in their language: PASS / FAIL / UNAVAILABLE per CLI with its version, every failed step and what it means, and for UNAVAILABLE the reason (login, usage limit, unsupported model). Do not retry a failing provider in a loop.
