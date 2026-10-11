# Installing V4 into a repository that already has agent configuration

`install/apply.py` stops with `MIGRATION REQUIRED` when the target already has its own `AGENTS.md`,
`CLAUDE.md`, `.claude/settings.json`, `.codex/` or `.agents/` files. Those files hold facts about the
project that must not be lost, so they are merged by meaning, not overwritten.

Give the prompt below to an agent (Claude Code, Codex or Antigravity) opened **in the target
repository**, replacing `<HARNESS>` with the path to this harness checkout. Review its diff before
committing.

---

```text
Install the V4 agent harness from <HARNESS> into this repository without losing existing
project knowledge.

1. Run: python3 <HARNESS>/install/apply.py --target .
   It lists the conflicting files. Read each one fully before changing anything.
2. Move every conflicting file to .agent-migration-backup/<same path> (keep the folder layout).
3. Run: python3 <HARNESS>/install/apply.py --target . --apply --create-project-template
   It must finish with "Config check: PASSED".
4. Merge the backed-up originals into the installed V4 files:
   - AGENTS.md / CLAUDE.md: keep V4's policy sections unchanged. Move every project-specific
     fact from the old file (build/test commands, architecture notes, conventions, forbidden
     actions, domain rules) into PROJECT.md or a short "Project specifics" section at the end of
     AGENTS.md. Drop only generic advice V4 already covers, and list what you dropped and why.
   - .claude/settings.json: add back the project's own allow/ask/deny rules, env, MCP and other
     settings. Never remove a V4 deny or ask rule, the hooks block or the sandbox block; if a
     project rule conflicts with one, stop and ask me.
   - .codex/* and .agents/*: add back project entries that do not weaken V4 hooks or sandbox
     settings; ask me about any that would.
5. Run: python3 agent-core/scripts/sync_agent_config.py
        python3 agent-core/scripts/check_agent_config.py
        python3 agent-core/scripts/bootstrap_project.py --write
        python3 agent-core/scripts/install_git_hooks.py
        python3 agent-core/scripts/doctor.py
6. Report: files merged, facts moved and where, anything dropped, and doctor findings.
```
