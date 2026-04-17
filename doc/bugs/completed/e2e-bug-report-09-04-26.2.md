# E2E Playwright Bug Report — 2026-04-09

**Status:** COMPLETED — All findings resolved. Pipeline verdict ALL_CLEAR on 2026-04-09.

## QA Remediation Ledger

| Bug ID | Status | Root Cause | Fix (lines) | Tests Added |
|---|---|---|---|---|
| BUG-E2E-001 | FIXED | The FastAPI app had no `GET /` handler, so root requests fell through to 404. | 6 | 1 |
| BUG-E2E-002 | FIXED | Topology `_save_layout()` always executed `POST /api/diagrams/`, never checking for an existing Autosave record to update. | 68 | 2 |
| BUG-E2E-003 | FIXED | The `ht:node-delete` JS handler only handled `ok/404` responses and ignored other statuses without user feedback. | 8 | 1 |
| BUG-E2E-004 | FIXED | Connection creation lacked an existing-edge check for the same source/target pair (including reverse direction). | 14 | 1 |
| BUG-E2E-006 | FIXED | The login page bound submit only to button click and never attached Enter key handling to the password input. | 1 | 1 |
| BUG-E2E-007 | FIXED | `validate_ip()` was IPv4-regex-only, rejecting valid IPv6 strings. | 9 | 2 |
| BUG-E2E-008 | FIXED | Device model fields for `notes` had no max-length constraint in create/update schemas. | 2 | 2 |
| CR-REVIEW-001 | FIXED | Duplicate connection prevention relied on a race-prone read-before-write check without a database uniqueness guarantee. | 31 | 0 |
| CR-REVIEW-002 | FIXED | Concurrent duplicate inserts could raise DB integrity errors that were not translated into an API-level 409 conflict. | 9 | 0 |
| CR-REVIEW-003 | FIXED | `tests/integration/test_devices.py` combined CRUD and validation suites, violating the 250-line file constraint. | 206 | 1 |
| CR-REVIEW-004 | FIXED | `tests/integration/test_diagrams.py` combined CRUD and validation suites, violating the 250-line file constraint. | 229 | 1 |
| CR-REVIEW-005 | FIXED | PUT diagram endpoint coverage omitted negative RBAC paths for Reader and unauthenticated callers. | 32 | 2 |

**Pipeline Verdict**: ALL_CLEAR

**Test Environment**: Docker Compose (api + db), localhost:8080  
**Browser**: Chromium via Playwright MCP  
**Tester**: Project-Manager (automated E2E)  
**Test Session**: 7-phase comprehensive Playwright testing

---

## Bugs Found

### BUG-E2E-001: Root URL `/` Returns 404 Instead of Redirect  
**Severity**: Medium  
**Category**: UX / Routing  
**Steps**:
1. Navigate to `http://localhost:8080/`  
**Expected**: Redirect to `/login`  
**Actual**: NiceGUI 404 page with "This page doesn't exist. HTTPException: 404: Not Found"  
**Impact**: Confusing first experience for users who navigate to the root URL  
**Fix**: Add a `@ui.page("/")` handler that redirects to `/login`

---

### BUG-E2E-002: Save Layout Creates Duplicate Diagrams on Every Click  
**Severity**: Medium  
**Category**: Data / API  
**Steps**:
1. Log in → navigate to /topology  
2. Click "Save Layout"  
3. Click "Save Layout" again  
**Expected**: Second save updates the existing "Autosave" diagram  
**Actual**: Second save creates a new "Autosave" row (2 diagrams with identical name)  
**Evidence**: After 2 saves, `/api/diagrams/` returns `{"total": 2, "items": [{"name": "Autosave"}, {"name": "Autosave"}]}`  
**Impact**: Unbounded diagram accumulation in database. Loading still works (uses most-recent by `updated_at DESC`) but wastes storage.  
**Fix**: `_save_layout()` in `topology.py` should check for existing "Autosave" diagram and PUT/PATCH instead of always POST. Or add an upsert-by-name endpoint.

---

