# Security

## What the harness does and does not promise

The hooks block a defined set of dangerous commands, secret-file reads, external actions and writes
to the harness itself, on Claude Code, Codex and Antigravity. It is a narrow guard, not a shell
firewall: known gaps are listed in `docs/VERIFICATION-REPORT.md`. The Codex workspace sandbox adds OS-level limits;
the Claude Code sandbox is off by default and adds them only when enabled; Antigravity has no sandbox layer in V4.

Do not keep production secrets in files an agent can reach. Inject them at run time from a secret
manager or keychain.

## Reporting a bypass

If you find a command that should be blocked but is not, or a way to read a protected file:

1. Do not open a public issue with a working bypass. Use GitHub's private vulnerability reporting
   (Security tab → "Report a vulnerability") on this repository.
2. Include the provider and CLI version, the exact command or tool call, what you expected and what
   happened, and whether the hook log (`.agent-state/hook-log.jsonl`) recorded it.
3. Test only in a disposable repository. Never test destructive probes against real data.

Fixes for confirmed bypasses get a regression test and a changelog entry.
