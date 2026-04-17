# Completed Security Reports

Archived Security-Orchestrator reports whose every finding has reached a terminal state (`FIXED`, `ACCEPTED_RISK`, or `DUPLICATE`) **and** whose remediation diff was approved by Code-Reviewer.

## Archival Rules

- Project-Manager is the sole owner of security-report archival.
- Security-Orchestrator never moves its own reports — if a finding returns after archival, Security-Orchestrator opens a NEW report in `doc/security/` referencing the archived one.
- Moves use `git mv` so history is preserved.
- Filenames are never changed on archival.
- Reports with any `OPEN`, `DEFERRED`, or `BLOCKED` finding stay in `doc/security/`, not here.
- Archived reports are retained for compliance traceability.

See the **Report Lifecycle** section in `AGENTS.md` for the full contract.
