---
description: V4 harness health check (configuration, user-level settings, tracked secrets, CLI versions)
disable-model-invocation: true
---

Run these two commands from the repository root and read their full output:

1. `python3 -B agent-core/scripts/check_agent_config.py`
2. `python3 -B agent-core/scripts/doctor.py`

Then report to the user, in their language: every RISK and WARN finding with its `fix:` line, whether the configuration check passed, and which CLIs have never been smoke-tested or changed since the last smoke test. Do not change any setting yourself; doctor is read-only on purpose.
