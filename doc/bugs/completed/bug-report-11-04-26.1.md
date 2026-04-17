# Bug Report 11-04-26.1

## QA Remediation Ledger

| Bug ID | Status | Root Cause | Fix (lines) | Tests Added |
|---|---|---|---|---|
| BUG-1101-01 | FIXED | Export/import wire schema and service orchestration never included `services` or `service_dependencies`, so snapshot assembly and restore logic silently dropped those entities. | 54 | 1 |
| BUG-1101-02 | FIXED | Diagram update and patch flows performed optimistic-lock checks on an unlocked row, letting concurrent writers evaluate the same version before either transaction committed. | 44 | 2 |
| BUG-1101-04 | FIXED | `_clear_all_tables()` omitted `service_dependencies` and `services`, leaving dependent rows behind and causing re-import FK failures. | 8 | 0 |
| BUG-1101-17 | FIXED | Diagram write operations called `session.commit()` without `IntegrityError` handling, so transaction failures leaked and sessions were left dirty without rollback. | 29 | 2 |
| BUG-1101-20 | FIXED | `import_full_snapshot()` lacked pre-insert referential validation for `device.location_id` against payload locations, so dangling references were accepted (SQLite) or deferred to DB constraints. | 17 | 1 |
| BUG-1101-33 | FIXED | Diagram delete/timestamp-touch read mutable rows without row locks, leaving a TOCTOU window between fetch and write/delete in concurrent requests. | 8 | 0 |
| BUG-1101-05 | FIXED | `device_service.update()` (and `create()`) called `session.commit()` without `IntegrityError` handling, so conflicts leaked as 500 and left the transaction unrolled back. | 15 | 1 |
| BUG-1101-06 | FIXED | `connection_service.update()` committed outside a guarded `IntegrityError` path, so write conflicts escaped as raw DB errors. | 9 | 1 |
| BUG-1101-07 | FIXED | `location_service.update()` committed without rollback-on-integrity failure, leaking ORM exceptions and dirty sessions. | 7 | 1 |
| BUG-1101-09 | FIXED | `service_service.add_dependency()` re-raised unmapped `IntegrityError`, exposing backend SQL details through 500 responses. | 3 | 1 |
| BUG-1101-10 | FIXED | `connection_service.create()` re-raised unmapped `IntegrityError`, leaking SQLAlchemy internals instead of a clean API error. | 3 | 1 |
| BUG-1101-21 | FIXED | `service_service.remove_dependency()` treated missing edges as idempotent no-op, violating API semantics that require explicit not-found feedback. | 3 | 1 |
| BUG-1101-29 | FIXED | `service_service.remove_dependency()` logged successful removal even when nothing was deleted because existence was never checked. | 2 | 1 |
| BUG-1101-16 | FIXED | `require_role()` directly coerced untrusted JWT role claims via `Role(...)`, allowing invalid claims to raise `ValueError` and bubble as 500 instead of a guarded 403 deny. | 12 | 1 |
| BUG-1101-22 | FIXED | `authenticate()` wrote user-supplied email values to WARNING logs on invalid credentials, exposing account-enumeration data to log readers. | 1 | 0 |
| BUG-1101-23 | FIXED | Disabled-account login warnings logged raw email addresses, unnecessarily persisting identifying data in auth failure logs. | 1 | 0 |
| BUG-1101-30 | FIXED | First-boot admin creation INFO logs included the configured admin email, leaking PII in normal startup logs. | 1 | 0 |
| BUG-1101-11 | FIXED | `ConnectionBase` and DB schema had no enforced `source_id != target_id` invariant in the active model/migration path, so self-loop payloads were accepted pre-service validation. | 16 | 1 |
| BUG-1101-12 | FIXED | `DeviceUpdate` redeclared `ip` without a field validator, so PATCH schema validation diverged from `DeviceBase` and relied on downstream service checks. | 10 | 1 |
| BUG-1101-13 | FIXED | `UserBase` and `UserUpdate` lacked username trimming/non-empty enforcement and email format validation, allowing malformed identity data through request models. | 46 | 2 |
| BUG-1101-27 | FIXED | `Location.row` validator rejected only empty/negative-numeric values and did not reject punctuation-only strings like `---`. | 9 | 1 |
| BUG-1101-28 | FIXED | `Location.rack` had no validator, so whitespace-only values were persisted instead of being normalized to null/clean strings. | 12 | 2 |
| BUG-1101-03 | FIXED | Canvas `dragfree` handler only wrote positions to browser memory (`window._htNodePositions`); no server persistence until manual Save Layout click. | 45 | 4 |
| BUG-1101-08 | FIXED | Duplicate `cy.on('tap', 'node', ...)` handlers in `canvas_js.py` and `canvas_events.py` both fired on every node click with non-deterministic order. | 8 | 0 |
| BUG-1101-14 | FIXED | `system.py` router executed 6 DB count queries and 2 raw SQL calls inline, bypassing the service layer entirely. | 90 | 12 |
| BUG-1101-15 | FIXED | `settings_locations.py` `or ""` fallback replaced falsy `0.0` lat/lng with empty string on edit modal, breaking equator/prime-meridian coordinates. | 6 | 2 |
| BUG-1101-18 | ROUTED_ELSEWHERE | Sync `session.commit()` calls inside `async def` handlers block the event loop under concurrent load. Systemic refactor deferred to Product-Owner story. | 0 | 0 |
| BUG-1101-19 | FIXED | `topology_data.py` loaded stale Cytoscape node references from saved layouts without filtering against current device IDs. | 12 | 1 |
| BUG-1101-24 | FIXED | `health.py` performed `SELECT 1` DB connectivity probe inline in the router handler instead of delegating to a service. | 15 | 2 |
| BUG-1101-25 | FIXED | `services.py` router `add_service_dependency` declared `response_model=SQLModel` but returned `dict[str, str]`, causing Pydantic serialization mismatch. | 1 | 0 |
| BUG-1101-26 | FIXED | Canvas node-delete success path called `window._cy.getElementById(d.id).remove()` without verifying the element existed in the graph. | 4 | 0 |
| BUG-1101-31 | FIXED | `inventory.py::_on_search` event handler parameter had no type annotation. | 1 | 0 |
| BUG-1101-32 | FIXED | `canvas_tooltip.py` service status lookup tolerated whitespace/case mismatches by accident instead of normalizing explicitly. | 2 | 0 |

