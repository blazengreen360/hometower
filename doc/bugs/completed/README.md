# Completed Bug Reports

Archived QA bug reports whose every finding has reached a terminal state (`FIXED`, `SKIPPED`, or `DUPLICATE`) **and** whose remediation diff was approved by Code-Reviewer.

## Archival Rules

- QA-Fixer moves a report here from `doc/bugs/` only when its pipeline verdict is `ALL_CLEAR`.
- Project-Manager may archive a report here if QA-Fixer was bypassed (single-shot surgical fix) and the report is otherwise closed.
- Moves use `git mv` so history is preserved.
- Filenames are never changed on archival.
- Reports with any `OPEN`, `BLOCKED`, or `PARTIAL` finding stay in `doc/bugs/`, not here.
- Archived reports are never deleted — this directory is the historical audit trail.

See the **Report Lifecycle** section in `AGENTS.md` for the full contract.
