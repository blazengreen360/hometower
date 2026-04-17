---
name: qa-bug-patterns
description: Hometower's proven bug patterns and QA lane-to-file mappings — recurring defects, ODC lane assignments for Bug-Finder fan-out, and the architect's edge case catalog. Read this when hunting bugs, writing proof tests, or designing edge case coverage.
---

# qa-bug-patterns

## Proven Bug Patterns

These have been found before. Check if they've resurfaced or exist in new code:

| Pattern | Where to Look | What to Check |
|---|---|---|
| Missing `try/except IntegrityError` on `session.commit()` | All `*_service.py` | Every `commit()` has rollback + HTTPException? |
| Validator on `Base` but not on `Update` | All `src/models/*.py` | Does `*Update` redeclare fields — if so, inherits validators? |
| Router with direct DB access | All `src/api/routers/*.py` | Any `session.exec()` or `session.execute()` in a router? |
| Falsiness trap (`or ""` on `0.0`) | UI pages with form pre-fill | Does `value or ""` erase falsy-but-valid inputs? |
| Missing cascade on FK deletion | All models with `foreign_key=` | FK has `ondelete="CASCADE"` where needed? |
| Silent no-op (succeeds but did nothing) | Delete/remove service methods | Method verifies entity existed before returning success? |
| Duplicate event handlers in canvas JS | `canvas_js.py`, `canvas_events.py` | Same event registered in multiple files? |
| Log leaking PII | `auth_service.py`, all `logger.*` calls | Email or IP in failure-path logs? |

## QA Orchestrator ODC Lane Assignments

| Lane | ODC Focus | Target Scope |
|---|---|---|
| lane-1 | Function (Input/Output) | `src/models/`, Pydantic validators, IP/MAC/Enum edge cases |
| lane-2 | Assignment (State) | `src/repositories/`, session lifecycle, transaction bounds |
| lane-3 | Checking (Errors) | `src/services/`, missing `try/except IntegrityError`, 500 leaks |
| lane-4 | Timing/Serialization | TOCTOU races, sync-in-async, last-write-wins diagram saves |
| lane-5 | Function (Auth/RBAC) | `src/api/middleware/auth.py`, JWT bypass, missing `require_role()` |
| lane-6 | Function (Integrity) | Device/Connection orphans, missing cascades, export/import data loss |
| lane-7 | Documentation (Logs) | PII in `logger.*`, misleading error messages |
| lane-8 | Interface (Architecture) | Layer boundary drift: routers with DB queries, UI importing repos |
| lane-9 | Algorithm (Canvas UI) | `src/ui/components/canvas*.py`, event duplication, layout persistence |
| lane-10 | Algorithm (Domain) | `src/domain/`, pure logic invariants, falsiness traps |

## Edge Case Catalog (from Architect)

Every RFC and test plan must address these categories:

1. **Empty state** — zero entities (empty inventory, no connections, no tags)
2. **Boundary values** — max name length, extreme coordinates, UUID collisions, zero-page pagination
3. **Concurrent access** — two users editing same entity, optimistic locking (`version` field)
4. **Cascade effects** — entity deleted, what happens to children/dependents?
5. **RBAC per operation** — which role can create/read/update/delete? Reader vs contributor view?
6. **Round-trip integrity** — export to JSON and re-import, does every field survive?
7. **Canvas impact** — entity on topology canvas, how do Cytoscape elements change?
8. **Performance at scale** — 500 devices, 1000 connections, 50 nested containers

## Boundary Values Reference

| Input | Boundary Values |
|---|---|
| IP | `""`, `"256.0.0.0"`, `"255.255.255.255"`, `"0.0.0.0"`, `"not-an-ip"`, `"::1"` |
| Coordinates | lat `90.0`, `90.1`, `-90.1`, `0.0` (falsy-but-valid) |
| Device name | `""`, `"   "`, 1 char, 255 chars, 256 chars |
| Port | `0`, `1`, `65535`, `65536` |
| Version | `0`, `1`, negative |
| Pagination | `page=1, limit=1`, `page=0`, `limit=0` |