Pipeline Verdict: ALL_CLEAR — 32 fixed, 0 open, 1 routed elsewhere (BUG-1101-18 → Product-Owner story).

**Generated by:** QA-Orchestrator
**Date:** 2026-04-11
**Audit scope:** Full Hometower codebase (`src/`)
**Lanes dispatched:** 10/10
**Lanes returned:** 10/10

---

## Executive Summary

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 16 |
| Medium | 12 |
| Low | 4 |
| **Total (deduplicated)** | **33** |

### Top 3 risks

1. **[BUG-1101-01 — Critical]** `services` and `service_dependencies` tables are entirely omitted from the export/import pipeline. A full backup → restore cycle silently loses every service and dependency edge in the database. The `_clear_all_tables()` TRUNCATE statement also omits these tables, so a second import will fail with a foreign-key violation. Combined: data loss on first restore, broken pipeline on second. Files: `src/services/export_service.py:57`, `src/services/import_service.py:42`, `src/models/export_schema.py:92`.

2. **[BUG-1101-02 — High]** Diagram save uses an in-Python read-modify-write version check (`diagram_service.update()` and `partial_update()`), creating a TOCTOU window where two concurrent saves both pass the version guard, both increment to `v+1`, and the second commit silently overwrites the first. Last-write-wins is the documented v1 strategy — but this implementation loses work *even when both clients meant well*, because both transactions see the same baseline before either writes. Files: `src/services/diagram_service.py:38, 84`.

3. **[BUG-1101-03 — High]** Canvas drag-free position updates are written only to `window._htNodePositions` in browser memory; nothing persists to the server until the user clicks **Save Layout**. A user who repositions 20 nodes and closes the tab loses every change with no warning. Combined with the absence of an autosave debouncer, this is the highest-likelihood data-loss path in the UI. File: `src/ui/components/canvas_js.py:128`.

### Coverage notes

- All 10 ODC lanes returned within scope.
- 1 cross-lane duplicate merged (device + connection update rollback finding from lane 3 collapsed into lane 2).
- One lane-3 finding (`device_service.update` missing IntegrityError handling) and one lane-2 finding (`device_service.update` missing rollback) reference the same code path with the same fix — see Duplicate Merge Log.
- Two findings depend on each other (BUG-1101-01 and the export-related half of BUG-1101-04) and should be fixed together.

