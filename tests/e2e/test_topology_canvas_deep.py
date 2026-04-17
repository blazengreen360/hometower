"""Deep Playwright canvas test for topology-scoped load/save persistence.

Run directly (requires server on port 8080):
    python tests/e2e/test_topology_canvas_deep.py
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:8080"
ADMIN_EMAIL = "admin@hometower.local"
ADMIN_PASS = "changeme_on_first_boot"


def api(method: str, path: str, body: dict[str, object] | None = None, token: str = "") -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        parsed["__status"] = exc.code
        return parsed


def login_api() -> str:
    data = api("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    token = str(data.get("access_token", ""))
    if not token:
        raise RuntimeError(f"API login failed: {data}")
    return token


def login_ui(page: Page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.locator('input[type="text"], input[type="email"]').first.fill(ADMIN_EMAIL)
    page.locator('input[type="password"]').first.fill(ADMIN_PASS)
    page.locator('button:has-text("Log in")').first.click()
    page.wait_for_timeout(1500)


def wait_for_cy(page: Page, timeout_ms: int = 15000) -> bool:
    for _ in range(timeout_ms // 300):
        ready = page.evaluate(
            "() => typeof window._cy !== 'undefined' && window._cy !== null && typeof window._cy.nodes === 'function'"
        )
        if ready:
            return True
        page.wait_for_timeout(300)
    return False


def select_node(page: Page, node_id: str) -> None:
    page.evaluate(
        """(targetId) => {
            if (!window._cy) return;
            var node = window._cy.getElementById(targetId);
            if (!node || !node.length) return;
            window._cy.nodes().unselect();
            node.select();
        }""",
        node_id,
    )
    page.wait_for_timeout(250)


def overlay_visible(page: Page) -> bool:
    return bool(page.evaluate(
        """() => {
            var overlay = document.getElementById('ht-node-resize-overlay');
            if (!overlay) return false;
            var style = window.getComputedStyle(overlay);
            return style.display !== 'none' && style.visibility !== 'hidden';
        }"""
    ))


def drag_resize_handle(page: Page, direction: str, dx: float, dy: float) -> bool:
    handle = page.locator(f'#ht-node-resize-overlay [data-ht-resize-handle="{direction}"]')
    if handle.count() == 0:
        return False
    box = handle.first.bounding_box()
    if box is None:
        return False
    start_x = box["x"] + (box["width"] / 2)
    start_y = box["y"] + (box["height"] / 2)
    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(start_x + dx, start_y + dy)
    page.mouse.up()
    page.wait_for_timeout(350)
    return True


def read_node_size(page: Page, node_id: str) -> dict[str, object]:
    return page.evaluate(
        """(targetId) => {
            if (!window._cy) return { exists: false };
            var node = window._cy.getElementById(targetId);
            if (!node || !node.length) return { exists: false };
            return {
                exists: true,
                width: Number(node.width()),
                height: Number(node.height()),
                styleWidth: node.style('width'),
                styleHeight: node.style('height')
            };
        }""",
        node_id,
    )


def _num(value: object) -> float:
    text = str(value or "").replace("px", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def run_deep_canvas_test() -> int:
    token = login_api()
    workspaces = api("GET", "/api/workspaces/", token=token).get("items", [])
    if not isinstance(workspaces, list) or not workspaces:
        print("FAIL: no workspaces available")
        return 1
    ws = workspaces[0]
    ws_id = str(ws["id"])

    topologies = api("GET", f"/api/workspaces/{ws_id}/topologies/", token=token).get("items", [])
    if not isinstance(topologies, list) or not topologies:
        print(f"FAIL: no topologies in workspace {ws_id}")
        return 1
    topo = topologies[0]
    topo_id = str(topo["id"])

    url = f"{BASE}/topology?workspace_id={ws_id}&topology_id={topo_id}"
    print(f"Testing URL: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        login_ui(page)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        if not wait_for_cy(page):
            print("FAIL: Cytoscape not initialized")
            browser.close()
            return 1

        initial = page.evaluate(
            """() => ({
                nodes: window._cy.nodes().length,
                edges: window._cy.edges().length,
                htDiagramId: window._htDiagramId ?? null,
                htDiagramVersion: window._htDiagramVersion ?? null,
                readonly: window.HT_READONLY,
            })"""
        )
        print("Initial canvas state:", initial)

        resize_bridge_ready = page.evaluate(
            """() => (
                typeof window._htResizeSyncFromSelection === 'function'
                && typeof window._htResizeSetEnabled === 'function'
            )"""
        )
        if not resize_bridge_ready:
            print("FAIL: resize bridge is missing in the running app bundle (restart app and retry)")
            browser.close()
            return 1

        # Enter edit mode (required for save flow)
        edit_btn = page.locator('button:has-text("Edit")')
        if edit_btn.count() == 0:
            print("FAIL: no Edit button")
            browser.close()
            return 1
        edit_btn.first.click()
        page.wait_for_timeout(800)

        # Add a deterministic draft node directly to canvas for persistence check
        probe_id = f"draft-deep-{int(time.time())}"
        page.evaluate(
            """(nodeId) => {
                if (!window._cy) return;
                window._cy.add({
                    group: 'nodes',
                    classes: 'draft',
                    data: {
                        id: nodeId,
                        draft: true,
                        draft_name: 'Deep Probe',
                        draft_type: 'Server',
                        label: 'Deep Probe',
                        raw_name: 'Deep Probe',
                        device_type: 'Server',
                        raw_device_type: 'Server',
                        shape: 'rectangle',
                        status: 'Active'
                    },
                    position: {x: 320, y: 260}
                });
            }""",
            probe_id,
        )

        select_node(page, probe_id)
        if not overlay_visible(page):
            print("FAIL: resize overlay did not activate in edit mode")
            browser.close()
            return 1

        if not drag_resize_handle(page, "se", 120, 80):
            print("FAIL: resize handle is unavailable")
            browser.close()
            return 1

        resized_before_save = read_node_size(page, probe_id)
        print("Resized node state:", resized_before_save)
        if not resized_before_save.get("exists"):
            print("FAIL: probe node missing after resize interaction")
            browser.close()
            return 1
        if _num(resized_before_save.get("width")) <= 48 or _num(resized_before_save.get("height")) <= 48:
            print("FAIL: resize interaction did not increase node dimensions")
            browser.close()
            return 1

        # Save as a new version
        page.get_by_role("button", name="Save Version").first.click()
        page.wait_for_timeout(1500)

        # Resolve latest history entry and validate topology binding through its diagram
        history_payload = api("GET", f"/api/topologies/{topo_id}/history?limit=10", token=token)
        history_items = history_payload.get("items", []) if isinstance(history_payload, dict) else []
        if not isinstance(history_items, list) or not history_items:
            print("FAIL: topology history list response malformed")
            browser.close()
            return 1
        latest_history = history_items[0]
        created_diagram_id = latest_history.get("diagram_id")
        if not created_diagram_id:
            print("FAIL: latest history entry missing diagram_id")
            browser.close()
            return 1
        created = api("GET", f"/api/diagrams/{created_diagram_id}", token=token)
        if not isinstance(created, dict):
            print("FAIL: diagram detail response malformed")
            browser.close()
            return 1

        created_topology_id = created.get("topology_id")
        print("Created layout:", {"id": created.get("id"), "name": created.get("name"), "topology_id": created_topology_id})

        # Refresh the same topology URL and verify the probe node persists
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        if not wait_for_cy(page):
            print("FAIL: Cytoscape did not initialize after refresh")
            browser.close()
            return 1

        select_node(page, probe_id)
        view_overlay_visible = overlay_visible(page)

        edit_btn = page.locator('button:has-text("Edit")')
        if edit_btn.count() == 0:
            print("FAIL: no Edit button after refresh")
            browser.close()
            return 1
        edit_btn.first.click()
        page.wait_for_timeout(700)
        select_node(page, probe_id)
        edit_overlay_visible = overlay_visible(page)

        persisted = page.evaluate(
            """(nodeId) => ({
                exists: window._cy.getElementById(nodeId).length > 0,
                nodes: window._cy.nodes().length,
                htDiagramId: window._htDiagramId ?? null,
                htDiagramVersion: window._htDiagramVersion ?? null,
                width: window._cy.getElementById(nodeId).length > 0 ? Number(window._cy.getElementById(nodeId).first().width()) : 0,
                height: window._cy.getElementById(nodeId).length > 0 ? Number(window._cy.getElementById(nodeId).first().height()) : 0,
                styleWidth: window._cy.getElementById(nodeId).length > 0 ? window._cy.getElementById(nodeId).first().style('width') : null,
                styleHeight: window._cy.getElementById(nodeId).length > 0 ? window._cy.getElementById(nodeId).first().style('height') : null,
            })""",
            probe_id,
        )
        print("Post-refresh state:", persisted)

        browser.close()

    ok_topology_binding = str(created_topology_id) == topo_id
    ok_persisted = bool(persisted.get("exists"))
    size_delta_w = abs(_num(persisted.get("width")) - _num(resized_before_save.get("width")))
    size_delta_h = abs(_num(persisted.get("height")) - _num(resized_before_save.get("height")))
    style_delta_w = abs(_num(persisted.get("styleWidth")) - _num(resized_before_save.get("styleWidth")))
    style_delta_h = abs(_num(persisted.get("styleHeight")) - _num(resized_before_save.get("styleHeight")))
    ok_resize_persisted = size_delta_w <= 2 and size_delta_h <= 2 and style_delta_w <= 2 and style_delta_h <= 2
    ok_view_mode_hidden = not view_overlay_visible
    ok_edit_mode_visible = edit_overlay_visible

    if not ok_topology_binding:
        print(
            "FAIL: saved layout is not topology-scoped "
            f"(expected topology_id={topo_id}, got={created_topology_id})"
        )
        return 1
    if not ok_persisted:
        print("FAIL: saved canvas change missing after refresh")
        return 1
    if not ok_resize_persisted:
        print(
            "FAIL: resized dimensions did not persist across refresh "
            f"(node delta=({size_delta_w:.2f}, {size_delta_h:.2f}), "
            f"style delta=({style_delta_w:.2f}, {style_delta_h:.2f}))"
        )
        return 1
    if not ok_view_mode_hidden:
        print("FAIL: resize overlay should be inactive in view mode")
        return 1
    if not ok_edit_mode_visible:
        print("FAIL: resize overlay did not reactivate in edit mode")
        return 1

    print("PASS: deep topology canvas save/load persistence test")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_deep_canvas_test())
