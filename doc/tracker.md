# Engineering Tracker

Items discovered during execution that need attention but don't belong in the product backlog.
Project-Manager reads this at the start of every session. Items graduate to stories (`doc/stories/`), bugs (`doc/bugs/`), or RFCs (`doc/rfc/`) when clarified.

Last updated: 19 April 2026 — resolved T-011 after HT-082 follow-up closeout.

## Open

| ID | Source | Category | Description | Blocked By | Priority | Age (pipelines) |
|---|---|---|---|---|---|---|
| T-002 | HT-052 pipeline | tech-debt | 4 test_auth.py::TestLogin tests fail — passlib bcrypt backend: `module 'bcrypt' has no attribute '__about__'`. Likely bcrypt 4.x + passlib incompatibility. Fix: pin bcrypt<4.1 or migrate to bcrypt directly. | — | MEDIUM | 0 |
| T-005 | HT-031 code-review residual | tech-debt | `src/ui/pages/inventory_page_controller.py` remains high-complexity at 379 lines after cap fix. Schedule targeted decomposition of orchestration methods before next bulk-feature expansion. | — | MEDIUM | 0 |
| T-006 | BUG-HUNT-14-04-26.1 | test-gap | Add a real Postgres concurrent import contention integration test to validate ordered DELETE clear-path behavior under lock pressure; current BUG-001 proof is unit-level only. | — | MEDIUM | 0 |
| T-009 | HT-050 browser validation | follow-up | In browser validation, `HT_READONLY` sometimes flips back to `true` shortly after entering edit mode, likely due to a canvas re-init/personal-draft load race. It did not block the final production-path resize fix, but it is worth a separate targeted investigation because it can interfere with tooling/devtools sessions. | — | LOW | 0 |
|---|---|---|---|---|---|---|

## Resolved

| ID | Resolution | Resolved Via | Date |
|---|---|---|---|
| T-001 | Completed HT-051 follow-up by wiring remove-from-view actions into the shared HT-032 undo stack with local snapshot restore/removal behavior and matching test coverage. | HT-032 canvas undo/redo implementation | 14 Apr 2026 |
| T-003 | Hardened destructive import cleanup to clear newer schema tables in dependency-safe order, added focused regression coverage in `tests/unit/test_import_service.py`, and reran the canonical gate successfully on current HEAD. | Current-head closeout verification and import cleanup remediation | 17 Apr 2026 |
| T-004 | Triaged the untracked `tests/integration/test_critical_paths.py` suite, confirmed the full file passed in isolation, reran the official verify gate, and observed no remaining blocker on current file state. | HT-024 verify-gate triage | 14 Apr 2026 |
| T-007 | Hardened the rebuild/recreate drift surfaces by updating `Dockerfile` ownership/COPY behavior and adding `.dockerignore`, then verified `docker compose build api`, recreate/health, `docker compose exec api mypy src/ --ignore-missing-imports`, and full `docker compose exec api pytest` (`1857 passed, 2 warnings in 208.33s`) on branch state. | HT-078 + T-007 closeout | 18 Apr 2026 |
| T-008 | Added missing PUT support to the shared AsyncClient test stub, restored dashboard/map regression coverage in `tests/unit/test_ui_shell_pages.py`, confirmed canonical verify-gate was green, and unblocked formal HT-068 closeout. | HT-068 gate-failure triage and closeout | 17 Apr 2026 |
| T-010 | Hardened `tests/e2e/test_topology_canvas_deep.py` with stronger login readiness gating, safer evaluation retries, and a longer nested-container settle wait; final Code-Reviewer approval accepted the remaining rapid repeated-run auth-throttle noise as non-blocking to HT-050 closeout. | HT-050 follow-up final closeout | 17 Apr 2026 |
| T-012 | Reordered the `get_device(...)` router signature in `src/api/routers/devices.py` so `Request` precedes defaulted query params, restoring FastAPI app import and unblocking HT-082 dashboard integration/live validation. | HT-082 follow-up verification unblock | 19 Apr 2026 |
| T-013 | Fixed `src/services/canvas_undo_service.py` restore-conflict rollback reachability, corrected devices-router owner scoping, and stabilized `tests/integration/test_devices_include.py` to the owner-scoped model; the subsequent full gate rerun passed (`1893 passed, 2 warnings`, mypy PASS, arch greps PASS, build PASS). | HT-082 gate rerun unblock | 19 Apr 2026 |
| T-011 | Closed the HT-082 follow-up by hardening dashboard owner scoping, recent-device route resolution, legacy no-`Device.owner_id` fallback behavior, and current-layout-only placement / placed-id reads; final current-head verify gate passed (`1918 passed, 2 warnings`, mypy PASS, arch greps PASS, build PASS), focused live validation passed, and dual Code-Reviewer lanes APPROVED. | HT-082 follow-up final closeout | 19 Apr 2026 |

---

## Categories

- `tech-debt` — Code quality issue, missing abstraction, performance concern
- `follow-up` — Incomplete work from a prior pipeline (not a bug, not a story)
- `blocked-bug` — Engineering issue that needs an RFC or architectural decision before it can be fixed
- `infra` — Docker, CI, deployment, migration concern
- `test-gap` — Missing test coverage discovered during review or execution

## Rules

1. **PM owns this file.** Other agents surface issues to PM; PM writes them here.
2. **Items are not stories.** If something has user-facing value, it goes to Product-Owner → `doc/stories/`.
3. **Items are not bugs.** If something is a defect found by QA, it goes to `doc/bugs/`.
4. **Graduation**: When an item is clarified enough, PM creates the appropriate artifact (story/bug/RFC) and moves the tracker item to Resolved.
5. **Staleness**: Items open for >3 pipelines are escalated to the user for triage.