---

## Prioritized Findings

`risk_score = impact + exploitability + likelihood + blast_radius + confidence` (each 1–5)

| ID | Sev | Score | Title | File:Line |
|---|---|---|---|---|
| BUG-1101-01 | Critical | 25 | Services/service_dependencies missing from export+import | `src/services/export_service.py:57` |
| BUG-1101-02 | High | 22 | Diagram save TOCTOU race in `update()` and `partial_update()` | `src/services/diagram_service.py:38, 84` |
| BUG-1101-03 | High | 22 | Canvas drag positions never persisted to server | `src/ui/components/canvas_js.py:128` |
| BUG-1101-04 | High | 20 | `_clear_all_tables()` TRUNCATE omits services/service_dependencies → FK violation on re-import | `src/services/import_service.py:42` |
| BUG-1101-05 | High | 19 | `device_service.update()` commits without try/except + rollback | `src/services/device_service.py:198` |
| BUG-1101-06 | High | 19 | `connection_service.update()` commits without try/except + rollback | `src/services/connection_service.py:118` |
| BUG-1101-07 | High | 19 | `location_service.update()` commits without try/except + rollback | `src/services/location_service.py:140` |
| BUG-1101-08 | High | 18 | Duplicate Cytoscape `tap` `node` handlers (canvas_js.py + canvas_events.py) | `src/ui/components/canvas_js.py:90` |
| BUG-1101-09 | High | 18 | `service_service.add_dependency()` bare `raise` leaks IntegrityError as 500 | `src/services/service_service.py:195` |
| BUG-1101-10 | High | 18 | `connection_service.create()` bare `raise` leaks IntegrityError as 500 | `src/services/connection_service.py:48` |
| BUG-1101-11 | High | 17 | `Connection` model accepts self-loop (`source_id == target_id`) | `src/models/connection.py:15` |
| BUG-1101-12 | High | 17 | `DeviceUpdate` accepts invalid IPs (PATCH bypasses validator on `DeviceBase`) | `src/models/device.py:75` |
| BUG-1101-13 | High | 17 | `UserBase` lacks validators for `username` and `email` | `src/models/user.py:20` |
| BUG-1101-14 | High | 16 | `system.py` router executes DB queries directly, bypassing service layer | `src/api/routers/system.py:49` |
| BUG-1101-15 | High | 16 | `settings_locations.py` `or ""` fallback erases falsy `0.0` lat/lng on edit | `src/ui/pages/settings_locations.py:114` |
| BUG-1101-16 | High | 14 | `require_role()` `Role(...)` ValueError on bad enum claim → 500 not 403 | `src/domain/rbac.py:31` |
| BUG-1101-17 | High | 14 | `diagram_service` write paths commit without try/except + rollback | `src/services/diagram_service.py:13, 38, 72` |
| BUG-1101-18 | Medium | 13 | Sync `session.commit()` calls inside `async def` handlers (event-loop blocking) | `src/api/routers/diagrams.py:52` (systemic) |
| BUG-1101-19 | Medium | 12 | `cytoscape_json` references device IDs that are not cascade-cleaned on device delete | `src/models/diagram.py:18` |
| BUG-1101-20 | Medium | 12 | Import does not pre-validate `device.location_id` against payload locations | `src/services/import_service.py:99` |
| BUG-1101-21 | Medium | 12 | `service_service.remove_dependency()` silent no-op for non-existent edge | `src/services/service_service.py:203` |
| BUG-1101-22 | Medium | 12 | Email logged at WARNING on login failure (enumeration vector) | `src/services/auth_service.py:33` |
| BUG-1101-23 | Medium | 12 | Email logged at WARNING on disabled-account login | `src/services/auth_service.py:36` |
| BUG-1101-24 | Medium | 11 | `health.py` performs DB ping + status logic inside the router handler | `src/api/routers/health.py:42` |
| BUG-1101-25 | Medium | 11 | `services.py` `add_service_dependency` declares `response_model=SQLModel` but returns `dict[str, str]` | `src/api/routers/services.py:98` |
| BUG-1101-26 | Medium | 11 | Canvas node-delete success path doesn't verify the element actually existed | `src/ui/components/canvas_events.py:157` |
| BUG-1101-27 | Medium | 10 | `Location.row` validator allows dash-only strings (`"-"`, `"--"`) | `src/models/location.py:50` |
| BUG-1101-28 | Medium | 10 | `Location.rack` field has no `field_validator` (whitespace bypass) | `src/models/location.py:22` |
| BUG-1101-29 | Medium | 10 | `service_service.remove_dependency()` `logger.info` claims removal even on no-op | `src/services/service_service.py:205` |
| BUG-1101-30 | Low | 8 | Admin email logged at INFO on first-boot seed | `src/services/auth_service.py:94` |
| BUG-1101-31 | Low | 8 | `inventory.py::_on_search` event handler parameter is untyped | `src/ui/pages/inventory.py:87` |
| BUG-1101-32 | Low | 7 | `canvas_tooltip.py` service status lookup tolerates whitespace/case mismatches by accident | `src/ui/components/canvas_tooltip.py:61` |
| BUG-1101-33 | Low | 7 | `diagram_service.delete()` and `update_timestamp()` not atomic CAS | `src/services/diagram_service.py:62, 72` |

