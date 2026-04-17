"""Browser proof for HT-032 canvas undo/redo high-risk scenarios.

Run directly (requires app on http://localhost:8080):
    python tests/e2e/test_topology_canvas_undo_redo.py
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
    body = _api(
        "POST",
        "/api/auth/login",
        {"email": ADMIN_EMAIL, "password": ADMIN_PASS},
    )
    token = str(body.get("access_token", ""))
    if not token:
        raise RuntimeError(f"API login failed: {body}")
    return token


def _first_workspace_topology(token: str) -> tuple[str, str]:
    workspaces = _api("GET", "/api/workspaces/", token=token).get("items", [])
    if not isinstance(workspaces, list) or not workspaces:
        raise RuntimeError("No workspaces available for browser proof")

    workspace_id = str(workspaces[0].get("id", ""))
    topologies = _api("GET", f"/api/workspaces/{workspace_id}/topologies/", token=token).get(
        "items", []
    )
    if not isinstance(topologies, list) or not topologies:
        raise RuntimeError(f"No topologies available for workspace {workspace_id}")

    topology_id = str(topologies[0].get("id", ""))
    if not workspace_id or not topology_id:
        raise RuntimeError("Unable to resolve workspace/topology IDs")
    return workspace_id, topology_id


def _login_ui(page: Page) -> bool:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.locator('input[type="text"], input[type="email"]').first.fill(ADMIN_EMAIL)
    page.locator('input[type="password"]').first.fill(ADMIN_PASS)
    page.locator('button:has-text("Log in")').first.click()
    page.wait_for_timeout(1200)
    return "/login" not in page.url


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
    return _wait_for_condition(
        page,
        "() => typeof window._cy !== 'undefined' && window._cy !== null && typeof window._cy.nodes === 'function'",
        timeout_ms=timeout_ms,
        interval_ms=300,
    )


def _wait_for_undo_idle(page: Page, timeout_ms: int = 12000) -> bool:
    return _wait_for_condition(
        page,
        "() => !!window._htUndoState && !window._htUndoState.busy",
        timeout_ms=timeout_ms,
    )


def _ensure_edit_mode(page: Page) -> bool:
    if _wait_for_condition(
        page,
        "() => window.HT_READONLY === false && !!window._htUndoState && !window._htUndoState.busy",
        timeout_ms=3000,
        interval_ms=200,
    ):
        return True

    edit_button = page.locator('button:has-text("Edit")')
    if edit_button.count() == 0:
        return _wait_for_condition(
            page,
            "() => window.HT_READONLY === false && !!window._htUndoState && !window._htUndoState.busy",
            timeout_ms=6000,
            interval_ms=200,
        )

    edit_button.first.click()
    return _wait_for_condition(
        page,
        "() => window.HT_READONLY === false && !!window._htUndoState && !window._htUndoState.busy",
        timeout_ms=9000,
        interval_ms=200,
    )


def _published_node_ids(page: Page) -> list[str]:
    node_ids = page.evaluate(
        """() => {
            if (!window._cy) return [];
            var ids = [];
            window._cy.nodes().forEach(function(node) {
                var id = String(node.id());
                var isDraft = Boolean(
                    (window._htIsDraft && window._htIsDraft(id))
                    || id.indexOf('draft-') === 0
                    || node.data('draft')
                );
                if (!isDraft) ids.push(id);
            });
            return ids;
        }"""
    )
    return node_ids if isinstance(node_ids, list) else []


def _wait_for_node_position(page: Page, node_id: str, expected: dict[str, object]) -> bool:
    return _wait_for_condition(
        page,
        """(args) => {
            if (!window._cy) return false;
            var node = window._cy.getElementById(args.node_id);
            if (!node || !node.length) return false;
            var x = Number(node.position('x'));
            var y = Number(node.position('y'));
            return Math.abs(x - Number(args.expected.x)) < 1
                && Math.abs(y - Number(args.expected.y)) < 1;
        }""",
        {"node_id": node_id, "expected": expected},
        timeout_ms=12000,
    )


def _wait_for_node_name(page: Page, node_id: str, expected_name: str) -> bool:
    return _wait_for_condition(
        page,
        """(args) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            var node = window._cy.getElementById(args.node_id);
            if (!node || !node.length) return false;
            var raw = String(node.data('raw_name') || node.data('label') || '');
            return raw === args.expected_name;
        }""",
        {"node_id": node_id, "expected_name": expected_name},
        timeout_ms=15000,
    )


def _scenario_move_and_remove(page: Page) -> tuple[bool, str]:
    move_result = page.evaluate(
        """() => {
            if (!window._cy) return { ok: false, reason: 'canvas_missing' };
            var probeId = 'draft-undo-probe-' + String(Date.now());
            window._cy.add({
                group: 'nodes',
                classes: 'draft',
                data: {
                    id: probeId,
                    label: 'Undo Probe',
                    raw_name: 'Undo Probe',
                    draft: true,
                },
                position: { x: 160, y: 120 },
            });

            var probe = window._cy.getElementById(probeId);
            var node = probe && probe.length ? probe[0] : null;
            if (!node) return { ok: false, reason: 'probe_missing' };
            var before = { x: node.position('x'), y: node.position('y') };
            if (!window._htBeginMoveGesture || !window._htCommitMoveGesture) {
                return { ok: false, reason: 'move_helpers_missing' };
            }
            window._htBeginMoveGesture(node);
            node.position({ x: before.x + 75, y: before.y + 25 });
            window._htCommitMoveGesture(node);
            return {
                ok: true,
                node_id: String(node.id()),
                before: before,
                after: { x: node.position('x'), y: node.position('y') },
            };
        }"""
    )
    if not isinstance(move_result, dict) or not move_result.get("ok"):
        reason = "unknown"
        if isinstance(move_result, dict):
            reason = str(move_result.get("reason", "unknown"))
        return False, f"unable to create local move action ({reason})"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_node_position(page, str(move_result["node_id"]), dict(move_result["before"])):
        return False, "move undo did not restore node coordinates"

    page.evaluate("() => window._htRequestRedo && window._htRequestRedo()")
    if not _wait_for_node_position(page, str(move_result["node_id"]), dict(move_result["after"])):
        return False, "move redo did not reapply node coordinates"

    remove_result = page.evaluate(
        """(nodeId) => {
            if (!window._cy) {
                return { ok: false, reason: 'no_nodes' };
            }
            var node = window._cy.getElementById(String(nodeId));
            if (!node || !node.length) return { ok: false, reason: 'node_missing' };
            var removeFn = window._htCommitLocalRemoveFromView || window._htCommitLocalDraftDelete;
            if (!removeFn) return { ok: false, reason: 'remove_helper_missing' };
            var beforeCount = window._cy.nodes().length;
            removeFn(node);
            return {
                ok: true,
                before_count: beforeCount,
            };
        }""",
        str(move_result["node_id"]),
    )
    if not isinstance(remove_result, dict) or not remove_result.get("ok"):
        reason = "unknown"
        if isinstance(remove_result, dict):
            reason = str(remove_result.get("reason", "unknown"))
        return False, f"unable to create remove-from-view action ({reason})"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    restored = page.evaluate("() => window._cy ? window._cy.nodes().length : -1")
    if not isinstance(restored, int) or restored < int(remove_result["before_count"]):
        return False, "remove-from-view undo did not restore nodes"

    return True, "move/remove local undo checks passed"


def _scenario_published_edge_cycle(page: Page, token: str) -> tuple[bool, str]:
    pair = page.evaluate(
        """() => {
            if (!window._cy) return null;
            var ids = [];
            window._cy.nodes().forEach(function(node) {
                var id = String(node.id());
                var isDraft = Boolean(
                    (window._htIsDraft && window._htIsDraft(id))
                    || id.indexOf('draft-') === 0
                    || node.data('draft')
                );
                if (!isDraft) ids.push(id);
            });
            function hasEdge(a, b) {
                var linked = false;
                window._cy.edges().forEach(function(edge) {
                    var source = String(edge.data('source') || '');
                    var target = String(edge.data('target') || '');
                    if ((source === a && target === b) || (source === b && target === a)) {
                        linked = true;
                    }
                });
                return linked;
            }
            for (var i = 0; i < ids.length; i += 1) {
                for (var j = i + 1; j < ids.length; j += 1) {
                    if (!hasEdge(ids[i], ids[j])) {
                        return { source_id: ids[i], target_id: ids[j] };
                    }
                }
            }
            return null;
        }"""
    )
    if not isinstance(pair, dict):
        suffix = int(time.time() * 1000)
        source_name = f"HT032-Undo-Edge-Source-{suffix}"
        target_name = f"HT032-Undo-Edge-Target-{suffix}"

        source = _api(
            "POST",
            "/api/devices/",
            {"name": source_name, "type": "Switch"},
            token=token,
        )
        target = _api(
            "POST",
            "/api/devices/",
            {"name": target_name, "type": "Server"},
            token=token,
        )

        source_id = str(source.get("id", ""))
        target_id = str(target.get("id", ""))
        if not source_id or not target_id:
            return False, "no published node pair available and device bootstrap failed"

        added = page.evaluate(
            """(args) => {
                if (!window._cy) return false;

                function ensureNode(id, label, x, y) {
                    if (window._cy.getElementById(String(id)).length) return;
                    window._cy.add({
                        group: 'nodes',
                        data: {
                            id: String(id),
                            label: String(label),
                            raw_name: String(label),
                        },
                        position: { x: Number(x), y: Number(y) },
                    });
                }

                ensureNode(args.source_id, args.source_name, 220, 220);
                ensureNode(args.target_id, args.target_name, 420, 220);
                return true;
            }""",
            {
                "source_id": source_id,
                "target_id": target_id,
                "source_name": source_name,
                "target_name": target_name,
            },
        )
        if not added:
            return False, "no published node pair available and canvas bootstrap failed"

        pair = {"source_id": source_id, "target_id": target_id}

    before_edges = page.evaluate(
        """() => {
            if (!window._cy) return [];
            var ids = [];
            window._cy.edges().forEach(function(edge) { ids.push(String(edge.id())); });
            return ids;
        }"""
    )
    if not isinstance(before_edges, list):
        return False, "unable to inspect initial edge IDs"

    before_undo_len = page.evaluate(
        "() => window._htUndoState ? window._htUndoState.undoStack.length : 0"
    )
    label = f"ht-e2e-edge-{int(time.time())}"

    created = page.evaluate(
        """(args) => {
            if (!window._htRequestCanvasAction) return false;
            window._htRequestCanvasAction({
                type: 'create_edge',
                payload: {
                    scope: 'published',
                    source_id: args.source_id,
                    target_id: args.target_id,
                    connection_type: 'Ethernet',
                    label: args.label,
                },
            });
            return true;
        }""",
        {
            "source_id": str(pair.get("source_id", "")),
            "target_id": str(pair.get("target_id", "")),
            "label": label,
        },
    )
    if not created:
        return False, "failed to dispatch create_edge action"

    created_ok = _wait_for_condition(
        page,
        """(args) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            if (window._htUndoState.undoStack.length <= Number(args.before_undo_len)) return false;
            var extra = 0;
            window._cy.edges().forEach(function(edge) {
                var id = String(edge.id());
                if (args.before_edges.indexOf(id) === -1) extra += 1;
            });
            return extra > 0;
        }""",
        {"before_edges": before_edges, "before_undo_len": int(before_undo_len)},
        timeout_ms=15000,
    )
    if not created_ok:
        return False, "published edge did not appear after create action"

    first_created_id = page.evaluate(
        """(beforeEdges) => {
            if (!window._cy) return '';
            var found = '';
            window._cy.edges().forEach(function(edge) {
                var id = String(edge.id());
                if (!found && beforeEdges.indexOf(id) === -1) found = id;
            });
            return found;
        }""",
        before_edges,
    )
    if not isinstance(first_created_id, str) or not first_created_id:
        return False, "unable to identify created edge ID"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_condition(
        page,
        """(edgeId) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            return window._cy.getElementById(edgeId).length === 0;
        }""",
        first_created_id,
        timeout_ms=15000,
    ):
        return False, "first undo did not remove created edge"

    page.evaluate("() => window._htRequestRedo && window._htRequestRedo()")
    if not _wait_for_condition(
        page,
        """(beforeEdges) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            var extra = 0;
            window._cy.edges().forEach(function(edge) {
                if (beforeEdges.indexOf(String(edge.id())) === -1) extra += 1;
            });
            return extra > 0;
        }""",
        before_edges,
        timeout_ms=15000,
    ):
        return False, "redo did not recreate published edge"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    removed_again = _wait_for_condition(
        page,
        """(beforeEdges) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            var extra = 0;
            window._cy.edges().forEach(function(edge) {
                if (beforeEdges.indexOf(String(edge.id())) === -1) extra += 1;
            });
            return extra === 0;
        }""",
        before_edges,
        timeout_ms=15000,
    )
    if not removed_again:
        return False, "second undo did not remove recreated edge"

    return True, "published edge create->undo->redo->undo cycle passed"


def _scenario_multi_layout_delete_cycle(page: Page, topology_id: str) -> tuple[bool, str]:
    setup = page.evaluate(
        """async (args) => {
            if (!window._cy || !window._htRequestCanvasAction) {
                return { ok: false, error: 'canvas_or_undo_missing' };
            }

            function publishedNodes() {
                var ids = [];
                window._cy.nodes().forEach(function(node) {
                    var id = String(node.id());
                    var isDraft = Boolean(
                        (window._htIsDraft && window._htIsDraft(id))
                        || id.indexOf('draft-') === 0
                        || node.data('draft')
                    );
                    if (!isDraft) ids.push(id);
                });
                return ids;
            }

            var nodes = publishedNodes();
            if (!nodes.length) {
                return { ok: false, error: 'no_published_nodes' };
            }
            var nodeId = String(nodes[0]);
            var node = window._cy.getElementById(nodeId);
            if (!node || !node.length) {
                return { ok: false, error: 'node_missing' };
            }
            var basePos = { x: Number(node.position('x')), y: Number(node.position('y')) };

            if (!window._htDiagramId) {
                if (!window.getCanvasJson) {
                    return { ok: false, error: 'no_active_layout_and_no_canvas_json' };
                }
                var createBase = await fetch('/api/diagrams/', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: 'HT032-Undo-Base-' + Date.now(),
                        topology_id: args.topology_id,
                        cytoscape_json: window.getCanvasJson(),
                    }),
                });
                if (!createBase.ok) {
                    return { ok: false, error: 'create_base_layout_failed:' + createBase.status };
                }
                var createdBase = await createBase.json();
                window._htDiagramId = createdBase.id;
                window._htDiagramVersion = createdBase.version;
            }

            var baseResp = await fetch('/api/diagrams/' + window._htDiagramId, {
                credentials: 'include',
            });
            if (!baseResp.ok) {
                return { ok: false, error: 'load_base_layout_failed:' + baseResp.status };
            }
            var baseLayout = await baseResp.json();
            var clone = JSON.parse(JSON.stringify(baseLayout.cytoscape_json || {}));

            function moveNode(layout, targetId, dx, dy) {
                function patchNode(nodeEntry) {
                    if (!nodeEntry || !nodeEntry.data || String(nodeEntry.data.id || '') !== targetId) {
                        return null;
                    }
                    var original = nodeEntry.position || { x: basePos.x, y: basePos.y };
                    nodeEntry.position = {
                        x: Number(original.x || 0) + dx,
                        y: Number(original.y || 0) + dy,
                    };
                    return { x: Number(nodeEntry.position.x), y: Number(nodeEntry.position.y) };
                }

                if (layout && Array.isArray(layout.elements)) {
                    for (var i = 0; i < layout.elements.length; i += 1) {
                        var entry = layout.elements[i];
                        if (entry && entry.group === 'nodes') {
                            var movedFlat = patchNode(entry);
                            if (movedFlat) return movedFlat;
                        }
                    }
                }

                if (layout && layout.elements && Array.isArray(layout.elements.nodes)) {
                    for (var j = 0; j < layout.elements.nodes.length; j += 1) {
                        var movedNested = patchNode(layout.elements.nodes[j]);
                        if (movedNested) return movedNested;
                    }
                }

                if (layout && Array.isArray(layout.nodes)) {
                    for (var k = 0; k < layout.nodes.length; k += 1) {
                        var movedTop = patchNode(layout.nodes[k]);
                        if (movedTop) return movedTop;
                    }
                }
                return null;
            }

            var altPos = moveNode(clone, nodeId, 240, 120);
            if (!altPos) {
                return { ok: false, error: 'unable_to_move_node_in_layout_snapshot' };
            }

            var createAlt = await fetch('/api/diagrams/', {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: 'HT032-Undo-Multi-' + Date.now(),
                    topology_id: baseLayout.topology_id || args.topology_id,
                    cytoscape_json: clone,
                }),
            });
            if (!createAlt.ok) {
                return { ok: false, error: 'create_alt_layout_failed:' + createAlt.status };
            }
            var altLayout = await createAlt.json();

            window._htDiagramId = altLayout.id;
            window._htDiagramVersion = altLayout.version;
            if (window.applyLayoutPositions) {
                window.applyLayoutPositions(clone);
            }

            return {
                ok: true,
                node_id: nodeId,
                base_pos: basePos,
                alt_pos: altPos,
                alt_diagram_id: String(altLayout.id),
            };
        }""",
        {"topology_id": topology_id},
    )
    if not isinstance(setup, dict) or not setup.get("ok"):
        reason = str(setup.get("error", "unknown")) if isinstance(setup, dict) else "setup_failed"
        return False, f"multi-layout setup failed ({reason})"

    node_id = str(setup["node_id"])
    alt_pos = dict(setup["alt_pos"])
    base_pos = dict(setup["base_pos"])

    if not _wait_for_node_position(page, node_id, alt_pos):
        return False, "failed to activate alternate diagram coordinates before delete"

    delete_sent = page.evaluate(
        """(args) => {
            if (!window._cy || !window._htRequestCanvasAction) return false;
            var node = window._cy.getElementById(args.node_id);
            if (!node || !node.length) return false;
            var snapshot = window._htSnapshotNodeSet ? window._htSnapshotNodeSet(node) : null;
            window._htRequestCanvasAction({
                type: 'delete_published_node',
                payload: {
                    device_id: args.node_id,
                    active_diagram_id: args.active_diagram_id,
                    active_node: snapshot,
                },
            });
            return true;
        }""",
        {
            "node_id": node_id,
            "active_diagram_id": str(setup["alt_diagram_id"]),
        },
    )
    if not delete_sent:
        return False, "failed to dispatch delete_published_node"

    if not _wait_for_condition(
        page,
        """(nodeId) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            return window._cy.getElementById(nodeId).length === 0;
        }""",
        node_id,
    ):
        return False, "published node delete did not remove node"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_condition(
        page,
        """(nodeId) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            return window._cy.getElementById(nodeId).length > 0;
        }""",
        node_id,
    ):
        return False, "undo after delete did not restore node"

    restored = page.evaluate(
        """(nodeId) => {
            if (!window._cy) return null;
            var node = window._cy.getElementById(nodeId);
            if (!node || !node.length) return null;
            return { x: Number(node.position('x')), y: Number(node.position('y')) };
        }""",
        node_id,
    )
    if not isinstance(restored, dict):
        return False, "restored node position unavailable"

    x_delta = abs(float(restored["x"]) - float(alt_pos["x"]))
    y_delta = abs(float(restored["y"]) - float(alt_pos["y"]))
    if x_delta > 1 or y_delta > 1:
        return False, "undo restored node using wrong layout snapshot (active diagram not honored)"

    base_x_delta = abs(float(restored["x"]) - float(base_pos["x"]))
    base_y_delta = abs(float(restored["y"]) - float(base_pos["y"]))
    if base_x_delta < 1 and base_y_delta < 1:
        return False, "restored node snapped to base layout instead of active layout"

    page.evaluate("() => window._htRequestRedo && window._htRequestRedo()")
    if not _wait_for_condition(
        page,
        """(nodeId) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            return window._cy.getElementById(nodeId).length === 0;
        }""",
        node_id,
    ):
        return False, "redo after multi-layout undo did not re-delete node"

    # Cleanup: restore deleted device so the environment is not left modified.
    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_condition(
        page,
        """(nodeId) => {
            if (!window._cy || !window._htUndoState || window._htUndoState.busy) return false;
            return window._cy.getElementById(nodeId).length > 0;
        }""",
        node_id,
    ):
        return False, "cleanup undo after multi-layout cycle failed"

    return True, "multi-layout published delete->undo->redo cycle passed"


def _trimmed_name(base: str, suffix: str) -> str:
    max_prefix = 240 - len(suffix)
    safe_prefix = base[: max(max_prefix, 1)]
    return f"{safe_prefix}{suffix}"


def _commit_detail_panel_style_name_patch(
    page: Page,
    node_id: str,
    after_name: str,
) -> dict[str, object]:
    result = page.evaluate(
        """async (args) => {
            if (!window._cy) return { ok: false, error: 'canvas_missing' };
            var node = window._cy.getElementById(args.node_id);
            if (!node || !node.length) return { ok: false, error: 'node_missing' };

            var beforeName = String(node.data('raw_name') || node.data('label') || '');
            var versionRaw = Number(node.data('version') || 1);
            var response = await fetch('/api/devices/' + args.node_id, {
                method: 'PATCH',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: args.after_name, version: versionRaw }),
            });
            if (!response.ok) {
                return { ok: false, error: 'patch_failed:' + response.status };
            }

            var body = await response.json();
            var nextVersion = Number(body.version || versionRaw);
            var nodePatch = { name: args.after_name, version: nextVersion };

            if (window._htApplyUndoNodePatch) {
                window._htApplyUndoNodePatch(args.node_id, nodePatch);
            }
            if (window._htPushCommittedUndoEntry) {
                window._htPushCommittedUndoEntry({
                    entry_id: crypto.randomUUID(),
                    type: 'update_device_field',
                    label: 'Update Name',
                    execution: 'api',
                    forward: {
                        op: 'update_device_field',
                        payload: {
                            device_id: String(args.node_id),
                            field: 'name',
                            before: beforeName,
                            after: args.after_name,
                            version_cursor: nextVersion,
                            version_strategy: 'current_device',
                            node_patch: nodePatch,
                        },
                    },
                    reverse: {
                        op: 'update_device_field',
                        payload: {
                            device_id: String(args.node_id),
                            field: 'name',
                            before: beforeName,
                            after: args.after_name,
                            version_cursor: nextVersion,
                            version_strategy: 'current_device',
                            node_patch: nodePatch,
                        },
                    },
                });
            }

            return {
                ok: true,
                before_name: beforeName,
                after_name: args.after_name,
                next_version: nextVersion,
            };
        }""",
        {"node_id": node_id, "after_name": after_name},
    )
    return result if isinstance(result, dict) else {"ok": False, "error": "invalid_patch_result"}


def _scenario_patch_backed_field_cycle(page: Page) -> tuple[bool, str]:
    published = _published_node_ids(page)
    if not published:
        return False, "no published nodes available for PATCH-backed detail scenario"

    node_id = published[0]
    original_name_raw = page.evaluate(
        """(nodeId) => {
            if (!window._cy) return '';
            var node = window._cy.getElementById(nodeId);
            if (!node || !node.length) return '';
            return String(node.data('raw_name') || node.data('label') || '');
        }""",
        node_id,
    )
    if not isinstance(original_name_raw, str):
        return False, "failed to read original node name"

    name_one = _trimmed_name(original_name_raw or "Device", " [Undo-A]")
    name_two = _trimmed_name(original_name_raw or "Device", " [Undo-B]")

    first_patch = _commit_detail_panel_style_name_patch(page, node_id, name_one)
    if not first_patch.get("ok"):
        return False, f"first PATCH-backed update failed ({first_patch.get('error', 'unknown')})"
    if not _wait_for_node_name(page, node_id, name_one):
        return False, "first PATCH-backed update was not reflected on node"

    second_patch = _commit_detail_panel_style_name_patch(page, node_id, name_two)
    if not second_patch.get("ok"):
        return False, f"second PATCH-backed update failed ({second_patch.get('error', 'unknown')})"
    if not _wait_for_node_name(page, node_id, name_two):
        return False, "second PATCH-backed update was not reflected on node"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_node_name(page, node_id, name_one):
        return False, "first undo after stacked PATCH updates did not land on intermediate value"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_node_name(page, node_id, original_name_raw):
        return False, "second undo after stacked PATCH updates did not restore original value"

    page.evaluate("() => window._htRequestRedo && window._htRequestRedo()")
    if not _wait_for_node_name(page, node_id, name_one):
        return False, "first redo after stacked PATCH updates did not restore intermediate value"

    page.evaluate("() => window._htRequestRedo && window._htRequestRedo()")
    if not _wait_for_node_name(page, node_id, name_two):
        return False, "second redo after stacked PATCH updates did not restore latest value"

    # Cleanup: return the node to original name.
    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_node_name(page, node_id, name_one):
        return False, "cleanup undo (latest -> intermediate) failed"

    page.evaluate("() => window._htRequestUndo && window._htRequestUndo()")
    if not _wait_for_node_name(page, node_id, original_name_raw):
        return False, "cleanup undo (intermediate -> original) failed"

    return True, "PATCH-backed detail-panel-style stacked undo/redo cycle passed"


def _run() -> int:
    token = _login_api()
    workspace_id, topology_id = _first_workspace_topology(token)
    url = f"{BASE}/topology?workspace_id={workspace_id}&topology_id={topology_id}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        if not _login_ui(page):
            print("FAIL: login failed")
            browser.close()
            return 1

        page.goto(url, wait_until="networkidle")
        if not _wait_for_canvas(page):
            print("FAIL: canvas not ready")
            browser.close()
            return 1

        if not _ensure_edit_mode(page):
            print("FAIL: unable to enter edit mode")
            browser.close()
            return 1

        checks: list[tuple[str, tuple[bool, str]]] = [
            ("baseline local move/remove", _scenario_move_and_remove(page)),
            ("published edge create->undo->redo->undo", _scenario_published_edge_cycle(page, token)),
            (
                "multi-layout published delete->undo->redo",
                _scenario_multi_layout_delete_cycle(page, topology_id),
            ),
            ("PATCH-backed detail-panel field undo/redo", _scenario_patch_backed_field_cycle(page)),
        ]

        for name, (ok, message) in checks:
            if not ok:
                print(f"FAIL: {name}: {message}")
                browser.close()
                return 1
            print(f"PASS: {name}: {message}")

        print(
            "PASS: HT-032 browser proof "
            "(published edge cycle + multi-layout delete cycle + PATCH-backed stacked field cycle)"
        )
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(_run())
