"""Browser regression for HT-077 convert-to-container draft persistence.

This proof isolates the persistence contract downstream of the already-tested
context-menu dispatch: a draft node that is converted in-session must persist
the `container` class into personal-draft editor-state and still be a
container after reload, even if no later gesture occurs.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

from playwright.sync_api import Page, sync_playwright

BASE = os.getenv("HT_E2E_BASE_URL", "http://localhost:8080")
ADMIN_EMAIL = os.getenv("HT_E2E_ADMIN_EMAIL", "admin@hometower.local")
ADMIN_PASSWORD = os.getenv("HT_E2E_ADMIN_PASSWORD", "changeme_on_first_boot")


def _api(
    method: str,
    path: str,
    body: dict[str, object] | None = None,
    token: str = "",
) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(payload)
        except Exception:
            parsed = {"raw": payload}
        parsed["__status"] = exc.code
        return parsed


def _login_api() -> str:
    token = str(
        _api(
            "POST",
            "/api/auth/login",
            {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        ).get("access_token", "")
    )
    if not token:
        raise AssertionError("API login did not return an access token")
    return token


def _create_workspace_topology(token: str, suffix: str) -> tuple[str, str]:
    workspace = _api(
        "POST",
        "/api/workspaces/",
        {"name": f"ht077-ws-{suffix}"},
        token,
    )
    workspace_id = str(workspace.get("id", ""))
    if not workspace_id:
        raise AssertionError(f"Workspace creation failed: {workspace}")

    topology = _api(
        "POST",
        f"/api/workspaces/{workspace_id}/topologies/",
        {"name": f"ht077-topo-{suffix}"},
        token,
    )
    topology_id = str(topology.get("id", ""))
    if not topology_id:
        raise AssertionError(f"Topology creation failed: {topology}")

    return workspace_id, topology_id


def _seed_plain_draft(token: str, topology_id: str, node_id: str) -> int:
    payload = {
        "cytoscape_json": {
            "elements": {
                "nodes": [
                    {
                        "data": {
                            "id": node_id,
                            "draft": True,
                            "draft_name": "HT077 Draft",
                            "draft_type": "Server",
                            "label": "HT077 Draft",
                            "raw_name": "HT077 Draft",
                            "device_type": "Server",
                            "raw_device_type": "Server",
                            "shape": "rectangle",
                            "status": "Active",
                        },
                        "position": {"x": 280, "y": 220},
                        "classes": "draft",
                    }
                ],
                "edges": [],
            },
            "zoom": 1,
            "pan": {"x": 0, "y": 0},
            "collapsedNodes": [],
        }
    }
    response = _api("PUT", f"/api/topologies/{topology_id}/personal-draft", payload, token)
    status = int(response.get("__status", 200))
    if status >= 400:
        raise AssertionError(f"Draft seed failed: {response}")
    version = response.get("version")
    if not isinstance(version, int):
        raise AssertionError(f"Draft seed did not return a version: {response}")
    return version


def _login_ui(page: Page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.locator('input[type="text"], input[type="email"]').first.fill(ADMIN_EMAIL)
    page.locator('input[type="password"]').first.fill(ADMIN_PASSWORD)
    page.locator('button:has-text("Log in"), button:has-text("Login")').first.click()
    page.wait_for_timeout(1500)
    if "/login" in page.url:
        raise AssertionError("UI login did not complete successfully")


def _wait_for_canvas(page: Page, timeout_ms: int = 15000) -> bool:
    page.evaluate(
        """() => {
            var el = document.getElementById('cy');
            if (el && el.clientHeight === 0) el.style.height = '600px';
        }"""
    )
    for _ in range(max(timeout_ms // 300, 1)):
        ready = page.evaluate(
            "() => typeof window._cy !== 'undefined' && window._cy !== null "
            "&& typeof window._cy.nodes === 'function'"
        )
        if ready:
            return True
        page.wait_for_timeout(300)
    return False


def _ensure_edit_mode(page: Page) -> None:
    if bool(page.evaluate("() => window.HT_READONLY === false")):
        return
    edit_button = page.locator('button:has-text("Edit")').first
    if edit_button.count() == 0:
        raise AssertionError("Edit button was not found on the topology page")
    edit_button.click()
    page.wait_for_timeout(800)
    if bool(page.evaluate("() => window.HT_READONLY !== false")):
        raise AssertionError("Topology page did not enter edit mode")


def _find_node_entry(payload: dict[str, object], node_id: str) -> dict[str, object] | None:
    cytoscape_json = payload.get("cytoscape_json")
    if not isinstance(cytoscape_json, dict):
        return None
    elements = cytoscape_json.get("elements")
    if isinstance(elements, dict):
        nodes = elements.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                data = node.get("data")
                if isinstance(data, dict) and str(data.get("id", "")) == node_id:
                    return node
    if isinstance(elements, list):
        for entry in elements:
            if not isinstance(entry, dict):
                continue
            data = entry.get("data")
            if isinstance(data, dict) and str(data.get("id", "")) == node_id:
                return entry
    return None


def _node_classes(node_entry: dict[str, object] | None) -> list[str]:
    if not isinstance(node_entry, dict):
        return []
    classes = node_entry.get("classes")
    return _class_tokens(classes)


def _class_tokens(classes: object) -> list[str]:
    if isinstance(classes, str):
        return [part for part in classes.split(" ") if part]
    if isinstance(classes, list):
        return [str(part) for part in classes if str(part)]
    return []


def _poll_editor_state_until_version(token: str, topology_id: str, min_version: int, timeout_s: float = 10.0) -> dict[str, object] | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        payload = _api("GET", f"/api/topologies/{topology_id}/editor-state", token=token)
        if int(payload.get("__status", 200)) < 400 and int(payload.get("draft_version", 0) or 0) >= min_version:
            return payload
        time.sleep(0.25)
    return None


def run_regression() -> None:
    token = _login_api()
    suffix = uuid.uuid4().hex[:8]
    workspace_id, topology_id = _create_workspace_topology(token, suffix)
    node_id = f"draft-ht077-{suffix}"
    _seed_plain_draft(token, topology_id, node_id)

    before_convert = _api("GET", f"/api/topologies/{topology_id}/editor-state", token=token)
    preconvert_version = int(before_convert.get("draft_version", 0) or 0)
    if preconvert_version <= 0:
        raise AssertionError(f"Expected seeded draft_version before convert, got: {before_convert}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        _login_ui(page)
        page.goto(
            f"{BASE}/topology?workspace_id={workspace_id}&topology_id={topology_id}",
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(1200)
        if not _wait_for_canvas(page, timeout_ms=20000):
            browser.close()
            raise AssertionError("Cytoscape did not initialize for the seeded topology draft")

        _ensure_edit_mode(page)
        live_before = page.evaluate(
            """(targetId) => {
                var node = window._cy ? window._cy.getElementById(targetId) : null;
                return {
                    exists: !!(node && node.length),
                    classes: node && node.length ? node.classes() : ''
                };
            }""",
            node_id,
        )
        if not live_before.get("exists"):
            browser.close()
            raise AssertionError(f"Seeded draft node was not present on canvas: {live_before}")
        if "container" in _class_tokens(live_before.get("classes")):
            browser.close()
            raise AssertionError(f"Seeded node unexpectedly started as a container: {live_before}")

        page.evaluate(
            """(targetId) => {
                document.dispatchEvent(
                    new CustomEvent('ht:node-convert-container', { detail: { id: targetId } })
                );
            }""",
            node_id,
        )
        page.wait_for_timeout(250)
        live_after = page.evaluate(
            """(targetId) => {
                var node = window._cy ? window._cy.getElementById(targetId) : null;
                return {
                    exists: !!(node && node.length),
                    classes: node && node.length ? node.classes() : ''
                };
            }""",
            node_id,
        )
        if "container" not in _class_tokens(live_after.get("classes")):
            browser.close()
            raise AssertionError(f"Convert event did not update the live canvas node: {live_after}")

        persisted = _poll_editor_state_until_version(token, topology_id, preconvert_version + 1)
        if persisted is None:
            browser.close()
            raise AssertionError(
                "Convert-to-container did not produce a new personal-draft version without a follow-up gesture"
            )

        persisted_node = _find_node_entry(persisted, node_id)
        persisted_classes = _node_classes(persisted_node)
        if "container" not in persisted_classes:
            browser.close()
            raise AssertionError(
                "Convert-to-container was visible in-session but the saved personal-draft payload "
                f"did not persist the container class: live={live_after} persisted_node={persisted_node}"
            )

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        if not _wait_for_canvas(page, timeout_ms=20000):
            browser.close()
            raise AssertionError("Cytoscape did not reinitialize after reload")

        reloaded = page.evaluate(
            """(targetId) => {
                var node = window._cy ? window._cy.getElementById(targetId) : null;
                return {
                    exists: !!(node && node.length),
                    classes: node && node.length ? node.classes() : ''
                };
            }""",
            node_id,
        )
        browser.close()

    if not reloaded.get("exists"):
        raise AssertionError(f"Converted draft node was missing after reload: {reloaded}")
    if "container" not in _class_tokens(reloaded.get("classes")):
        raise AssertionError(
            "Convert-to-container did not survive reload without a follow-up gesture: "
            f"persisted_classes={persisted_classes} reloaded={reloaded}"
        )


def test_ht077_convert_to_container_persists_without_followup_gesture() -> None:
    """Converted draft nodes must persist container state into editor-state and after reload."""
    run_regression()


if __name__ == "__main__":
    try:
        run_regression()
        print("PASS: HT-077 convert-to-container persisted into editor-state and after reload")
        sys.exit(0)
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)