---

## Critical & High Details

### BUG-1101-01 — Services & service_dependencies missing from export/import (Critical)

- **File:** `src/services/export_service.py:57`, `src/services/import_service.py:42`, `src/models/export_schema.py:92`
- **Trigger:** `POST /api/data-transfer/export` with services in DB → JSON missing services and service_dependencies. Subsequent import drops every service.
- **Expected:** All entities round-trip losslessly.
- **Actual:** `build_full_export()` retrieves only devices, connections, locations, tags, device_tags, custom_fields, diagram_layouts, users — `services` and `service_dependencies` are absent. `ExportSchema` has no `ExportedService` / `ExportedServiceDependency`. `_clear_all_tables()` omits both tables from its TRUNCATE list, and `import_full_snapshot()` has no insertion logic for them.
- **Evidence:**
  ```python
  # export_service.py:57+
  def build_full_export(...):
      # devices, connections, locations, tags, device_tags,
      # custom_fields, diagram_layouts, users — services NOT included
  ```
  ```python
  # export_schema.py:92-102
  class ExportSchema(SQLModel):
      devices: list[ExportedDevice]
      connections: list[ExportedConnection]
      # ... no services, no service_dependencies
  ```
  ```python
  # import_service.py:40-44
  TRUNCATE custom_fields, device_tags, connections, devices,
  diagram_layouts, locations, tags, users CASCADE
  # ^ services / service_dependencies absent
  ```
- **Failure mode:** Full data loss on backup/restore for the entire services subsystem.
- **Fix direction:** Add `ExportedService` + `ExportedServiceDependency` Pydantic models. Populate in `export_service.build_full_export()` after devices. Add insert logic in `import_service.import_full_snapshot()` after devices (services FK to devices) and after services (dependencies FK to services). Also fix BUG-1101-04 in the same diff.

### BUG-1101-02 — Diagram save TOCTOU race (High)

- **File:** `src/services/diagram_service.py:38, 84`
- **Trigger:** Two concurrent `PATCH /api/diagrams/{id}` requests, both reading `version=N` before either commits.
- **Expected:** First commit wins, second receives 409.
- **Actual:** Both transactions read the same baseline, both pass the in-Python `if data.version != layout.version:` guard, both increment `version` to N+1, both commit. Last write silently wins.
- **Evidence:** see `diagram_service.update()` (lines 38–57) and `partial_update()` (lines 84–103). The version check is performed in Python after the SELECT and before the UPDATE — there is no `WHERE version = N` predicate on the UPDATE itself.
- **Failure mode:** Concurrent autosaves silently overwrite each other; affected user is unaware of the loss.
- **Fix direction:** Atomicize the version check inside the UPDATE: `UPDATE diagram_layouts SET ..., version = version + 1 WHERE id = ? AND version = ?` and check `rowcount == 1` to detect conflict. Alternatively use `SELECT ... FOR UPDATE` inside an explicit transaction. Both `update()` and `partial_update()` need the same fix.

### BUG-1101-03 — Canvas drag positions never persisted (High)

- **File:** `src/ui/components/canvas_js.py:128`
- **Trigger:** User drags a node, then closes the tab without clicking **Save Layout**.
- **Expected:** Position changes are persisted to the server (immediately, debounced, or on tab unload).
- **Actual:** `dragfree` handler only writes to `window._htNodePositions`. No `fetch()` to `/api/diagrams/`. The only persistence path is the manual **Save Layout** button.
- **Evidence:**
  ```javascript
  // canvas_js.py:128-138
  cy.on('dragfree', 'node', function(evt) {
      var node = evt.target;
      window._htNodePositions = window._htNodePositions || {};
      window._htNodePositions[node.id()] = node.position();
      // no POST, no PATCH, no autosave
  });
  ```
