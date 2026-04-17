# Bug Report 14-04-26.1

## Executive Summary
| Severity | Count |
|---|---|
| Critical | 0 |
| High | 1 |
| Medium | 2 |
| Low | 0 |
| **Total** | **3** |

Pipeline Verdict: ALL_CLEAR — all findings remediated and verified.

## Final Status
| ID | Severity | Status | Remediation |
|---|---|---|---|
| BUG-001 | High | FIXED | Replaced PostgreSQL `TRUNCATE ... CASCADE` clear path with ordered `DELETE FROM` operations in [src/services/import_service.py](src/services/import_service.py). Added regression guard in [tests/unit/test_import_service.py](tests/unit/test_import_service.py). |
| BUG-002 | Medium | FIXED | Expanded restore conflict mapping for Postgres and SQLite message forms in [src/services/canvas_undo_service.py](src/services/canvas_undo_service.py). Added proof coverage in [tests/unit/test_canvas_undo_restore_conflict.py](tests/unit/test_canvas_undo_restore_conflict.py). |
| BUG-003 | Medium | FIXED | Removed per-user bcrypt hashing by computing one sentinel hash per import operation in [src/services/import_service_rows.py](src/services/import_service_rows.py). Added call-count regression in [tests/unit/test_import_service_rows_sentinel_hash.py](tests/unit/test_import_service_rows_sentinel_hash.py). |

## Verification Evidence
- Targeted tactical tests:
  - `tests/unit/test_canvas_undo_restore_conflict.py` PASS
  - `tests/unit/test_import_service_rows_sentinel_hash.py` PASS
  - `tests/unit/test_import_service.py` PASS (includes no-TRUNCATE assertion)
- Full pre-push gate PASS after remediations:
  - `pytest`: 1660 passed
  - `mypy`: success (205 source files)
  - `arch-grep`: pass
  - `docker compose build`: pass
- Final Code-Reviewer verdict: APPROVED (scoped remediation review).

## Residual Risks
1. BUG-001 lock-risk mitigation is validated at unit level; no concurrent Postgres contention simulation test exists yet.
2. BUG-002 conflict mapping remains pattern-based; new/unexpected constraint naming may still fall back to generic conflict copy.

## Follow-up Recommendation
- Add a dedicated integration test that exercises import behavior under concurrent Postgres write load to validate lock contention characteristics in CI-like conditions.
