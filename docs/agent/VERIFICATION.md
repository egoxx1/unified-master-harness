# Package verification — V4

A release is acceptable only when the extracted release tree passes the same checks as the source tree.

Required evidence:

```bash
python3 agent-core/scripts/sync_agent_config.py
python3 agent-core/scripts/check_agent_config.py
python3 -m unittest discover -s agent-core/tests -v
python3 agent-core/scripts/growth_engine.py status
python3 agent-core/scripts/doctor.py --repo-only --strict
python3 agent-core/scripts/upgrade_harness.py --write-manifest   # last step before packaging a template
```

Runtime evidence (needs installed, authenticated CLIs; spends some usage):

```bash
python3 agent-core/scripts/provider_smoke.py          # all three providers, harmless fixtures
python3 agent-core/scripts/run_evals.py --provider claude
python3 agent-core/scripts/codex_hook_probe.py       # Codex hook runtime, no account or usage needed
```

An eval case marked `NOANS` means the agent ended without its final `SKILLS:` line (usually a timeout). It is not a routing result either way: rerun just those cases with `--cases <ids> --timeout 420`.

Local caches (`__pycache__`, `.pytest_cache`, `.DS_Store`, ...) are gitignored and excluded from release ZIPs, so the config check ignores them; the order of these commands does not matter. Hook adapters never write bytecode.

Also validate:

- no `.agents/workflows/` dependency;
- generated `.agents/AGENTS.md` matches canonical root `AGENTS.md` byte-for-byte;
- Claude skill mirrors match canonical skills byte-for-byte;
- safety variants, wrapper/global-option bypasses, external actions and normal development commands are covered by tests;
- the Antigravity hook command resolves the adapter from `.agents/`, the repo root and (inside git) subdirectories, and fails closed elsewhere;
- bootstrap works for Node, Python, and minimal repositories;
- installer applies cleanly and refuses existing conflicting agent configuration;
- temporary worktree create/list/remove works and dirty removal is rejected;
- final ZIP extracts without errors and the extracted tree passes config/unit checks;
- no caches, secrets, absolute user-home paths, or target-project profile is packaged.

Provider smoke definitions are in `agent-core/evals/provider-smoke.md`. A provider is not considered runtime-verified merely because its config file exists.