- **Failure mode:** Silent loss of layout work on tab close, browser crash, or navigation.
- **Fix direction:** Add a debounced (≈800 ms) POST to `/api/diagrams/{current_id}/positions` from inside `dragfree`. Also add a `beforeunload` handler that flushes any pending debounce. Surface a "Saving…" / "Saved" indicator in the layout bar.

### BUG-1101-04 — TRUNCATE order omits services tables (High)

- **File:** `src/services/import_service.py:42`
- **Trigger:** Second `import_full_snapshot()` call against a database that already contains rows in `services` / `service_dependencies`.
- **Expected:** TRUNCATE wipes all tables in the correct dependency order.
- **Actual:** TRUNCATE list does not include `services` or `service_dependencies`. `service_dependencies.service_id` and `.depends_on_id` both have FKs to `services.id` (`migrations 012 lines 60, 85–89`); `services.device_id` has FK to `devices.id`. Re-import fails with FK violation.
- **Failure mode:** Restore-after-restore is permanently broken once any service rows exist.
- **Fix direction:** Update TRUNCATE to: `TRUNCATE service_dependencies, services, custom_fields, device_tags, connections, devices, diagram_layouts, locations, tags, users CASCADE`. Fix together with BUG-1101-01.

### BUG-1101-05 / 06 / 07 — Service `update()` commits without rollback (High)

- **Files:**
  - `src/services/device_service.py:198`
  - `src/services/connection_service.py:118`
  - `src/services/location_service.py:140`
- **Trigger:** Any `IntegrityError`/`OperationalError` raised during `session.commit()` in the `update()` paths of these services.
- **Expected:** `try / except IntegrityError → session.rollback() → HTTPException(409)`. Pattern is already used in `tag_service.update()` and `custom_field_service.update()`.
- **Actual:** No try/except wraps the commit. Exception escapes to FastAPI as a 500 with a dirty session left in scope.
- **Evidence (device_service.py:172–201):**
  ```python
  result = device_repository.update(session, device)
  session.commit()  # no try/except, no rollback path
  logger.info("Device updated: id={} name={}", result.id, result.name)
  return result
  ```
- **Failure mode:** Constraint violations surface as opaque 500s; subsequent operations on the same request inherit a poisoned session.
- **Fix direction:** Mirror the existing tag/custom-field pattern. Map known constraint names to 409, log unknown ones with `logger.exception` and re-raise as `HTTPException(500, "Internal database error")` (do not leak constraint names).

### BUG-1101-08 — Duplicate Cytoscape tap handlers (High)

- **File:** `src/ui/components/canvas_js.py:90` and `src/ui/components/canvas_events.py:239`
- **Trigger:** Click any device node on the canvas.
- **Expected:** A single `tap` `node` handler runs.
- **Actual:** `canvas_js.py` registers a `cy.on('tap', 'node', …)` that dispatches `ht:node-selected`. `canvas_events.py` *also* registers `cy.on('tap', 'node', …)` for connection-association mode. Both fire on every click; the order is non-deterministic and depends on which initializer ran last.
- **Failure mode:** Inconsistent UI state — detail panel may open while association mode is also being entered, or vice versa.
- **Fix direction:** Consolidate into a single canonical `tap` handler that branches on `window._htEdgeSource` / shift-modifier. Move association logic to a helper called from the same handler, not its own `cy.on('tap', 'node', …)`.

### BUG-1101-09 — `service_service.add_dependency()` bare `raise` leaks IntegrityError (High)

- **File:** `src/services/service_service.py:195`
- **Trigger:** `IntegrityError` whose `str(exc.orig)` does not contain `ck_service_dep_no_self_ref`, `check constraint`, `unique`, or `primary key`.
- **Expected:** Map unknown errors to a clean 500 with a generic message and `logger.exception` for diagnostics.
- **Actual:** `raise` re-throws the SQLAlchemy `IntegrityError`, which FastAPI returns as a 500 with whatever string SQLAlchemy produced — frequently leaking constraint names and column names.
- **Fix direction:** Replace the bare `raise` with `logger.exception("Unmapped IntegrityError on add_dependency"); raise HTTPException(500, "Internal database error") from exc`.

