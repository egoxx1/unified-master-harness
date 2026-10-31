# Claude Code adapter

@AGENTS.md

The imported root `AGENTS.md` is the canonical shared operating policy. Provider-specific behavior belongs in `.claude/`; do not duplicate the policy here.

Claude Code specifics (enforced by `.claude/settings.json`, not by this text): shell commands and file edits run without prompts and without the sandbox (off by default; `sandbox.enabled` turns it back on); secret files are unreadable; push/publish and edits of harness files (`AGENTS.md`, `CLAUDE.md`, `agent-core/hooks|scripts|evals`, `.codex`, `.agents`) need the user's approval, and the safety hook still denies work-destroying commands. When `dev-review` applies, run it through the `dev-reviewer` subagent so the review has a fresh context.
