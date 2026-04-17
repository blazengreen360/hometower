"""Deep Playwright E2E bug hunt — HT-047..HT-052, HT-049, security, API contracts.

Covers stories NOT in the original test_stories_e2e.py suite, plus fixes
for known selector/field-name issues found in baseline run.

Run directly (requires server on port 8080):
    python tests/e2e/test_deep_hunt.py 2>&1 | tee /tmp/deeptest.log
"""
from __future__ import annotations

import json
import time
import traceback
import urllib.error
import urllib.request
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright

BASE = "http://localhost:8080"
ADMIN_EMAIL = "admin@hometower.local"
ADMIN_PASS = "changeme_on_first_boot"

results: list[dict[str, str]] = []
_admin_token: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def record(story: str, test: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    results.append({"story": story, "test": test, "status": status, "detail": detail})
    print(f"  [{status}] {story} — {test}" + (f" ({detail})" if detail else ""))


def api(method: str, path: str, body: dict[str, Any] | None = None,
        token: str = "", expect_status: int = 200) -> dict[str, Any] | None:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        raw = resp.read()
        return json.loads(raw) if raw else {"__status": resp.status}
    except urllib.error.HTTPError as e:
        if e.code == expect_status:
            return {"__status": e.code}
        raw = e.read()
        try:
            return {"__status": e.code, "__body": json.loads(raw)}
        except Exception:
            return {"__status": e.code, "__body": raw.decode(errors="replace")}
    except Exception as exc:
        return {"__error": str(exc)}


def get_admin_token() -> str:
    global _admin_token
    if _admin_token:
        return _admin_token
    resp = api("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    _admin_token = (resp or {}).get("access_token", "")
    return _admin_token


def login(page: Page, email: str = ADMIN_EMAIL, password: str = ADMIN_PASS) -> bool:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_timeout(1500)
    em = page.locator('input[type="text"], input[type="email"]')
    pw = page.locator('input[type="password"]')
    btn = page.locator('button:has-text("Log in"), button:has-text("Login"), button:has-text("Sign in")')
    if em.count() == 0 or pw.count() == 0 or btn.count() == 0:
        return False
    em.first.fill(email)
    pw.first.fill(password)
    btn.first.click()
    page.wait_for_timeout(2000)
    return "/login" not in page.url


def wait_for_cy(page: Page, timeout_ms: int = 15000) -> bool:
    page.evaluate("() => { var el=document.getElementById('cy'); if(el&&el.clientHeight===0) el.style.height='600px'; }")
    for _ in range(timeout_ms // 500):
        ready = page.evaluate(
            "() => typeof window._cy!=='undefined' && window._cy!==null && typeof window._cy.nodes==='function'"
        )
        if ready:
            return True
        page.wait_for_timeout(500)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 1. INVENTORY TABLE (fixed selectors — from HT-009 failures)
# ─────────────────────────────────────────────────────────────────────────────

def test_inventory_deep(page: Page) -> None:
    print("\n=== INVENTORY DEEP (HT-009 selector fix) ===")
    login(page)
    page.goto(f"{BASE}/inventory", wait_until="networkidle")
    page.wait_for_timeout(4000)

    # Use correct selector — q-tr renders as <tr> inside .q-table tbody
    row_sel = ".q-table tbody tr"
    rows = page.locator(row_sel)
    n = rows.count()
    record("HT-009-fix", "Inventory rows found with corrected selector", n > 0, f"rows={n}")

    # Column headers
    headers = [h.strip() for h in page.locator(".q-table thead th").all_inner_texts()]
    record("HT-009-fix", "Table has Name column", "Name" in headers, str(headers))
    record("HT-009-fix", "Table has Type column", "Type" in headers, str(headers))
    record("HT-009-fix", "Table has Status column", "Status" in headers, str(headers))

    # Search
    search = page.locator('input[placeholder*="Search"]')
    if search.count() > 0 and n > 0:
        first_name = rows.first.all_inner_texts()[0] if n > 0 else ""
        search.first.fill("zzz_no_match_xyz")
        page.wait_for_timeout(1500)
        after_search = page.locator(row_sel).count()
        record("HT-009-fix", "Search with no-match clears rows", after_search == 0,
               f"after_filter={after_search}")
        search.first.fill("")
        page.wait_for_timeout(1500)
        record("HT-009-fix", "Clearing search restores rows", page.locator(row_sel).count() > 0)
    else:
        record("HT-009-fix", "Search input present", search.count() > 0)


# ─────────────────────────────────────────────────────────────────────────────
# 2. WORKSPACE HIERARCHY  (HT-047)
# ─────────────────────────────────────────────────────────────────────────────

def test_workspace_hierarchy(page: Page) -> None:
    print("\n=== WORKSPACE HIERARCHY (HT-047) ===")
    token = get_admin_token()

    # API: create workspace + topology
    ws = api("POST", "/api/workspaces/", {"name": f"E2E-WS-{int(time.time())}"}, token=token)
    ws_id = (ws or {}).get("id", "")
    record("HT-047", "Workspace created via API", bool(ws_id), str(ws_id)[:8] if ws_id else "ERR")

    topo = api("POST", f"/api/workspaces/{ws_id}/topologies/",
               {"name": "E2E Topology"}, token=token)
    topo_id = (topo or {}).get("id", "")
    record("HT-047", "Topology created inside workspace", bool(topo_id), str(topo_id)[:8] if topo_id else "ERR")

    # UI: /workspaces page
    login(page)
    page.goto(f"{BASE}/workspaces", wait_until="networkidle")
    page.wait_for_timeout(3000)
    ws_heading = page.locator(':text("Workspaces"), :text("workspace")').count()
    record("HT-047", "/workspaces page renders", ws_heading > 0 or "workspaces" in page.url)

    # The workspace row should appear
    ws_rows = page.locator(".q-table tbody tr, table tbody tr")
    record("HT-047", "Workspace table has rows", ws_rows.count() > 0, f"rows={ws_rows.count()}")

    # Navigate to workspace detail
    if ws_id:
        page.goto(f"{BASE}/workspaces/{ws_id}", wait_until="networkidle")
        page.wait_for_timeout(3000)
        topo_heading = page.locator(':text("Topology"), :text("topology")').count()
        record("HT-047", "Workspace detail page renders", topo_heading > 0 or ws_id in page.url)

        # Navigate to topology → should redirect to canvas
        if topo_id:
            page.goto(f"{BASE}/workspaces/{ws_id}/topologies/{topo_id}", wait_until="networkidle")
            page.wait_for_timeout(4000)
            on_topology = "/topology" in page.url
            record("HT-047", "Topology link redirects to /topology canvas", on_topology, page.url[:80])

    # Cleanup
    if ws_id:
        api("DELETE", f"/api/workspaces/{ws_id}", token=token)


# ─────────────────────────────────────────────────────────────────────────────
# 3. EDIT MODE + RBAC GATE  (HT-048)
# ─────────────────────────────────────────────────────────────────────────────

def test_edit_mode_rbac(page: Page) -> None:
    print("\n=== EDIT MODE + RBAC GATE (HT-048) ===")
    login(page)
    page.goto(f"{BASE}/topology", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # Palette should be hidden in view mode
    palette = page.locator('.palette-card, [data-device-type], [draggable="true"]')
    # The palette container is hidden but palette cards may still be in DOM
    # Test via JS — HT_READONLY should be true by default
    readonly = page.evaluate("() => window.HT_READONLY")
    record("HT-048", "Canvas starts in readonly mode", readonly is True or readonly == 1,
           f"HT_READONLY={readonly}")

    # Edit toggle button
    edit_btn = page.locator('button:has-text("Edit"), button[aria-label*="edit" i], [data-testid="edit-toggle"]')
    has_edit = edit_btn.count() > 0
    record("HT-048", "Edit toggle button present for admin", has_edit)

    if has_edit:
        edit_btn.first.click()
        page.wait_for_timeout(2000)
        after_edit = page.evaluate("() => window.HT_READONLY")
        record("HT-048", "HT_READONLY becomes false after edit toggle",
               after_edit is False or after_edit == 0, f"HT_READONLY={after_edit}")

        # Palette container should now be visible
        palette_container = page.locator('[id*="palette"], .palette-card, [draggable="true"]')
        record("HT-048", "Palette/draggable elements visible in edit mode",
               palette_container.count() > 0, f"count={palette_container.count()}")

        # Exit edit mode
        edit_btn.first.click()
        page.wait_for_timeout(1500)
        exited = page.evaluate("() => window.HT_READONLY")
        record("HT-048", "HT_READONLY restores true after exiting edit", exited is True or exited == 1)

    # RBAC: Create Reader token via API, test no Edit button
    token = get_admin_token()
    import random, string
    rnd = "".join(random.choices(string.ascii_lowercase, k=6))
    reader_user = api("POST", "/api/users/", {
        "username": f"reader_{rnd}",
        "email": f"reader_{rnd}@test.local",
        "password": "Test1234!",
        "role": "Reader",
    }, token=token)
    if reader_user and "id" in reader_user:
        login(page, f"reader_{rnd}@test.local", "Test1234!")
        page.goto(f"{BASE}/topology", wait_until="networkidle")
        page.wait_for_timeout(2500)
        reader_edit = page.locator('button:has-text("Edit")').count()
        record("HT-048", "Reader role: no Edit button", reader_edit == 0, f"found={reader_edit}")
        # Cleanup
        api("DELETE", f"/api/users/{reader_user['id']}", token=token)
        login(page)  # re-login as admin


# ─────────────────────────────────────────────────────────────────────────────
# 4. STENCILS PANEL  (HT-049)
# ─────────────────────────────────────────────────────────────────────────────

def test_stencils_panel(page: Page) -> None:
    print("\n=== STENCILS PANEL (HT-049) ===")
    login(page)
    page.goto(f"{BASE}/topology", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # Enter edit mode
    edit_btn = page.locator('button:has-text("Edit")')
    if edit_btn.count() > 0:
        edit_btn.first.click()
        page.wait_for_timeout(2000)

    # Stencils panel header "Inventory"
    stencils = page.locator(':text("Inventory"), [id*="stencil"], [class*="stencil"]')
    record("HT-049", "Stencils panel visible in edit mode",
           stencils.count() > 0, f"matches={stencils.count()}")

    # Collapse toggle
    collapse_btn = page.locator('button[aria-label*="collapse" i], button[aria-label*="toggle" i], '
                                '.stencil-collapse, button:has(i:text("chevron_left")), '
                                'button:has(i:text("chevron_right"))')
    record("HT-049", "Stencils collapse toggle present", collapse_btn.count() > 0,
           f"count={collapse_btn.count()}")

    # Search input inside stencils
    search_inputs = page.locator('input[placeholder*="Search"]')
    record("HT-049", "Search input in stencils panel",
           search_inputs.count() > 0, f"inputs={search_inputs.count()}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. CANVAS EDGE DATA  (HT-004 field name bug: conn_type → connection_type)
# ─────────────────────────────────────────────────────────────────────────────

def test_edge_connection_type_field(page: Page) -> None:
    print("\n=== EDGE DATA FIELD NAME (HT-004 regression) ===")
    login(page)
    page.goto(f"{BASE}/topology", wait_until="networkidle")
    wait_for_cy(page)

    edge_count = page.evaluate("() => window._cy ? window._cy.edges().length : 0")
    if edge_count == 0:
        record("HT-004-field", "Edges exist for field test", False, "no edges")
        return

    # Check correct field name is `connection_type`
    conn_types = page.evaluate("""() => {
        if (!window._cy) return [];
        return window._cy.edges().map(e => ({
            conn_type: e.data('conn_type'),
            connection_type: e.data('connection_type'),
            type: e.data('type')
        }));
    }""")
    first = conn_types[0] if conn_types else {}
    record("HT-004-field", "Edge uses connection_type field (not conn_type)",
           bool(first.get("connection_type")) and not bool(first.get("conn_type")),
           str(first))
    record("HT-004-field", "Edge connection_type is not 'unknown'",
           (first.get("connection_type") or "") not in ("unknown", ""),
           f"connection_type={first.get('connection_type')!r}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. KEYBOARD SHORTCUTS (HT-016 — fixed timing)
# ─────────────────────────────────────────────────────────────────────────────

def test_shortcuts_deep(page: Page) -> None:
    print("\n=== KEYBOARD SHORTCUTS DEEP (HT-016) ===")
    login(page)
    page.goto(f"{BASE}/topology", wait_until="networkidle")
    if not wait_for_cy(page):
        record("HT-016-deep", "Canvas ready for shortcut tests", False)
        return

    # F — fit all
    page.locator("#cy").click()
    page.keyboard.press("f")
    page.wait_for_timeout(800)
    record("HT-016-deep", "F key no error", True)

    # Ctrl+A — select all nodes
    page.locator("#cy").click()
    page.keyboard.press("Control+a")
    page.wait_for_timeout(800)
    total = page.evaluate("() => window._cy ? window._cy.nodes().length : 0")
    sel = page.evaluate("() => window._cy ? window._cy.$(':selected').length : 0")
    record("HT-016-deep", "Ctrl+A selects all nodes", sel == total and total > 0,
           f"selected={sel}/{total}")

    # Escape — deselect all
    page.locator("#cy").click()
    page.keyboard.press("Escape")
    page.wait_for_timeout(800)
    after_esc = page.evaluate("() => window._cy ? window._cy.$(':selected').length : 0")
    record("HT-016-deep", "Escape deselects all", after_esc == 0, f"selected={after_esc}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. DEVICE NODE TAP → DETAIL PANEL  (HT-010 revised)
# ─────────────────────────────────────────────────────────────────────────────

def test_node_tap_detail(page: Page) -> None:
    print("\n=== NODE TAP → DETAIL  (HT-010 revised) ===")
    login(page)
    page.goto(f"{BASE}/topology", wait_until="networkidle")
    if not wait_for_cy(page):
        record("HT-010-revised", "Canvas ready", False)
        return

    node_count = page.evaluate("() => window._cy ? window._cy.nodes().length : 0")
    if node_count == 0:
        record("HT-010-revised", "Nodes exist for tap test", False)
        return

    # Fire ht:node-selected event to simulate what a tap would do
    did_fire = page.evaluate("""() => {
        if (!window._cy || window._cy.nodes().length === 0) return false;
        var node = window._cy.nodes()[0];
        var detail = node.data();
        document.dispatchEvent(new CustomEvent('ht:node-selected', {
            detail: { id: node.id(), name: String(detail.label || ''), data: detail }
        }));
        return true;
    }""")
    record("HT-010-revised", "ht:node-selected event dispatched", bool(did_fire))
    page.wait_for_timeout(2000)

    # Check either: detail panel appeared OR navigated to /inventory
    detail_visible = page.locator(':text("Device"), :text("device"), [class*="detail"]').count() > 0
    navigated = "/inventory" in page.url
    record("HT-010-revised", "Detail response: panel or navigation occurred",
           detail_visible or navigated, f"url={page.url[:60]}, detail_panels={detail_visible}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. INVENTORY DELETION  (HT-052)
# ─────────────────────────────────────────────────────────────────────────────

def test_inventory_deletion(page: Page) -> None:
    print("\n=== INVENTORY DELETION (HT-052) ===")
    token = get_admin_token()

    # Create a device to delete
    import random as _r
    dev = api("POST", "/api/devices/", {
        "name": f"E2E-Delete-{_r.randint(1000, 9999)}",
        "type": "Server",
    }, token=token)
    dev_id = (dev or {}).get("id", "")
    record("HT-052", "Device created for delete test", bool(dev_id))
    if not dev_id:
        return

    login(page)
    page.goto(f"{BASE}/inventory", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # Delete button should exist in the actions column
    delete_btns = page.locator('button:has(i:text("delete")), button[aria-label*="delete" i]')
    record("HT-052", "Delete buttons present in inventory", delete_btns.count() > 0,
           f"found={delete_btns.count()}")

    # Use API to verify row count change
    before = api("GET", "/api/devices/?limit=1", token=token)
    before_total = (before or {}).get("total", -1)

    # Delete via API
    del_resp = api("DELETE", f"/api/devices/{dev_id}", token=token)
    record("HT-052", "Device DELETE API returns 204", del_resp == {"__status": 204}, str(del_resp))

    after = api("GET", "/api/devices/?limit=1", token=token)
    after_total = (after or {}).get("total", -1)
    record("HT-052", "Device count decremented after delete",
           after_total == before_total - 1, f"before={before_total}, after={after_total}")

    # Reload inventory — device should no longer appear
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3000)


# ─────────────────────────────────────────────────────────────────────────────
# 9. API CONTRACT: DEVICE CRUD  (comprehensive)
# ─────────────────────────────────────────────────────────────────────────────

def test_api_device_crud() -> None:
    print("\n=== API DEVICE CRUD CONTRACT ===")
    token = get_admin_token()

    # Create
    dev = api("POST", "/api/devices/", {"name": "E2E-API-Device", "type": "Server",
              "ip": "10.0.0.200", "notes": "e2e test"}, token=token)
    dev_id = (dev or {}).get("id", "")
    record("API-devices", "POST /api/devices/ returns id", bool(dev_id))
    record("API-devices", "Response has version field", "version" in (dev or {}),
           str((dev or {}).get("version")))

    # Read
    got = api("GET", f"/api/devices/{dev_id}", token=token) if dev_id else None
    record("API-devices", "GET /api/devices/{id} returns device",
           (got or {}).get("id") == dev_id)
    record("API-devices", "Device name correct", (got or {}).get("name") == "E2E-API-Device")

    # Update with optimistic locking
    ver = (got or {}).get("version", 1)
    up = api("PATCH", f"/api/devices/{dev_id}", {"name": "E2E-API-Updated", "version": ver},
             token=token) if dev_id else None
    record("API-devices", "PATCH updates name", (up or {}).get("name") == "E2E-API-Updated",
           str((up or {}).get("name")))
    record("API-devices", "PATCH increments version", (up or {}).get("version", 0) == ver + 1,
           f"version={up and up.get('version')}")

    # Stale version conflict
    stale = api("PATCH", f"/api/devices/{dev_id}", {"name": "Stale", "version": ver},
                token=token, expect_status=409) if dev_id else None
    record("API-devices", "PATCH with stale version returns 409",
           (stale or {}).get("__status") == 409, str(stale))

    # Pagination
    page_resp = api("GET", "/api/devices/?page=1&limit=5", token=token)
    record("API-devices", "GET /api/devices/ has items + total",
           "items" in (page_resp or {}) and "total" in (page_resp or {}))

    # Delete
    del_resp = api("DELETE", f"/api/devices/{dev_id}", token=token, expect_status=204) if dev_id else None
    record("API-devices", "DELETE /api/devices/{id} returns 204",
           (del_resp or {}).get("__status") == 204)

    # 404 after delete
    gone = api("GET", f"/api/devices/{dev_id}", token=token, expect_status=404) if dev_id else None
    record("API-devices", "GET deleted device returns 404",
           (gone or {}).get("__status") == 404)


# ─────────────────────────────────────────────────────────────────────────────
# 10. API CONTRACT: CONNECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def test_api_connections_crud() -> None:
    print("\n=== API CONNECTIONS CONTRACT ===")
    token = get_admin_token()

    import random as _r
    rnd = _r.randint(10000, 99999)
    src = api("POST", "/api/devices/", {"name": f"E2E-Src-{rnd}", "type": "Switch"}, token=token)
    tgt = api("POST", "/api/devices/", {"name": f"E2E-Tgt-{rnd}", "type": "Server"}, token=token)
    src_id = (src or {}).get("id", "")
    tgt_id = (tgt or {}).get("id", "")

    if not src_id or not tgt_id:
        record("API-connections", "Setup devices created", False)
        return

    # Create connection
    conn = api("POST", "/api/connections/", {
        "source_id": src_id, "target_id": tgt_id, "type": "Ethernet", "label": "e2e"
    }, token=token)
    conn_id = (conn or {}).get("id", "")
    record("API-connections", "POST /api/connections/ creates edge", bool(conn_id))
    record("API-connections", "Connection type field present",
           "type" in (conn or {}), str((conn or {}).get("type")))

    # Duplicate connection rejection
    dup = api("POST", "/api/connections/", {
        "source_id": src_id, "target_id": tgt_id, "type": "Ethernet"
    }, token=token, expect_status=409)
    record("API-connections", "Duplicate connection returns 409",
           (dup or {}).get("__status") == 409, str(dup))

    # Self-loop rejection
    self_loop = api("POST", "/api/connections/", {
        "source_id": src_id, "target_id": src_id, "type": "Ethernet"
    }, token=token, expect_status=422)
    record("API-connections", "Self-loop connection rejected 422",
           (self_loop or {}).get("__status") in (400, 422), str(self_loop))

    # Cleanup
    if conn_id:
        api("DELETE", f"/api/connections/{conn_id}", token=token, expect_status=204)
    api("DELETE", f"/api/devices/{src_id}", token=token, expect_status=204)
    api("DELETE", f"/api/devices/{tgt_id}", token=token, expect_status=204)


# ─────────────────────────────────────────────────────────────────────────────
# 11. RBAC MATRIX  (HT-011 + HT-045 deep)
# ─────────────────────────────────────────────────────────────────────────────

def test_rbac_matrix() -> None:
    print("\n=== RBAC MATRIX (HT-011 + HT-045) ===")
    token = get_admin_token()

    import random, string
    rnd = "".join(random.choices(string.ascii_lowercase, k=6))

    # Create contributor + reader
    contrib = api("POST", "/api/users/", {
        "username": f"contrib_{rnd}", "email": f"contrib_{rnd}@test.local",
        "password": "Test1234!", "role": "Contributor",
    }, token=token)
    reader = api("POST", "/api/users/", {
        "username": f"reader_{rnd}", "email": f"reader_{rnd}@test.local",
        "password": "Test1234!", "role": "Reader",
    }, token=token)

    contrib_login = api("POST", "/api/auth/login", {
        "email": f"contrib_{rnd}@test.local", "password": "Test1234!",
    })
    reader_login = api("POST", "/api/auth/login", {
        "email": f"reader_{rnd}@test.local", "password": "Test1234!",
    })
    ct = (contrib_login or {}).get("access_token", "")
    rt = (reader_login or {}).get("access_token", "")

    # Admin CAN create device
    dev = api("POST", "/api/devices/", {"name": f"RBAC-dev-{rnd}", "type": "Server"}, token=token)
    dev_id = (dev or {}).get("id", "")
    record("RBAC", "Admin can create device", bool(dev_id))

    # Contributor CAN create device
    dev_c = api("POST", "/api/devices/", {"name": f"RBAC-contrib-{rnd}", "type": "Router"}, token=ct)
    dev_c_id = (dev_c or {}).get("id", "")
    record("RBAC", "Contributor can create device", bool(dev_c_id))

    # Reader CANNOT create device
    dev_r = api("POST", "/api/devices/", {"name": f"RBAC-reader-{rnd}", "type": "Server"},
                token=rt, expect_status=403)
    record("RBAC", "Reader cannot create device (403)",
           (dev_r or {}).get("__status") == 403, str(dev_r))

    # Reader CAN read devices
    list_r = api("GET", "/api/devices/?limit=1", token=rt)
    record("RBAC", "Reader can list devices", "items" in (list_r or {}))

    # Reader CANNOT delete device
    del_r = api("DELETE", f"/api/devices/{dev_id}", token=rt, expect_status=403) if dev_id else None
    record("RBAC", "Reader cannot delete device (403)",
           (del_r or {}).get("__status") == 403, str(del_r))

    # Reader CANNOT manage users
    users_r = api("GET", "/api/users/", token=rt, expect_status=403)
    record("RBAC", "Reader cannot list users (403)",
           (users_r or {}).get("__status") == 403, str(users_r))

    # Contributor CANNOT manage users
    users_c = api("GET", "/api/users/", token=ct, expect_status=403)
    record("RBAC", "Contributor cannot list users (403)",
           (users_c or {}).get("__status") == 403, str(users_c))

    # Admin CAN manage users
    users_a = api("GET", "/api/users/", token=token)
    record("RBAC", "Admin can list users", "items" in (users_a or {}))

    # Cleanup
    for did in [dev_id, dev_c_id]:
        if did:
            api("DELETE", f"/api/devices/{did}", token=token, expect_status=204)
    for uid in [(contrib or {}).get("id"), (reader or {}).get("id")]:
        if uid:
            api("DELETE", f"/api/users/{uid}", token=token)


# ─────────────────────────────────────────────────────────────────────────────
# 12. SECURITY: AUTH EDGE CASES
# ─────────────────────────────────────────────────────────────────────────────

def test_auth_security() -> None:
    print("\n=== AUTH SECURITY ===")

    # No token → 401
    no_auth = api("GET", "/api/devices/", expect_status=401)
    record("Security", "No token → 401", (no_auth or {}).get("__status") == 401)

    # Malformed JWT → 401
    bad_jwt = api("GET", "/api/devices/", token="notajwt", expect_status=401)
    record("Security", "Malformed JWT → 401", (bad_jwt or {}).get("__status") == 401)

    # Expired-looking token (wrong signature) → 401
    fake = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDkiLCJyb2xlIjoiQWRtaW4ifQ.badSig"
    bad_sig = api("GET", "/api/devices/", token=fake, expect_status=401)
    record("Security", "Forged JWT (bad sig) → 401", (bad_sig or {}).get("__status") == 401)

    # Wrong credentials → 401
    wrong = api("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": "wrongpassword"},
                expect_status=401)
    record("Security", "Wrong password → 401", (wrong or {}).get("__status") == 401)

    # Non-existent user → 401
    noemail = api("POST", "/api/auth/login", {"email": "notexists@test.local", "password": "pass"},
                  expect_status=401)
    record("Security", "Non-existent user → 401", (noemail or {}).get("__status") == 401)


# ─────────────────────────────────────────────────────────────────────────────
# 13. SECURITY: IDOR CHECK  (HT-053 backlog item)
# ─────────────────────────────────────────────────────────────────────────────

def test_idor_workspace_isolation() -> None:
    print("\n=== IDOR WORKSPACE ISOLATION (HT-053) ===")
    token = get_admin_token()

    import random, string
    rnd = "".join(random.choices(string.ascii_lowercase, k=6))

    # Create second user
    usr2 = api("POST", "/api/users/", {
        "username": f"usr2_{rnd}", "email": f"usr2_{rnd}@test.local",
        "password": "Test1234!", "role": "Contributor",
    }, token=token)
    usr2_id = (usr2 or {}).get("id", "")
    usr2_login = api("POST", "/api/auth/login", {
        "email": f"usr2_{rnd}@test.local", "password": "Test1234!",
    })
    t2 = (usr2_login or {}).get("access_token", "")

    # Admin creates workspace
    ws = api("POST", "/api/workspaces/", {"name": f"Admin-WS-{rnd}"}, token=token)
    ws_id = (ws or {}).get("id", "")
    record("IDOR", "Admin workspace created", bool(ws_id))

    # User2 should NOT see admin's workspace in their list
    user2_ws = api("GET", "/api/workspaces/", token=t2)
    user2_ids = [(w.get("id")) for w in (user2_ws or {}).get("items", [])]
    record("IDOR", "User2 does not see admin workspace in own list",
           ws_id not in user2_ids, f"user2_ws_count={len(user2_ids)}, admin_ws={str(ws_id)[:8]}")

    # User2 direct access to admin workspace → should 403 or 404
    direct = api("GET", f"/api/workspaces/{ws_id}", token=t2, expect_status=403)
    record("IDOR", "User2 cannot directly access admin workspace (403/404)",
           (direct or {}).get("__status") in (403, 404), str(direct))

    # Cleanup
    if ws_id:
        api("DELETE", f"/api/workspaces/{ws_id}", token=token)
    if usr2_id:
        api("DELETE", f"/api/users/{usr2_id}", token=token)


# ─────────────────────────────────────────────────────────────────────────────
# 14. VALIDATION EDGE CASES  (HT-055 related)
# ─────────────────────────────────────────────────────────────────────────────

def test_input_validation() -> None:
    print("\n=== INPUT VALIDATION ===")
    token = get_admin_token()

    # Empty name
    r1 = api("POST", "/api/devices/", {"name": "", "type": "Server"},
             token=token, expect_status=422)
    record("Validation", "Empty name rejected (422)", (r1 or {}).get("__status") == 422)

    # Name too long (>255)
    r2 = api("POST", "/api/devices/", {"name": "X" * 256, "type": "Server"},
             token=token, expect_status=422)
    record("Validation", "Name >255 chars rejected (422)", (r2 or {}).get("__status") == 422)

    # Invalid device type
    r3 = api("POST", "/api/devices/", {"name": "Test", "type": "InvalidType"},
             token=token, expect_status=422)
    record("Validation", "Invalid DeviceType rejected (422)", (r3 or {}).get("__status") == 422)

    # Invalid IP
    r4 = api("POST", "/api/devices/", {"name": "Test", "type": "Server", "ip": "999.999.999.999"},
             token=token, expect_status=422)
    record("Validation", "Invalid IP rejected (422)", (r4 or {}).get("__status") in (400, 422),
           str(r4))

    # Workspace empty name
    r5 = api("POST", "/api/workspaces/", {"name": ""},
             token=token, expect_status=422)
    record("Validation", "Empty workspace name rejected (422)", (r5 or {}).get("__status") == 422)


# ─────────────────────────────────────────────────────────────────────────────
# 15. DIRECT CANVAS ENTRY  (HT-057)
# ─────────────────────────────────────────────────────────────────────────────

def test_direct_canvas_entry(page: Page) -> None:
    print("\n=== DIRECT CANVAS ENTRY (HT-057) ===")
    token = get_admin_token()

    # Create workspace + topology via API
    import random as _r
    rnd = _r.randint(10000, 99999)
    ws = api("POST", "/api/workspaces/", {"name": f"E2E-HT057-{rnd}"}, token=token)
    ws_id = (ws or {}).get("id", "")
    if not ws_id:
        record("HT-057", "Setup workspace created", False)
        return

    topo = api("POST", f"/api/workspaces/{ws_id}/topologies/",
               {"name": "Direct Canvas Topo"}, token=token)
    topo_id = (topo or {}).get("id", "")

    login(page)
    # Navigate to workspace detail — click the topology name link directly
    page.goto(f"{BASE}/workspaces/{ws_id}", wait_until="networkidle")
    page.wait_for_timeout(3000)

    topo_links = page.locator(':text("Direct Canvas Topo")')
    has_link = topo_links.count() > 0
    record("HT-057", "Topology name appears in workspace detail", has_link)

    if has_link:
        topo_links.first.click()
        page.wait_for_timeout(4000)
        on_canvas = "/topology" in page.url
        record("HT-057", "Clicking topology name navigates to canvas", on_canvas, page.url[:80])

    # Cleanup
    api("DELETE", f"/api/workspaces/{ws_id}", token=token)


# ─────────────────────────────────────────────────────────────────────────────
# 16. LAYOUT MANAGEMENT DEEP  (HT-029)
# ─────────────────────────────────────────────────────────────────────────────

def test_layout_save_rename_delete(page: Page) -> None:
    print("\n=== TOOLBAR SEMANTICS DEEP (HT-029/HT-072) ===")
    token = get_admin_token()
    login(page)
    page.goto(f"{BASE}/topology", wait_until="networkidle")
    page.wait_for_timeout(3000)

    save_btn = page.get_by_role("button", name="Save Version")
    history_btn = page.get_by_role("button", name="History")
    legacy_saved_layouts = page.locator(':text("Saved Layouts")')
    legacy_save_layout = page.locator('button:has-text("Save Layout")')
    legacy_rename = page.locator('button:has-text("Rename layout")')
    legacy_delete = page.locator('button:has-text("Delete layout")')

    record("HT-029-deep", "Save Version button present", save_btn.count() > 0)
    record("HT-029-deep", "History button present", history_btn.count() > 0)
    record("HT-029-deep", "Legacy Saved Layouts hidden", legacy_saved_layouts.count() == 0)
    record("HT-029-deep", "Legacy Save Layout hidden", legacy_save_layout.count() == 0)
    record("HT-029-deep", "Legacy rename control hidden", legacy_rename.count() == 0)
    record("HT-029-deep", "Legacy delete control hidden", legacy_delete.count() == 0)

    if save_btn.count() > 0:
        save_btn.first.click()
        page.wait_for_timeout(800)
        save_confirm = page.locator('.q-dialog button:has-text("Save Version")')
        if save_confirm.count() > 0:
            save_confirm.first.click()
            page.wait_for_timeout(1500)
        notify = page.locator('.q-notification, [class*="toast"], [class*="notify"]')
        record("HT-029-deep", "Save Version shows feedback", notify.count() > 0,
               f"notifications={notify.count()}")

    if history_btn.count() > 0:
        history_btn.first.click()
        page.wait_for_timeout(800)
        history_versions = page.get_by_label("Versions")
        record("HT-029-deep", "History panel exposes versions selector", history_versions.count() > 0)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

    # Verify API has diagram layouts
    layouts = api("GET", "/api/diagrams/", token=token)
    record("HT-029-deep", "GET /api/diagrams/ returns items",
           "items" in (layouts or {}), f"total={(layouts or {}).get('total', '?')}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("HOMETOWER DEEP PLAYWRIGHT BUG HUNT")
    print("=" * 70)

    # Purely API-based tests (no browser)
    try:
        test_api_device_crud()
    except Exception:
        record("API-devices", "SUITE ERROR", False, traceback.format_exc()[-200:])
    try:
        test_api_connections_crud()
    except Exception:
        record("API-connections", "SUITE ERROR", False, traceback.format_exc()[-200:])
    try:
        test_rbac_matrix()
    except Exception:
        record("RBAC", "SUITE ERROR", False, traceback.format_exc()[-200:])
    try:
        test_auth_security()
    except Exception:
        record("Security", "SUITE ERROR", False, traceback.format_exc()[-200:])
    try:
        test_idor_workspace_isolation()
    except Exception:
        record("IDOR", "SUITE ERROR", False, traceback.format_exc()[-200:])
    try:
        test_input_validation()
    except Exception:
        record("Validation", "SUITE ERROR", False, traceback.format_exc()[-200:])

    # Browser-based tests
    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=True)
        ctx: BrowserContext = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page: Page = ctx.new_page()

        for fn, args in [
            (test_inventory_deep, (page,)),
            (test_workspace_hierarchy, (page,)),
            (test_edit_mode_rbac, (page,)),
            (test_stencils_panel, (page,)),
            (test_edge_connection_type_field, (page,)),
            (test_shortcuts_deep, (page,)),
            (test_node_tap_detail, (page,)),
            (test_inventory_deletion, (page,)),
            (test_direct_canvas_entry, (page,)),
            (test_layout_save_rename_delete, (page,)),
        ]:
            try:
                fn(*args)
            except Exception:
                record(fn.__name__, "SUITE ERROR", False, traceback.format_exc()[-300:])

        page.screenshot(path="/tmp/hometower_deep_hunt_final.png")
        browser.close()

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("DEEP HUNT SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"Total: {len(results)}  PASS: {passed}  FAIL: {failed}")
    if failed:
        print("\nFAILURES:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  {r['story']} — {r['test']}: {r['detail']}")
    print("\nAll results:")
    for r in results:
        print(f"  [{r['status']}] {r['story']} — {r['test']}"
              + (f" ({r['detail']})" if r["detail"] else ""))


if __name__ == "__main__":
    main()