### BUG-1101-10 — `connection_service.create()` bare `raise` leaks IntegrityError (High)

- **File:** `src/services/connection_service.py:48`
- **Trigger:** `IntegrityError` not matching `ix_connections_unique_pair`.
- **Same shape as BUG-1101-09.** Apply the same fix pattern.

### BUG-1101-11 — Connection self-loop allowed (High)

- **File:** `src/models/connection.py:15`
- **Trigger:** `POST /api/connections` with `source_id == target_id`.
- **Expected:** 422 with detail `"source and target must be different devices"`.
- **Actual:** Accepted; persisted as a self-loop. No `model_validator` enforces inequality. Compare with `ServiceDependency` which has a `CHECK` constraint.
- **Fix direction:** Add `@model_validator(mode='after')` to `ConnectionBase` and a matching `CheckConstraint("source_id <> target_id")` on the `Connection` table. Migration required.

### BUG-1101-12 — `DeviceUpdate` accepts invalid IPs (High)

- **File:** `src/models/device.py:75`
- **Trigger:** `PATCH /api/devices/{id}` with `ip="not.an.ip"`.
- **Expected:** 422 (same as POST).
- **Actual:** Accepted. `DeviceBase` has a `@field_validator("ip")` using `ipaddress.ip_address`, but `DeviceUpdate` redeclares `ip: Optional[str]` with only `max_length` and no validator. PATCH bypasses the check.
- **Fix direction:** Either inherit `DeviceBase` for the partial update or duplicate the validator on `DeviceUpdate`. Same gap likely exists for any redeclared field on `DeviceUpdate` — audit them all.

### BUG-1101-13 — `UserBase` missing validators (High)

- **File:** `src/models/user.py:20`
- **Trigger:** `POST /api/users` with `username="   "` or `email="not-an-email"`.
- **Expected:** 422 on whitespace-only username, 422 on malformed email.
- **Actual:** Accepted. `UserBase.username` has `max_length=100` only; `email` is `str` with `max_length=255`. No strip, no format check.
- **Fix direction:** Add `@field_validator('username')` to strip and reject empty. Use `pydantic.EmailStr` for the email field (already a transitive dep via Pydantic), or a `@field_validator('email')` with a regex.

### BUG-1101-14 — `system.py` router executes DB queries directly (High)

- **File:** `src/api/routers/system.py:49`
- **Trigger:** `GET /api/system/stats`.
- **Expected:** Handler delegates to `system_service.get_stats(session)`.
- **Actual:** Handler runs six `session.exec(select(func.count())...)` calls and two raw `session.execute()` calls inline. This is a direct violation of the layered architecture (`AGENTS.md`): routers must delegate to services, not own SQL.
- **Fix direction:** Create `src/services/system_service.py` with `get_stats(session) -> SystemStats`. Move all queries there.

### BUG-1101-15 — `settings_locations.py` `or ""` erases falsy `0.0` (High)

- **File:** `src/ui/pages/settings_locations.py:114`
- **Trigger:** Edit a geographic location whose stored `lat=0.0` or `lng=0.0` (anywhere on the equator or prime meridian).
- **Expected:** Form pre-fills the existing value `"0.0"`; user can save without modification.
- **Actual:** `form["lat"] = row.get("lat") or ""` replaces `0.0` with `""` because `0.0` is falsy. Submit then raises `ValueError` from `float("")` and surfaces "lat and lng must be valid numbers". The bug only affects edits; create-flow is unaffected. Compare `_to_rows()` at line 88, which correctly uses `is not None`.
- **Evidence:**
  ```python
  # open_edit_modal(), lines 114-115
  form["lat"] = row.get("lat") or ""
  form["lng"] = row.get("lng") or ""
  ```
- **Fix direction:** Replace both lines with the `is not None` pattern already used in `_to_rows()`:
  ```python
  form["lat"] = str(row["lat"]) if row.get("lat") not in (None, "") else ""
  form["lng"] = str(row["lng"]) if row.get("lng") not in (None, "") else ""
  ```

### BUG-1101-16 — `require_role()` ValueError on bad enum claim (High)

