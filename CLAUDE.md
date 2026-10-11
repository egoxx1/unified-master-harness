# Claude Code adapter

@AGENTS.md

The imported root `AGENTS.md` is the canonical shared operating policy. Provider-specific behavior belongs in `.claude/`; do not duplicate the policy here.

Claude Code specifics (enforced by `.claude/settings.json`, not by this text): shell commands run in a sandbox that can write only inside this project and common package caches; secret files are unreadable; harness files (`AGENTS.md`, `CLAUDE.md`, `agent-core/hooks|scripts|evals`, `.codex`, `.agents`) need the user's approval to edit and cannot be written from the shell. When `dev-review` applies, run it through the `dev-reviewer` subagent so the review has a fresh context.
