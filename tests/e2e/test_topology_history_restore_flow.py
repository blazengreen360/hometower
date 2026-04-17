"""Playwright regression for HT-072 history selection + restore flow.

Run directly (requires server on port 8080):
    python tests/e2e/test_topology_history_restore_flow.py
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
    page.wait_for_timeout(1200)


def wait_for_cy(page: Page, timeout_ms: int = 15000) -> bool:
    for _ in range(timeout_ms // 300):
        ready = page.evaluate(
            "() => typeof window._cy !== 'undefined' && window._cy !== null && typeof window._cy.nodes === 'function'"
        )
        if ready:
            return True
        page.wait_for_timeout(300)
    return False


def add_probe_node(page: Page, node_id: str, x: int, y: int) -> None:
    page.evaluate(
        """(payload) => {
            if (!window._cy) return;
            window._cy.add({
                group: 'nodes',
                classes: 'draft',
                data: {
                    id: payload.id,
                    draft: true,
                    draft_name: payload.id,
                    draft_type: 'Server',
                    label: payload.id,
                    raw_name: payload.id,
                    device_type: 'Server',
                    raw_device_type: 'Server',
                    shape: 'rectangle',
                    status: 'Active'
                },
                position: {x: payload.x, y: payload.y}
            });
        }""",
        {"id": node_id, "x": x, "y": y},
    )


def set_node_size(page: Page, node_id: str, width: int, height: int) -> None:
    page.evaluate(
        """(payload) => {
            if (!window._cy) return;
            var node = window._cy.getElementById(payload.id);
            if (!node || !node.length) return;
            node = node.first();
            node.style('width', payload.width);
            node.style('height', payload.height);
        }""",
        {"id": node_id, "width": width, "height": height},
    )
    page.wait_for_timeout(250)


def read_node_size(page: Page, node_id: str) -> dict[str, object]:
    return page.evaluate(
        """(targetId) => {
            if (!window._cy) return { exists: false };
            var node = window._cy.getElementById(targetId);
            if (!node || !node.length) return { exists: false };
            node = node.first();
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


def save_version(page: Page) -> None:
    page.get_by_role("button", name="Save Version").first.click()
    page.wait_for_timeout(1600)


def run_history_restore_flow_test() -> int:
    token = login_api()
    seed = int(time.time())

    workspace = api("POST", "/api/workspaces/", {"name": f"HT072-WS-{seed}"}, token=token)
    ws_id = str(workspace.get("id", ""))
    if not ws_id:
        print(f"FAIL: workspace creation failed: {workspace}")
        return 1

    topology = api(
        "POST",
        f"/api/workspaces/{ws_id}/topologies/",
        {"name": f"HT072-Topo-{seed}"},
        token=token,
    )
    topo_id = str(topology.get("id", ""))
    if not topo_id:
        print(f"FAIL: topology creation failed: {topology}")
        return 1

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

        edit_btn = page.locator('button:has-text("Edit")')
        if edit_btn.count() == 0:
            print("FAIL: no Edit button")
            browser.close()
            return 1
        edit_btn.first.click()
        page.wait_for_timeout(800)

        tracked_node = f"history-size-{seed}"
        add_probe_node(page, tracked_node, 260, 220)
        set_node_size(page, tracked_node, 140, 96)
        v1_size = read_node_size(page, tracked_node)
        save_version(page)
        page.wait_for_timeout(1200)

        set_node_size(page, tracked_node, 260, 180)
        v2_size = read_node_size(page, tracked_node)
        save_version(page)
        page.wait_for_timeout(1200)

        history_before = api("GET", f"/api/topologies/{topo_id}/history?limit=20", token=token)
        items_before = history_before.get("items", [])
        if not isinstance(items_before, list) or len(items_before) < 2:
            print(f"FAIL: expected at least 2 history entries, got: {history_before}")
            browser.close()
            return 1

        total_before = int(history_before.get("total", len(items_before)))
        newest_before = items_before[0]
        older_entry = items_before[1]

        page.get_by_role("button", name="History").first.click()
        page.wait_for_timeout(500)

        versions = page.get_by_label("Versions")
        if versions.count() == 0:
            print("FAIL: history versions selector missing")
            browser.close()
            return 1

        versions.first.click()
        page.wait_for_timeout(300)

        options = page.locator(".q-menu .q-item")
        if options.count() < 2:
            print("FAIL: history selector does not show an older option")
            browser.close()
            return 1
        options.nth(1).click()
        page.wait_for_timeout(300)

        page.get_by_role("button", name="Restore Selected").first.click()
        page.wait_for_timeout(300)

        restore_confirm = page.locator('.q-dialog button:has-text("Restore")')
        if restore_confirm.count() == 0:
            print("FAIL: restore confirmation did not open after selecting older version")
            browser.close()
            return 1
        restore_confirm.first.click()
        page.wait_for_timeout(1800)

        restored_size = read_node_size(page, tracked_node)

        history_after = api("GET", f"/api/topologies/{topo_id}/history?limit=20", token=token)
        items_after = history_after.get("items", [])
        if not isinstance(items_after, list) or not items_after:
            print(f"FAIL: history after restore malformed: {history_after}")
            browser.close()
            return 1

        total_after = int(history_after.get("total", len(items_after)))
        latest_after = items_after[0]

        browser.close()

    if total_after != total_before + 1:
        print(
            "FAIL: restore did not append a new latest history entry "
            f"(before={total_before}, after={total_after})"
        )
        return 1

    if latest_after.get("action") != "restore":
        print(f"FAIL: latest history action is not restore: {latest_after}")
        return 1

    if latest_after.get("restored_from_history_entry_id") != older_entry.get("id"):
        print(
            "FAIL: restore did not target selected older entry "
            f"(expected={older_entry.get('id')}, got={latest_after.get('restored_from_history_entry_id')})"
        )
        return 1

    after_ids = {str(item.get("id", "")) for item in items_after}
    if str(older_entry.get("id", "")) not in after_ids or str(newest_before.get("id", "")) not in after_ids:
        print("FAIL: previous history entries were not preserved after restore")
        return 1

    if not restored_size.get("exists"):
        print("FAIL: restored tracked node is missing")
        return 1

    restored_delta_w = abs(_num(restored_size.get("width")) - _num(v1_size.get("width")))
    restored_delta_h = abs(_num(restored_size.get("height")) - _num(v1_size.get("height")))
    restored_style_delta_w = abs(_num(restored_size.get("styleWidth")) - _num(v1_size.get("styleWidth")))
    restored_style_delta_h = abs(_num(restored_size.get("styleHeight")) - _num(v1_size.get("styleHeight")))
    v2_delta_w = abs(_num(restored_size.get("width")) - _num(v2_size.get("width")))
    v2_delta_h = abs(_num(restored_size.get("height")) - _num(v2_size.get("height")))

    if not (
        restored_delta_w <= 2
        and restored_delta_h <= 2
        and restored_style_delta_w <= 2
        and restored_style_delta_h <= 2
        and (v2_delta_w > 20 or v2_delta_h > 20)
    ):
        print(
            "FAIL: restored node dimensions did not revert to selected version "
            f"(restored={restored_size}, v1={v1_size}, v2={v2_size})"
        )
        return 1

    print("PASS: HT-072 history selection + restore flow works in browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_history_restore_flow_test())
