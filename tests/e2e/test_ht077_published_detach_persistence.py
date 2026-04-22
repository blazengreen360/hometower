"""Browser regression for HT-077 published detach draft persistence.

This proof seeds a real published parent-child topology via supported APIs and
save-version. Removing the child from its container must create a personal draft
whose editor-state survives reload; otherwise the topology rehydrates stale
history instead of the detached canvas state.
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
        {"name": f"ht077-detach-ws-{suffix}"},
        token,
    )
    workspace_id = str(workspace.get("id", ""))
    if not workspace_id:
        raise AssertionError(f"Workspace creation failed: {workspace}")

    topology = _api(
        "POST",
        f"/api/workspaces/{workspace_id}/topologies/",
        {"name": f"ht077-detach-topo-{suffix}"},
        token,
    )
    topology_id = str(topology.get("id", ""))
    if not topology_id:
        raise AssertionError(f"Topology creation failed: {topology}")

    return workspace_id, topology_id


def _create_device(token: str, name: str, parent_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"name": name, "type": "Server"}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = _api("POST", "/api/devices/", payload, token)
    if int(response.get("__status", 200)) >= 400:
        raise AssertionError(f"Device creation failed for {name}: {response}")
    return response


def _seed_published_parent_child_fixture(
    token: str,
    topology_id: str,
    suffix: str,
) -> dict[str, object]:
    parent = _create_device(token, f"HT077 Parent {suffix}")
    parent_id = str(parent.get("id", ""))
    child = _create_device(token, f"HT077 Child {suffix}", parent_id=parent_id)
    child_id = str(child.get("id", ""))
    if not parent_id or not child_id:
        raise AssertionError(f"Device fixture creation returned invalid IDs: parent={parent} child={child}")

    cytoscape_json = {
        "elements": {
            "nodes": [
                {
                    "data": {
                        "id": parent_id,
                        "label": f"HT077 Parent {suffix}",
                        "raw_name": f"HT077 Parent {suffix}",
                        "shape": "round-rectangle",
                        "device_type": "Server",
                        "raw_device_type": "Server",
                        "version": int(parent.get("version", 1) or 1),
                        "status": "Active",
                    },
                    "position": {"x": 340, "y": 220},
                    "classes": "container",
                },
                {
                    "data": {
                        "id": child_id,
                        "parent": parent_id,
                        "label": f"HT077 Child {suffix}",
                        "raw_name": f"HT077 Child {suffix}",
                        "shape": "rectangle",
                        "device_type": "Server",
                        "raw_device_type": "Server",
                        "version": int(child.get("version", 1) or 1),
                        "status": "Active",
                    },
                    "position": {"x": 372, "y": 246},
                },
            ],
            "edges": [],
        },
        "zoom": 1,
        "pan": {"x": 0, "y": 0},
        "collapsedNodes": [],
    }
    saved = _api(
        "POST",
        f"/api/topologies/{topology_id}/save-version",
        {"base_diagram_version": None, "cytoscape_json": cytoscape_json},
        token,
    )
    if int(saved.get("__status", 200)) >= 400:
        raise AssertionError(f"Initial save-version failed: {saved}")
    current_diagram_version = saved.get("current_diagram_version")
    if not isinstance(current_diagram_version, int):
        raise AssertionError(f"Save-version did not return a diagram version: {saved}")

    return {
        "parent_id": parent_id,
        "child_id": child_id,
        "child_version": int(child.get("version", 1) or 1),
        "current_diagram_version": current_diagram_version,
    }


def _login_ui(page: Page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.locator('input[type="text"], input[type="email"]').first.fill(ADMIN_EMAIL)
    page.locator('input[type="password"]').first.fill(ADMIN_PASSWORD)
    page.locator('button:has-text("Log in"), button:has-text("Login")').first.click()
    page.wait_for_timeout(1500)
    if "/login" in page.url:
        raise AssertionError("UI login did not complete successfully")


def _wait_for_condition(
    page: Page,
    expression: str,
    arg: object | None = None,
    timeout_ms: int = 15000,
    interval_ms: int = 200,
) -> bool:
    attempts = max(timeout_ms // interval_ms, 1)
    for _ in range(attempts):
        try:
            result = page.evaluate(expression, arg) if arg is not None else page.evaluate(expression)
        except Exception:
            result = False
        if result:
            return True
        page.wait_for_timeout(interval_ms)
    return False


def _wait_for_canvas(page: Page, timeout_ms: int = 15000) -> bool:
    page.evaluate(
        """() => {
            var el = document.getElementById('cy');
            if (el && el.clientHeight === 0) el.style.height = '600px';
        }"""
    )
    return _wait_for_condition(
        page,
        "() => typeof window._cy !== 'undefined' && window._cy !== null && typeof window._cy.nodes === 'function'",
        timeout_ms=timeout_ms,
        interval_ms=300,
    )


def _ensure_edit_mode(page: Page) -> None:
    if _wait_for_condition(page, "() => window.HT_READONLY === false", timeout_ms=3000):
        return
    edit_button = page.locator('button:has-text("Edit")')
    if edit_button.count() == 0:
        raise AssertionError("Edit button was not found on the topology page")
    edit_button.first.click()
    if not _wait_for_condition(page, "() => window.HT_READONLY === false", timeout_ms=9000):
        raise AssertionError("Topology page did not enter edit mode")


def _node_snapshot(page: Page, node_id: str) -> dict[str, object]:
    snapshot = page.evaluate(
        """(targetId) => {
            var node = window._cy ? window._cy.getElementById(String(targetId)) : null;
            if (!node || !node.length) {
                return { exists: false, node_id: String(targetId) };
            }
            var position = node.position ? node.position() : { x: 0, y: 0 };
            var rendered = node.renderedPosition ? node.renderedPosition() : position;
            return {
                exists: true,
                node_id: String(targetId),
                parent_id: String(node.data('parent') || ''),
                version: Number(node.data('version') || 0),
                position: {
                    x: Number(position.x || 0),
                    y: Number(position.y || 0),
                },
                rendered_position: {
                    x: Number(rendered.x || 0),
                    y: Number(rendered.y || 0),
                },
            };
        }""",
        node_id,
    )
    return snapshot if isinstance(snapshot, dict) else {"exists": False, "node_id": node_id}


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


def _node_entry_parent_id(node_entry: dict[str, object] | None) -> str | None:
    if not isinstance(node_entry, dict):
        return None
    data = node_entry.get("data")
    if not isinstance(data, dict):
        return None
    raw_parent = data.get("parent")
    if raw_parent in (None, ""):
        return None
    return str(raw_parent)


def _node_entry_position(node_entry: dict[str, object] | None) -> dict[str, float] | None:
    if not isinstance(node_entry, dict):
        return None
    position = node_entry.get("position")
    if not isinstance(position, dict):
        return None
    return {
        "x": float(position.get("x", 0) or 0),
        "y": float(position.get("y", 0) or 0),
    }


def _close_enough(a: dict[str, float], b: dict[str, float], tolerance: float = 1.0) -> bool:
    return abs(a["x"] - b["x"]) <= tolerance and abs(a["y"] - b["y"]) <= tolerance


def _poll_device_until_detached(
    token: str,
    child_id: str,
    expected_version: int,
    timeout_s: float = 12.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_s
    last: dict[str, object] = {}
    while time.time() < deadline:
        last = _api("GET", f"/api/devices/{child_id}", token=token)
        if (
            int(last.get("__status", 200)) < 400
            and last.get("parent_id") is None
            and int(last.get("version", 0) or 0) == expected_version
        ):
            return last
        time.sleep(0.25)
    return last


def _poll_device_until_parented(
    token: str,
    child_id: str,
    expected_parent_id: str,
    expected_version: int,
    timeout_s: float = 12.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_s
    last: dict[str, object] = {}
    while time.time() < deadline:
        last = _api("GET", f"/api/devices/{child_id}", token=token)
        if (
            int(last.get("__status", 200)) < 400
            and str(last.get("parent_id") or "") == expected_parent_id
            and int(last.get("version", 0) or 0) == expected_version
        ):
            return last
        time.sleep(0.25)
    return last


def _poll_editor_state_until_detached(
    token: str,
    topology_id: str,
    child_id: str,
    current_diagram_version: int,
    expected_position: dict[str, float],
    timeout_s: float = 12.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_s
    last: dict[str, object] = {}
    while time.time() < deadline:
        last = _api("GET", f"/api/topologies/{topology_id}/editor-state", token=token)
        node_entry = _find_node_entry(last, child_id)
        draft_version = last.get("draft_version")
        persisted_position = _node_entry_position(node_entry)
        if (
            int(last.get("__status", 200)) < 400
            and str(last.get("source", "")) == "draft"
            and isinstance(draft_version, int)
            and draft_version >= 1
            and int(last.get("current_diagram_version", 0) or 0) == current_diagram_version
            and bool(last.get("has_unsaved_changes", False))
            and _node_entry_parent_id(node_entry) is None
            and persisted_position is not None
            and _close_enough(persisted_position, expected_position)
        ):
            return last
        time.sleep(0.25)
    return last


def _poll_editor_state_until_parented(
    token: str,
    topology_id: str,
    child_id: str,
    current_diagram_version: int,
    expected_parent_id: str,
    timeout_s: float = 12.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_s
    last: dict[str, object] = {}
    while time.time() < deadline:
        last = _api("GET", f"/api/topologies/{topology_id}/editor-state", token=token)
        node_entry = _find_node_entry(last, child_id)
        draft_version = last.get("draft_version")
        if (
            int(last.get("__status", 200)) < 400
            and str(last.get("source", "")) == "draft"
            and isinstance(draft_version, int)
            and draft_version >= 1
            and int(last.get("current_diagram_version", 0) or 0) == current_diagram_version
            and bool(last.get("has_unsaved_changes", False))
            and _node_entry_parent_id(node_entry) == expected_parent_id
        ):
            return last
        time.sleep(0.25)
    return last


def _best_effort_delete_workspace(token: str, workspace_id: str) -> None:
    if not workspace_id:
        return
    _api("DELETE", f"/api/workspaces/{workspace_id}", token=token)


def run_regression(*, replay_undo: bool = False) -> None:
    token = _login_api()
    suffix = uuid.uuid4().hex[:8]
    workspace_id = ""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            workspace_id, topology_id = _create_workspace_topology(token, suffix)
            fixture = _seed_published_parent_child_fixture(token, topology_id, suffix)
            parent_id = str(fixture["parent_id"])
            child_id = str(fixture["child_id"])
            child_next_version = int(fixture["child_version"]) + 1
            child_replay_version = child_next_version + 1
            current_diagram_version = int(fixture["current_diagram_version"])

            before_editor_state = _api("GET", f"/api/topologies/{topology_id}/editor-state", token=token)
            before_node = _find_node_entry(before_editor_state, child_id)
            if str(before_editor_state.get("source", "")) != "history":
                raise AssertionError(f"Expected published fixture to start from history source: {before_editor_state}")
            if before_editor_state.get("draft_version") is not None:
                raise AssertionError(f"Published fixture unexpectedly started with a personal draft: {before_editor_state}")
            if _node_entry_parent_id(before_node) != parent_id:
                raise AssertionError(
                    "Published fixture did not persist the seeded parent relationship into editor-state: "
                    f"node={before_node} payload={before_editor_state}"
                )

            _login_ui(page)
            page.goto(
                f"{BASE}/topology?workspace_id={workspace_id}&topology_id={topology_id}",
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(1200)
            if not _wait_for_canvas(page, timeout_ms=20000):
                raise AssertionError("Cytoscape did not initialize for the published parent-child topology")

            _ensure_edit_mode(page)

            before_live = _node_snapshot(page, child_id)
            if not before_live.get("exists"):
                raise AssertionError(f"Published child node was missing before detach: {before_live}")
            if str(before_live.get("parent_id", "")) != parent_id:
                raise AssertionError(f"Published child did not start parented on canvas: {before_live}")

            page.evaluate(
                """(targetId) => {
                    document.dispatchEvent(
                        new CustomEvent('ht:node-remove-from-container', {
                            detail: { id: String(targetId) },
                        })
                    );
                }""",
                child_id,
            )

            if not _wait_for_condition(
                page,
                """(args) => {
                    if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
                    var node = window._cy.getElementById(String(args.child_id));
                    if (!node || !node.length) return false;
                    var rendered = node.renderedPosition ? node.renderedPosition() : node.position();
                    return String(node.data('parent') || '') === ''
                        && Math.abs(Number(rendered.x || 0) - Number(args.rendered.x)) < 1
                        && Math.abs(Number(rendered.y || 0) - Number(args.rendered.y)) < 1;
                }""",
                {"child_id": child_id, "rendered": before_live["rendered_position"]},
                timeout_ms=15000,
            ):
                raise AssertionError(
                    "Remove from container did not detach the live node while preserving rendered position: "
                    f"before={before_live} after={_node_snapshot(page, child_id)}"
                )

            after_live = _node_snapshot(page, child_id)
            if str(after_live.get("parent_id", "")) != "":
                raise AssertionError(f"Live detach left the child parented on canvas: {after_live}")

            detached_device = _poll_device_until_detached(token, child_id, child_next_version)
            if detached_device.get("parent_id") is not None or int(detached_device.get("version", 0) or 0) != child_next_version:
                raise AssertionError(
                    "Published detach did not persist the device row change as expected: "
                    f"device={detached_device} expected_version={child_next_version}"
                )

            persisted_editor_state = _poll_editor_state_until_detached(
                token,
                topology_id,
                child_id,
                current_diagram_version,
                {
                    "x": float(after_live["position"]["x"]),
                    "y": float(after_live["position"]["y"]),
                },
            )
            persisted_node = _find_node_entry(persisted_editor_state, child_id)
            persisted_position = _node_entry_position(persisted_node)
            if (
                str(persisted_editor_state.get("source", "")) != "draft"
                or not isinstance(persisted_editor_state.get("draft_version"), int)
                or _node_entry_parent_id(persisted_node) is not None
                or persisted_position is None
                or not _close_enough(
                    persisted_position,
                    {
                        "x": float(after_live["position"]["x"]),
                        "y": float(after_live["position"]["y"]),
                    },
                )
            ):
                raise AssertionError(
                    "Published detach updated the device row but did not persist detached editor-state before reload: "
                    f"live_after={after_live} editor_state={persisted_editor_state} node={persisted_node}"
                )

            if replay_undo:
                page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")

                if not _wait_for_condition(
                    page,
                    """(args) => {
                        if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
                        var node = window._cy.getElementById(String(args.child_id));
                        if (!node || !node.length) return false;
                        var rendered = node.renderedPosition ? node.renderedPosition() : node.position();
                        return String(node.data('parent') || '') === String(args.parent_id)
                            && Math.abs(Number(rendered.x || 0) - Number(args.rendered.x)) < 1
                            && Math.abs(Number(rendered.y || 0) - Number(args.rendered.y)) < 1;
                    }""",
                    {
                        "child_id": child_id,
                        "parent_id": parent_id,
                        "rendered": before_live["rendered_position"],
                    },
                    timeout_ms=15000,
                ):
                    raise AssertionError(
                        "Published detach undo updated the device row but did not restore the live reparented state: "
                        f"before={before_live} after={_node_snapshot(page, child_id)}"
                    )

                reparented_device = _poll_device_until_parented(
                    token,
                    child_id,
                    parent_id,
                    child_replay_version,
                )
                if (
                    str(reparented_device.get("parent_id") or "") != parent_id
                    or int(reparented_device.get("version", 0) or 0) != child_replay_version
                ):
                    raise AssertionError(
                        "Published detach undo did not persist the restored device row change as expected: "
                        f"device={reparented_device} expected_parent={parent_id} expected_version={child_replay_version}"
                    )

                replay_editor_state = _poll_editor_state_until_parented(
                    token,
                    topology_id,
                    child_id,
                    current_diagram_version,
                    parent_id,
                )
                replay_node = _find_node_entry(replay_editor_state, child_id)
                if (
                    str(replay_editor_state.get("source", "")) != "draft"
                    or not isinstance(replay_editor_state.get("draft_version"), int)
                    or _node_entry_parent_id(replay_node) != parent_id
                ):
                    raise AssertionError(
                        "Published detach undo updated the device row but did not persist restored editor-state before reload: "
                        f"editor_state={replay_editor_state} node={replay_node} expected_parent={parent_id}"
                    )

                page.reload(wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                if not _wait_for_canvas(page, timeout_ms=20000):
                    raise AssertionError("Cytoscape did not reinitialize after reload")

                if not _wait_for_condition(
                    page,
                    """(args) => {
                        if (!window._cy) return false;
                        var node = window._cy.getElementById(String(args.child_id));
                        if (!node || !node.length) return false;
                        return String(node.data('parent') || '') === String(args.parent_id);
                    }""",
                    {"child_id": child_id, "parent_id": parent_id},
                    timeout_ms=15000,
                ):
                    raise AssertionError(
                        "Published detach undo did not survive reload; the topology rehydrated stale detached draft state: "
                        f"reloaded={_node_snapshot(page, child_id)} expected_parent={parent_id}"
                    )
                return

            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            if not _wait_for_canvas(page, timeout_ms=20000):
                raise AssertionError("Cytoscape did not reinitialize after reload")

            if not _wait_for_condition(
                page,
                """(args) => {
                    if (!window._cy) return false;
                    var node = window._cy.getElementById(String(args.child_id));
                    if (!node || !node.length) return false;
                    var position = node.position ? node.position() : { x: 0, y: 0 };
                    return String(node.data('parent') || '') === ''
                        && Math.abs(Number(position.x || 0) - Number(args.position.x)) < 1
                        && Math.abs(Number(position.y || 0) - Number(args.position.y)) < 1;
                }""",
                {
                    "child_id": child_id,
                    "position": {
                        "x": float(after_live["position"]["x"]),
                        "y": float(after_live["position"]["y"]),
                    },
                },
                timeout_ms=15000,
            ):
                raise AssertionError(
                    "Published detach did not survive reload; the topology rehydrated stale parented state: "
                    f"reloaded={_node_snapshot(page, child_id)} expected_parent='' expected_position={after_live['position']}"
                )
        finally:
            browser.close()
            _best_effort_delete_workspace(token, workspace_id)


def test_ht077_published_remove_from_container_persists_into_editor_state_and_reload() -> None:
    """Published detach must persist into personal draft editor-state and survive reload."""
    run_regression()


def test_ht077_published_remove_from_container_undo_persists_into_editor_state_and_reload() -> None:
    """Published detach undo must persist replayed editor-state and survive reload."""
    run_regression(replay_undo=True)


if __name__ == "__main__":
    try:
        run_regression()
        print("PASS: HT-077 published remove-from-container persisted into editor-state and after reload")
        sys.exit(0)
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)