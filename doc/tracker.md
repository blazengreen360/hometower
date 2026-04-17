# Engineering Tracker

Items discovered during execution that need attention but don't belong in the product backlog.
Project-Manager reads this at the start of every session. Items graduate to stories (`doc/stories/`), bugs (`doc/bugs/`), or RFCs (`doc/rfc/`) when clarified.

Last updated: 17 April 2026 — resolved T-008 after gate-failure triage and closeout; added T-009 for edit-mode race follow-up; updated T-007 after current-head gate repair; added T-010 for residual HT-050 deep-proof warm-run flake.

## Open

| ID | Source | Category | Description | Blocked By | Priority | Age (pipelines) |
|---|---|---|---|---|---|---|
| T-002 | HT-052 pipeline | tech-debt | 4 test_auth.py::TestLogin tests fail — passlib bcrypt backend: `module 'bcrypt' has no attribute '__about__'`. Likely bcrypt 4.x + passlib incompatibility. Fix: pin bcrypt<4.1 or migrate to bcrypt directly. | — | MEDIUM | 0 |
| T-005 | HT-031 code-review residual | tech-debt | `src/ui/pages/inventory_page_controller.py` remains high-complexity at 379 lines after cap fix. Schedule targeted decomposition of orchestration methods before next bulk-feature expansion. | — | MEDIUM | 0 |
| T-006 | BUG-HUNT-14-04-26.1 | test-gap | Add a real Postgres concurrent import contention integration test to validate ordered DELETE clear-path behavior under lock pressure; current BUG-001 proof is unit-level only. | — | MEDIUM | 0 |
| T-007 | HT-071 / HT-044 / current-head closeout | infra | Current-head closeout repaired the live gate runtime and restored a full green canonical gate, but the underlying drift risk remains: `requirements.txt` does not declare `passlib`, `Dockerfile` applies ownership before `COPY`, and there is no `.dockerignore`, so rebuild/recreate can likely reintroduce missing `passlib` and root-owned `.mypy_cache`. Fix this as a dedicated infra-hardening pass. | — | MEDIUM | 1 |
| T-009 | HT-050 browser validation | follow-up | In browser validation, `HT_READONLY` sometimes flips back to `true` shortly after entering edit mode, likely due to a canvas re-init/personal-draft load race. It did not block the final production-path resize fix, but it is worth a separate targeted investigation because it can interfere with tooling/devtools sessions. | — | LOW | 0 |
| T-010 | HT-050 follow-up closeout | test-gap | `tests/e2e/test_topology_canvas_deep.py` now has the auth race fixed and recoverable Playwright evaluation retries, but repeated warm runs still show an intermittent resize-proof timing failure (`nested container valid resize did not produce a measurable change (after wait)`). Product behavior and the canonical gate are currently green, so stabilize this as a separate deep-proof hardening pass rather than reopening the resize bug itself. | — | LOW | 0 |
|---|---|---|---|---|---|---|

## Resolved

| ID | Resolution | Resolved Via | Date |
|---|---|---|---|
| T-001 | Completed HT-051 follow-up by wiring remove-from-view actions into the shared HT-032 undo stack with local snapshot restore/removal behavior and matching test coverage. | HT-032 canvas undo/redo implementation | 14 Apr 2026 |
| T-003 | Hardened destructive import cleanup to clear newer schema tables in dependency-safe order, added focused regression coverage in `tests/unit/test_import_service.py`, and reran the canonical gate successfully on current HEAD. | Current-head closeout verification and import cleanup remediation | 17 Apr 2026 |
| T-004 | Triaged the untracked `tests/integration/test_critical_paths.py` suite, confirmed the full file passed in isolation, reran the official verify gate, and observed no remaining blocker on current file state. | HT-024 verify-gate triage | 14 Apr 2026 |
| T-008 | Added missing PUT support to the shared AsyncClient test stub, restored dashboard/map regression coverage in `tests/unit/test_ui_shell_pages.py`, confirmed canonical verify-gate was green, and unblocked formal HT-068 closeout. | HT-068 gate-failure triage and closeout | 17 Apr 2026 |

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