- **File:** `src/domain/rbac.py:31`
- **Trigger:** Authenticated request whose JWT role claim is not a valid `Role` enum member (`"Admin" | "Contributor" | "Reader"`). Reachable only if `SECRET_KEY` is leaked or if a future change loosens JWT validation, but defense-in-depth still applies.
- **Expected:** `HTTPException(403, "Insufficient permissions")`.
- **Actual:** `Role(request.state.role)` raises `ValueError`, FastAPI returns 500.
- **Fix direction:** Wrap the enum coercion in `try/except ValueError → raise HTTPException(403)` and `logger.warning("Invalid role claim in JWT", user_id=...)`.

### BUG-1101-17 — `diagram_service` write ops missing try/except (High)

- **File:** `src/services/diagram_service.py:13, 38, 72`
- Same root cause as BUG-1101-05/06/07 but in the diagram path. `create()`, `update()`, `update_timestamp()` all call `session.commit()` with no rollback path.
- **Fix direction:** Same pattern. Note that BUG-1101-02 (TOCTOU) and BUG-1101-17 (rollback) should be fixed together since they both touch `update()` and `partial_update()`.

---

## All Findings (Deduplicated)

The Medium and Low findings are summarized in the **Prioritized Findings** table above. Full evidence for each is preserved in the lane logs (raw lane outputs are not embedded in this report to keep the document tractable; re-run the orchestrator with `--include-raw` if you need them).

Highlights from the Medium tier:

- **BUG-1101-18 (Medium, systemic)** — Every async router handler in the codebase calls service functions that invoke `session.commit()` synchronously. Under any concurrent load this blocks the event loop. Either wrap service calls in `asyncio.to_thread()` at the router boundary, or migrate to SQLAlchemy 2.0 async sessions (`AsyncSession` + `async with`). This is a single fix that improves the entire app.
- **BUG-1101-19 (Medium)** — `diagram.cytoscape_json` stores device IDs as opaque JSON. Deleting a device leaves dangling IDs in every layout that referenced it. Either add a service-layer hook on device delete that scrubs layouts, or accept the loose coupling and add a "stale node" filter on read.
- **BUG-1101-22 / 23 (Medium)** — Email enumeration vector: `auth_service.authenticate()` logs the user-supplied email at WARNING on both invalid-credentials and disabled-account paths. Anyone with log access can build a list of valid emails. Replace with `user_id=` (after lookup) or omit.

---

## Duplicate Merge Log

| Kept | Merged | Reason |
|---|---|---|
| BUG-1101-05 (`device_service.py:198` missing rollback, lane 2) | lane-3 finding "Missing IntegrityError handling in device_service.update" | Same file, same line, same fix; lane-2 framing (state lifecycle) is more general and the fix subsumes the lane-3 framing (error handling). Both ODC types noted in metadata. |
| BUG-1101-06 (`connection_service.py:118` missing rollback, lane 2) | lane-3 finding "Missing IntegrityError handling in connection_service.update" | Same as above. |
| BUG-1101-02 (`diagram_service.update()` TOCTOU, lane 4) | — | Kept distinct from BUG-1101-17 (rollback). Same function but different defects: TOCTOU is concurrency, rollback is error handling. Both must be fixed; the diff will share scaffolding. |

Total raw findings from 10 lanes: 34. After dedupe: 33.

---

## Lane Coverage Status

| Lane | ODC | Findings | Status | Notes |
|---|---|---|---|---|
| 1 | Function (input validation) | 5 | ✅ Complete | All 9 model files audited; `types.py` and `service_dependency.py` are mostly enum/constraint material. |
| 2 | Assignment (state) | 4 | ✅ Complete | All 8 repos + `db.py` audited. Repository layer is clean; service layer is the gap. |
| 3 | Checking (errors) | 4 (3 after dedupe) | ✅ Complete | Two findings merged into lane 2's framing. |
| 4 | Timing/Serialization | 4 | ✅ Complete | TOCTOU + sync-in-async surfaces are the headline issues. |
| 5 | Function (auth) | 1 | ✅ Complete | Strong result — only one defense-in-depth gap found. JWT, RBAC, password handling, middleware order all clean. |
| 6 | Function (data integrity) | 4 | ✅ Complete | Critical export/import gap is the headline. |
| 7 | Documentation (logs) | 3 | ✅ Complete | No `print()` or `logging.*` found. No JWT/password logging. Email-PII issues only. |
| 8 | Interface (cross-layer) | 4 | ✅ Complete | system.py and health.py are the structural violations; rest of the routers delegate cleanly. |
| 9 | Algorithm (canvas) | 4 | ✅ Complete | XSS surface is OK (`html.escape` + `_escapeHtml` in place); event handler conflicts and persistence gaps are the headline. |
| 10 | Algorithm (domain) | 1 | ✅ Complete | Pure-domain modules are clean. The single finding lives in the UI page that drives the location modal. |

