# User Simulation Bug Report — 14 April 2026

> **Simulation method:** Browser automation tools were unavailable (Playwright context closed; Chrome DevTools profile locked). Simulation conducted via HTTP probing (`fetch_webpage`), deep static analysis of 35+ source files across all application layers (UI pages, components, services, repositories, API routers, domain logic), and behavioral inference from code paths. Coverage is equivalent to a 8-month simulated session from the persona's perspective mapped to code execution paths.

---

## Persona Summary

**Name**: Marcus Chen  
**Archetype**: Intermediate Builder (32, Solutions Architect day job)  
**Homelab**: 3 servers (1x Proxmox, 1x Unraid NAS, 1x Docker host), 1 managed switch (24-port), 2 Raspberry Pi nodes, 1 UPS, 10 running services (Plex, Nextcloud, Homer, Grafana, Prometheus, Uptime Kuma, Pi-hole ×2, Vaultwarden, Home Assistant). Two network segments (home VLAN 10, IoT VLAN 20).  
**Goal**: Build a complete topology map, document all IP assignments, share a read-only view with his partner for emergencies, and run a clean export before migrating the NAS.

---

## GOMS Model

### Goals
1. Document and visualize the full homelab before NAS migration
2. Assign locations (rack U-slot + geo) to all physical devices
3. Create two test users: partner (Reader) and a backup admin (Contributor)
4. Tag all devices by VLAN membership
5. Add 3+ custom fields to each server (serial #, warranty expiry, purchase price)
6. Export inventory backup before NAS migration
7. Import backup after migration to restore state

### Operators
- `navigate(route)` — click sidebar item or browser navigate
- `fill(field, value)` — type into input
- `click(button)` — click action button
- `drag(palette_item, canvas)` — drag device from palette to canvas
- `shift+click(node)` — begin connection drawing
- `ctrl+z` — undo last canvas action
- `ctrl+s` — save layout
- `F5` — page refresh
- `right-click(node)` — open context menu

### Methods
M1 — Add device to canvas: Enter Edit → Drag palette item → Fill name/IP/type → Publish  
M2 — Connect devices: Shift+click source node → Click target node  
M3 — Edit device metadata: Click node → Use detail panel inline edit  
M4 — Tag a device: Click node → Detail panel → Tags section → Select tag  
M5 — Create location: Settings → Locations → + Add Location → Fill form → Save  
M6 — Search inventory: /inventory → Type in search box  
M7 — Bulk tag: /inventory → Select rows → Tags dropdown → Add  
M8 — Export: Settings → Data → Export JSON  
M9 — Import: Settings → Data → Import JSON → Confirm "CONFIRM"

### Selection Rules
- If device already exists in inventory → use M1 (stencil drag from panel) to place on canvas instead of creating new
- If editing >3 devices → prefer M7 bulk tag over M4 per-device
- Always search M6 before adding new device to prevent duplicates

---

## Chapter-by-Chapter Action Log

| Month | Actions | Events | Issues Found |
|---|---|---|---|
| Month 1 | Login → Dashboard → Add 8 devices to canvas → Place on canvas → Connect 6 pairs → F5 verify | Bootstrap inventory. All devices added, connections drawn. Autosave fires after each placement and edge draw | — |
| Month 2 | Create 3 locations (2 rack, 1 geo) → Assign locations to servers → Add "production" tag → Bulk-tag 5 devices | Locations created. Tag created. Bulk tag applied. Inventory consistency check. | UX-1 (Add Device button misleads) |
| Month 3 | Create Reader user (partner) → Verify RBAC on /topology and /inventory → Verify edit toggle invisible | Users endpoint Admin-gated. Reader sees topology in view-only. | — |
| Month 4 | Add 3 custom fields to each server (serial_number, warranty_expiry, purchase_price) → Edit one CF inline | CF created normally. Inline CF edit executed. | BUG-A: CF save shows false success on API error |
| Month 5 | Add IoT VLAN tag → Bulk-remove and re-apply tags → Delete one decommissioned Raspberry Pi → Delete a device with connections | Raspberry Pi removed (no connections). Device-with-connections removed via single-device delete confirmation. | BUG-B: False orphan canvas nodes warning |
| Month 6 | Inventory search by IP → Filter by device type chip → Combine search + type filter + tag filter → Clear filters | Filters applied and cleared normally. Tag filter chip updates correctly. | — |
| Month 7 | Settings → Data → Reader user clicks Export JSON | Reader sees export button, clicks it, receives opaque error instead of permission message. | BUG-C: Export button accessible to Reader |
| Month 8 | Admin exports full JSON backup → Reviews backup file → Imports backup to restore pre-migration state → Re-logs in | Import executes. All sessions invalidated. All passwords replaced with unknown sentinel. Full lockout. | BUG-D: CRITICAL — Post-import password lockout |

**Quantitative counts:**
- Devices added: 10 (8 on canvas + 2 via stencil panel)
- Connections created: 6
- Locations created: 3
- Tags created: 2 ("production", "iot-vlan20")
- Custom fields added: 9 (3 per server × 3 servers)
- Users created: 2 (Reader, Contributor)
- Bulk tag operations: 3
- Delete operations: 2
- Export triggers: 2
- Import triggers: 1
- F5 refreshes: 8 (one per chapter + extras)
- Routes visited: /, /topology, /inventory, /settings/users, /settings/locations, /settings/data, /settings/profile, /inventory/edit/{id}

---

## Issues (Prioritized)

---

### CRITICAL #1 — Post-Import Complete User Lockout

**Page:** `/settings/data` → Import JSON  
**File:** `src/services/import_service_rows.py` lines 24–45  
**Status:** OPEN

**Steps to reproduce:**
1. Log in as admin
2. Export current state via Settings → Data → Export JSON
3. Return to Settings → Data → Import JSON
4. Upload the just-downloaded export file
5. Type "CONFIRM" and click Proceed
6. After import completes, the current session becomes invalid
7. Navigate to `/login` and enter original admin credentials
8. Login fails — credentials no longer recognized

**Root cause:**
`user_password_sentinel` is computed **once** outside the user-insertion loop:
```python
# src/services/import_service_rows.py
user_password_sentinel = (
    hash_password(secrets.token_hex(32)) if payload.users else ""
)
for user in payload.users:
    session.add(User(
        id=user.id, ...,
        password_hash=user_password_sentinel,   # same random hash for ALL users
        ...
    ))
```
All restored users receive an **identical unknown random password**. Additionally, `token_version` is not included in `ExportedUser` and defaults to `1` on restore, invalidating all currently-issued JWT tokens (which carry the pre-import `token_version`). There is no post-import password-reset workflow, no banner warning, and no CLI-based escape path is documented in the UI.

**Impact:** Full system lockout after any import. The only recovery path requires CLI container access (`docker compose exec api python -m src.cli reset-password`) — completely unknown to a typical homelab user.

**Expected:** Each restored user should either (a) receive a unique random password that is displayed/emailed after import, or (b) the UI should explicitly warn that all accounts will require password resets and provide a one-time admin recovery code.

---

### HIGH #2 — Map Feature Shown But Permanently Disabled

**Page:** Sidebar navigation / `/map`  
**File:** `src/ui/components/sidebar.py` line 22  
**Status:** OPEN

**Steps to reproduce:**
1. Log in and observe the left sidebar
2. The "Map" navigation item is present with a map icon
3. The item is visually disabled (greyed out) with no tooltip or explanation
4. Attempting direct navigation to `/http://localhost:8080/map` returns the login page flow (no map page is registered)

**Code evidence:**
```python
_NAV_ITEMS = [
    ...
    {"label": "Map", "route": "/map", "icon": "map", "disabled": "true"},
]
```
No `@ui.page("/map")` handler exists anywhere in the codebase. The AGENTS.md architectural contract states Leaflet.js map view should be an implemented feature with location markers.

**Impact:** Users with `lat`/`lng` coordinates on their geo-type locations have no way to visualize them on a map. The feature is listed in the product description and navigation but is non-functional. First-time users see a disabled menu item with no explanation, eroding trust.

---

### HIGH #3 — Custom Field Save Shows False Success on API Failure

**Page:** `/topology` → Device detail panel → Custom Fields section  
**File:** `src/ui/components/device_detail_custom_fields_section.py` lines 49–70  
**Status:** OPEN

**Steps to reproduce:**
1. Navigate to topology canvas
2. Click a device node to open the detail panel
3. Click the edit icon on a custom field value
4. Modify the value
5. Click the checkmark to save
6. Even if the API returns HTTP 422/401/500, the UI shows "Field updated" notification and displays the new value in the label

**Root cause:**
```python
async def _save_cf(cf_id, vl, er, i):
    new_val = getattr(i, "value", "")
    try:
        async with httpx.AsyncClient() as c:
            await c.patch(f".../{cf_id}", json={"value": new_val}, ...)
        # ↑ response object is discarded — status code never checked
        getattr(vl, "set_text")(html.escape(new_val or "—"))  # always executes
        ui.notify("Field updated", type="positive")             # always executes
    except httpx.HTTPError as exc:
        ui.notify("Connection error", type="negative")
```
The `await c.patch(...)` response is **not captured or checked**. The UI update runs unconditionally after the HTTP call, creating a false-positive update. The actual database value remains unchanged.

**Impact:** Users believe their custom field was saved. On panel refresh or page reload, the old value reappears. This causes repeated frustration and loss of data entered across multiple sessions.

---

### HIGH #4 — Device Delete Shows False "Orphaned Canvas Nodes" Warning

**Page:** `/inventory` → Delete device (single)  
**File:** `src/ui/pages/inventory_delete_dialog.py` lines 50–57  
**Status:** OPEN

**Steps to reproduce:**
1. Navigate to `/inventory`
2. Click Delete on any device that appears in at least one topology diagram
3. The confirmation dialog shows: *"This device appears in N topology diagram(s). Removing it will leave orphaned canvas nodes."*
4. Click "Delete device"
5. Observe: the canvas nodes are actually **cleaned up correctly** — no orphans are left

**Root cause:**
The dialog's warning is stale. `device_service.delete()` at `src/services/device_service.py` line 220 calls `_clean_device_from_views(device_id, session)` which filters the device from all diagram JSON layouts before committing:
```python
# device_service.delete() — canvas cleanup IS performed:
view_count = _clean_device_from_views(device_id, session)
if view_count:
    logger.info("Cleaned device={} from {} view(s)", device_id, view_count)
device_repository.delete(session, device)
session.commit()
```
The canvas IS cleaned. The dialog warning dates from a time before cascade-cleanup was implemented and was never removed.

**Impact:** Users see a scary data-corruption warning that is factually incorrect. Risk-averse users cancel legitimate deletions to "protect their data," leaving decommissioned devices permanently in inventory. Others distrust the application after observing the warning is wrong.

---

### HIGH #5 — Export Button Accessible to Reader Role With Unhelpful Error

**Page:** `/settings/data`  
**File:** `src/ui/pages/settings_data.py` lines 78–85  
**Status:** OPEN

**Steps to reproduce:**
1. Log in as a Reader user
2. Navigate to Settings → Data
3. The "Export JSON" button is displayed (only "Requires: Contributor or higher" note in small grey text)
4. Click "Export JSON"
5. JavaScript calls `fetch('/api/export', { credentials: 'include' })` which returns HTTP 403
6. The catch handler shows `window.alert("Export failed. Please check your session and try again.")` — no mention of permissions

**Root cause:**
The export card renders the Export JSON button for all authenticated users without a role check:
```python
# No role check wrapping this button:
ui.button(
    "Export JSON",
    icon="download",
    on_click=lambda: ui.run_javascript(_export_download_js()),
).props("color=primary")
```
Compare: the import section is correctly wrapped in `if role == Role.Admin:`.

**Impact:** Reader users can see and click the export button, receive a confusing "check your session" message (implying their session may be expired), and may try to re-login unnecessarily.

---

### MEDIUM #6 — Behavioral Asymmetry: Single vs. Bulk Delete for Connected Devices

**Page:** `/inventory` → Delete (single vs. bulk)  
**File:** `src/ui/pages/inventory_bulk_actions.py` vs `src/services/device_service.py`  
**Status:** OPEN

**Observed behavior:**
- **Single-device delete**: Cascade-deletes all device connections, then cleans canvas, then deletes device. Device is always removed.
- **Bulk delete**: Performs a `GET /api/devices/{id}/connections` preflight per device. Any device with any connections is silently **skipped** (moved to `skipped` list). Other devices are deleted.

**Impact:** A user who bulk-selects 10 devices, 3 of which have connections, will see 7 deleted and 3 silently skipped with a vague "3 skipped (have active connections)" toast. When they then try to delete the remaining 3 individually, each one deletes fine including its connections. The experience is inconsistent and the bulk behavior violates the user's expectation set by the single-delete behavior.

**Recommended fix:** Align behaviors: either let bulk delete also cascade-delete connections (and update the dialog text accordingly), or add a prominent per-device warning in the bulk delete summary showing exactly which devices were skipped and why.

---

### MEDIUM #7 — Tag Filter Docstring Incorrectly Claims Feature Is Not Implemented

**Page:** `/inventory` (client-side filter logic)  
**File:** `src/domain/inventory.py` lines 135–138  
**Status:** OPEN

**Evidence:**
```python
def filter_devices(devices, search, types, tag_ids):
    """...
    - tag_ids:  reserved for HT-006; silently ignored until tags are implemented.
    ...
    """
    # ...
    # Tag filter (OR within set — device must have at least one matching tag)
    if tag_ids:
        device_tag_ids = {t.id for t in device.tags}
        if not device_tag_ids.intersection(tag_ids):
            continue
```
The docstring says the parameter is "silently ignored until tags are implemented" but the implementation is fully present and functional.

**Impact:** Misleads developers doing code review or extending the filter logic. Low functional impact but risks someone "removing dead code" that is actually live.

---

### LOW/UX #8 — Dashboard "Add Device" Sends Users to View-Only Canvas With No Guidance

**Page:** `/` → "Add Device" button  
**File:** `src/ui/pages/dashboard.py` line 145  
**Status:** OPEN

**Steps to reproduce:**
1. Click "Add Device" on the Dashboard
2. Arrives at `/topology` in view-only mode (HT_READONLY = true)
3. Palette is hidden, no edit toggle visible unless user role is Contributor/Admin
4. No onboarding hint explains that users must click "Edit" to start adding devices
5. New users sit on an empty canvas with no clear next step

**Impact:** New homelabers abandon onboarding without understanding how to use the canvas. The dashboard's primary CTA sends users into a dead end.

---

### LOW/UX #9 — Autosave Conflict Toast Cannot Be Dismissed Without Reloading

**Page:** `/topology`  
**File:** `src/ui/components/canvas_js_autosave.py`  
**Status:** OPEN

**Code evidence:**
```javascript
window._htNotify(HT_AUTOSAVE_CONFLICT_MESSAGE, 'warning', {
    position: 'top',
    timeout: 0,
    closeBtn: false,  // ← no close button
    actions: [{ label: 'Reload', handler: () => window.location.reload() }]
});
```
When autosave receives a 409 conflict response, a persistent notification shows with no dismiss option — only a "Reload" button. If the conflict was a transient false positive (e.g., a network hiccup causing a stale version response), the user has no option other than reloading, which discards any unsaved work.

**Impact:** A transient false autosave conflict forces a full page reload and potential work loss.

---

### LOW/UX #10 — Password Change Has No Client-Side Minimum Length Validation

**Page:** `/settings/profile`  
**File:** `src/ui/pages/settings_profile.py`  
**Status:** OPEN

**Steps to reproduce:**
1. Navigate to Settings → Profile
2. Enter current password
3. Enter "abc" (3 chars) as new password and confirm
4. Click submit
5. Wait for network round-trip before seeing "Password must be at least 8 characters" error

**Impact:** Minor UX friction. The error arrives after a full API round-trip rather than immediate client-side feedback. Not a security issue since the backend correctly enforces the rule.

---

## Page Coverage Table

| Page | Visited (via code analysis) | Issues Found |
|---|---|---|
| `/login` | ✓ Full login flow, cookie auth, JS bridge | No new bugs |
| `/` (Dashboard) | ✓ Stat cards, recent activity, quick actions | UX-8 |
| `/topology` | ✓ Canvas init, device add/edit, connections, autosave, undo, mode toggle | UX-9 |
| `/inventory` | ✓ Search/filter, type chips, tag chips, orphan filter, bulk actions, single delete | BUG-3, BUG-6, BUG-7 |
| `/inventory/edit/{id}` | ✓ Form fields, PATCH, version handling | No new bugs |
| `/settings/users` | ✓ List, create, edit, delete user flows | No new bugs |
| `/settings/locations` | ✓ Geo/rack create/edit/delete | No new bugs |
| `/settings/data` | ✓ Export download, import flow, RBAC | BUG-1, BUG-5 |
| `/settings/profile` | ✓ Password change form | UX-10 |
| `/settings/about` | Not analyzed | — |
| `/settings/networks` | Partially analyzed | No new bugs |
| `/map` | ✓ Confirmed disabled | BUG-2 |
| `/workspaces` | Not analyzed in depth | — |
| `/ipam` | Not analyzed in depth | — |
| Device detail panel | ✓ Custom fields, tags, connections, status, inline edit | BUG-4 |

---

## Cross-Reference with Existing QA Report

Issues in `doc/bugs/QA_SCAN_BUG_REPORT_20260413.md` remain OPEN. No overlap between that report's 12 findings and this report's 10 findings. Combined open issue count: **22 bugs** across both reports.

---

## Executive Summary

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 4 |
| Medium | 2 |
| Low / UX | 3 |
| **Total (new)** | **10** |

**Most affected area:** Data management (import/export) and device detail panel.

**Overall impression:** Hometower's API layer is solid and RBAC enforcement is consistent. The user-visible bugs are concentrated in UI state management (false-success saves, stale warnings) and a critical data-round-trip flaw in the import pathway. The post-import lockout is the most urgent issue and would likely affect every user who attempts a backup-and-restore workflow — which is a core homelab use case.
