# Source-to-rule map

This environment does not copy one AGENTS.md/CLAUDE.md wholesale. It extracts useful ideas, removes provider/person-specific assumptions, and places each idea at the correct layer.

| Source | Adopted | Deliberately rejected |
|---|---|---|
| Karpathy-inspired `CLAUDE.md` | simplicity, no speculative features, surgical changes, verifiable goals | mandatory clarification for every uncertainty |
| OpenAI `codex/AGENTS.md` | repository-native commands, targeted tests, context discipline, existing abstractions | Rust/Bazel/TUI-specific conventions |
| OpenAI Agents SDK `AGENTS.md` | secrets, trust boundaries, dependency/security evidence | SDK release-specific process |
| OpenAI skill-eval guidance | positive/negative routing cases, eval-before-tuning, regression comparison | feeling-based prompt tuning without measurements |
| OpenAI GPT-6 Astra skill/prompt guidance | smaller always-on context, selective skills, less scaffolding | accumulated prompt bloat |
| Vercel Next.js `AGENTS.md` | focused checks, capture expensive test output once and reuse it | Next.js-specific build/test commands |
| jbarbier `CLAUDE.md` | small/medium/large triage, smaller-first escalation, worktree writer isolation, deterministic automation | mandatory printed triage, fan-out/tournaments, always-push workflow |
| Superpowers | root-cause debugging, single-hypothesis experiments, evidence-before-completion, proportionate planning | default subagent-driven development, mandatory TDD for all work, repeated reviewer loops |
| Addy Osmani agent-skills | UI quality, anti-generic-AI defaults, accessibility baseline, significant-change spec routing | fixed human approval gates for every phase |
| Claude/Antigravity official docs | current context/skill/hook layering and progressive disclosure | undocumented compatibility assumptions |

Exact researched source blob SHAs are pinned in `agent-core/sources.lock.json` where a GitHub source was used.