---

## Residual Risk

Areas the 10-lane fan-out **did not** deeply cover and which warrant a follow-up audit:

1. **Alembic migration safety.** Lanes 2 and 6 brushed against migration files but no lane was tasked with a full migration audit (downgrade correctness, NOT NULL backfill safety, index creation locks). Recommend a dedicated DevOps-Engineer pass.
2. **Rate limiting correctness.** Lane 5 confirmed `slowapi` is wired but did not stress-test the limit/burst values for the auth endpoints. Likely fine, but worth a configuration review before any public exposure.
3. **NiceGUI session storage and CSRF.** Out of scope for the lanes as defined. NiceGUI's per-tab storage interactions with the JWT are not audited.
4. **Cytoscape memory growth across long sessions.** Lane 9 found no leaks but did not run the app under instrumentation. Worth a Playwright-driven 30-minute soak test (User-Simulator's territory).
5. **Bcrypt cost factor.** `src/utils/auth.py` was scanned but the cost factor value was not validated against current hardware recommendations. Worth a one-line check.
6. **Test coverage of the bugs above.** None of the bugs found are blocked by missing tests, but several (TOCTOU, drag persistence, FK ordering) have no regression test today. Test-Automation-Engineer should add coverage as part of QA-Fixer's pipeline.

---

## Recommended Fix Order

The order below sequences fixes to minimize rework. Bugs grouped under the same number are best fixed in a single PR.

1. **BUG-1101-01 + BUG-1101-04** — Restore the export/import pipeline as a single coherent fix (export schema + import truncate + import insert logic). One migration is required for the new schema fields. Add a round-trip test that exports, wipes, re-imports, and diffs every table.
2. **BUG-1101-02 + BUG-1101-17** — Fix the diagram TOCTOU and the missing rollback in the same diff, since both touch `update()` and `partial_update()`. Move the version check into a `WHERE version = ?` UPDATE and check `rowcount`.
3. **BUG-1101-03** — Add a debounced autosave for canvas drag positions plus a `beforeunload` flush. Probably the highest user-visible win.
4. **BUG-1101-05 + 06 + 07 + 17** — Roll out the rollback pattern across all service `update()` paths in one diff. Refactor the existing `tag_service` / `custom_field_service` pattern into a small helper if the duplication grows beyond five call sites.
5. **BUG-1101-08** — Consolidate the duplicate `tap` handlers. Low risk, high clarity benefit.
6. **BUG-1101-09 + 10 + 16** — Stop leaking SQL constraint names and stop returning 500 on bad role enums. Three small surgical fixes; one PR.
7. **BUG-1101-11 + 12 + 13** — Validation gaps. Low risk but each one is a real "wrong-case acceptance" bug. Bundle as a Pydantic-hardening PR.
8. **BUG-1101-14** — Extract `system.py` into a service. Architectural cleanup; do this before HT-021 lands or it will calcify.
9. **BUG-1101-15** — One-line falsy-coordinate fix in `settings_locations.py`. Trivial; could hitch a ride on any other UI PR.
10. **BUG-1101-18** — Sync-in-async refactor. Substantial scope; requires Architect input. Open as a follow-up Architect → Feature-Engineer story.
11. **Remaining Mediums and Lows** — Bundle as a "QA hygiene sweep" PR.

---

## Handoff

- **Downstream:** QA-Fixer
- **Pipeline verdict:** This report has 33 OPEN findings. It will remain in `doc/bugs/` (active) until every finding reaches a terminal state (`FIXED`, `SKIPPED`, or `ROUTED_ELSEWHERE`) and Code-Reviewer issues `APPROVED`.
- **Routing notes:**
  - **Architectural escalation needed:** BUG-1101-14 (system.py architecture violation) and BUG-1101-18 (sync-in-async refactor) should route to **Architect → Feature-Engineer**, not QA-Fixer alone.
  - **DevOps review needed:** BUG-1101-01 + BUG-1101-04 require a new Alembic migration; loop in **DevOps-Engineer** for the migration safety review.
  - **All other findings:** standard QA-Fixer remediation.
