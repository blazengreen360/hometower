# HT-082 Follow-Up Progress — Dashboard Semantic Remediation

**Story:** HT-082 follow-up (review remediation)
**Started:** 19 Apr 2026
**Status:** Done

## Work Plan (CPM)

Critical path:
1. QA-Fixer reproduces the review findings fail-first with focused regressions
2. QA-Fixer corrects dashboard aggregation scope and recent-activity routing semantics
3. User-Simulator validates the real dashboard click paths and scoped totals in the live app
4. CI-Gatekeeper runs mandatory gates on the reviewed scope
5. Code-Reviewer lane A and lane B independently review against the passing gate report

Parallelizable work:
- Code-Reviewer A and Code-Reviewer B can run in parallel only after User-Simulator passes and CI-Gatekeeper returns a passing current-pipeline report.

## Bundle Progress
| # | Bundle | Agent | Status | Notes |
|---|---|---|---|---|
| B1 | Reproduce dashboard defects | QA-Fixer | Completed | Added focused fail-first proofs in `tests/unit/test_dashboard_repository.py` and route-opacity guard coverage in `tests/unit/test_dashboard_page.py`; preserved architect-confirmed workspace aggregate scope semantics. |
| B2 | Patch dashboard semantics | QA-Fixer | Completed | QA-Fixer reconciled the live/runtime discrepancy by handling live schema compatibility in `src/repositories/dashboard_repository_support.py`; the previously failing recent device item now resolves to a concrete scoped topology route in the live app. |
| B3 | Validate live dashboard flows | User-Simulator | Completed | Focused live recheck passed after the devices-router regression fix: dashboard loaded, recent-device click-through landed on the intended scoped topology route, and no environment blocker was observed. Residual evidence gap remains only for a recent topology item not being visible during the rerun. |
| B4 | Run mandatory gates | CI-Gatekeeper | Completed | Final current-head verify gate PASS: `pytest` (`1918 passed, 2 warnings`), `mypy` PASS, architecture greps PASS, and `docker compose build` PASS. |
| B5 | Review lane A | Code-Reviewer | Completed | Final approval on current HEAD after the last placed-ids owner-scope fix; no remaining blockers. |
| B6 | Review lane B | Code-Reviewer | Completed | Final approval on current HEAD after the last placed-ids owner-scope fix; no remaining blockers. |

## Decisions
- Treat HT-082 review findings as an active follow-up remediation pipeline, not a new backlog story.
- Keep scope bounded to dashboard aggregation semantics, dashboard-to-resource routing, and the corresponding proof tests.
- Architect ruling (19 Apr 2026): workspace-scoped HT-082 aggregates should remain aligned to devices present in the current published topology state for the selected workspace, not all unplaced owner-visible devices; unplaced devices belong only in `All Workspaces` until a separate workspace-device ownership model exists.
- Architect ruling (19 Apr 2026): recent-activity device links must resolve to a concrete resource. Preferred route is `/topology?workspace_id=<workspace_id>&topology_id=<topology_id>&device_id=<device_id>` when the device has a qualifying current published placement in scope; otherwise fall back to `/inventory/edit/<device_id>`.
- Architect ruling (19 Apr 2026): no standalone RFC is required; proceed with direct remediation plus stronger semantic proof tests.

## Blockers
- Final verify truth on current HEAD: dashboard load PASS, recent-device click-through PASS, inventory load PASS, delete-confirmation placement count PASS (`1 topology diagram(s)`), full gate PASS, dual Code-Reviewer approval PASS.

## Blockers
- None.