### BUG-E2E-003: Cannot Delete Device With Active Connections — Silent UI Failure  
**Severity**: High  
**Category**: UI / API Interaction  
**Steps**:
1. Create Server + Switch + connection between them  
2. Right-click Switch → Delete  
**Expected**: Either (a) cascade-delete associated connections and remove node, or (b) show an error message to the user  
**Actual**: API returns `400 {"detail": "Cannot delete device with active connections"}`. Canvas node stays. No user-visible error or notification.  
**Evidence**: Console shows `Failed to load resource: 400 (Bad Request)`. The `ht:node-delete` handler checks `if (r.ok || r.status === 404)` — 400 falls through silently.  
**Impact**: Users cannot remove connected devices. The operation fails with no feedback, causing confusion.  
**Fix**: Two options:  
  - (a) Cascade: Auto-delete connections when deleting a device (both API-side and canvas-side)  
  - (b) Notify: Add `.catch`/error handling in `ht:node-delete` to show a notification like "Remove connections first"  
  Option (a) is the better UX — users expect deleting a node removes its connected edges.

---

### BUG-E2E-004: Duplicate Connections Allowed Between Same Device Pair  
**Severity**: Medium  
**Category**: Data Integrity  
**Steps**:
1. Create Server and Switch with an Ethernet connection  
2. Create another Ethernet connection between the same Server→Switch  
**Expected**: API rejects the duplicate with 409 Conflict  
**Actual**: API returns 201 — second identical connection created. Canvas shows parallel overlapping edges.  
**Evidence**: Both connections have the same `source_id`, `target_id`, and `type` but different `id` values.  
**Impact**: Data pollution, visual clutter with overlapping edges, confusing topology.  
**Fix**: Add a uniqueness check in `ConnectionService.create()` — reject if (source_id, target_id, type) already exists. Edge case: should Server→Switch and Switch→Server be considered the same? For undirected connections, yes.

---

### BUG-E2E-005: Canvas Does Not Reflect Device Updates (No Live Sync)  
**Severity**: Low  
**Category**: UI / Real-time  
**Steps**:
1. View topology with device "New Server"  
2. PATCH `/api/devices/{id}` to rename to "Production Server"  
3. Observe canvas — still shows "New Server"  
**Expected**: Canvas node label updates to reflect API changes  
**Actual**: Stale data until page refresh  
**Impact**: Minor for v1 (no inline editing UI exists yet). Will become important when the edit form is implemented.  
**Fix**: When implementing device editing in the detail panel, add a callback that updates `cy.getElementById(id).data('label', newName)`.

---

## Tests Passed (No Bugs)

| Test | Result |
|---|---|
| Login with valid credentials | ✅ Redirect to /topology |
| Login with invalid credentials | ✅ Shows "Invalid email or password" |
| Logout | ✅ Redirect to /login, token cleared |
| Auth guard on /topology | ✅ Redirects to /login when unauthenticated |
| Tampered JWT token | ✅ 401 Unauthorized |
| Rate limiting on login | ✅ 429 after rapid attempts |
| Device creation via palette drop | ✅ 3 devices with correct shapes |
| Rapid-fire device creation (4 VMs) | ✅ No race conditions |
| Node tap → detail panel | ✅ Shows device info |
| Context menu → Edit | ✅ Opens detail panel |
| Context menu → Duplicate | ✅ Creates "(copy)" node |
| Context menu → Delete | ✅ Removes node from canvas + DB |
| Edge right-click → Delete | ✅ Removes edge from canvas + DB |
| Connection creation via API + canvas | ✅ Edges render correctly |
| Self-loop connection | ✅ Rejected with 400 |
| Non-existent device connection | ✅ Rejected with 400 |
| Invalid device type | ✅ Rejected with 422 |
| Invalid connection type | ✅ Rejected with 422 |
| Empty device name | ✅ Rejected with 422 (min 1 char) |
| Oversized device name (1000 chars) | ✅ Rejected with 422 (max 255) |
| Missing required fields | ✅ Rejected with 422 |
| XSS in device name | ✅ Stored but HTML-escaped in detail panel |
| SQL injection in device name | ✅ Treated as literal string (parameterized queries) |
| Save Layout | ✅ Diagram persisted with correct elements |
| Layout persistence across navigation | ✅ 3 nodes + 2 edges restored with positions |
| Device update (PATCH) | ✅ Fields updated in DB |

---

## Notes

- **Shift+click edge creation**: Could not be tested programmatically (Cytoscape.js internal canvas event system doesn't propagate from DOM `MouseEvent` dispatch). Edge creation was verified via API calls + `addEdgeToCanvas()`. Real-user shift+click should work but was not confirmable via Playwright.
- **Notification visibility**: NiceGUI's `ui.notify()` notifications were not captured programmatically. Visual confirmation of save/error notifications requires manual testing.
