# Skill routing evals

These positive/negative cases are used when changing a skill name, description, or root routing rule.

The static checker verifies that referenced skills exist. It cannot prove model routing. For routing changes, run the cases in fresh Codex, Claude Code, and Antigravity sessions and record whether required skills activate and forbidden skills stay inactive.

The important metric is not how many skills fire; it is whether the minimum correct workflow fires without ceremony on unrelated work.

Run each case more than once before trusting a score: `python3 agent-core/scripts/run_evals.py --provider codex --repeat 3`. A case passes only when every run passes; cases that pass only sometimes are reported as unstable.
