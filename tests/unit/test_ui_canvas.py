"""Unit tests for Cytoscape canvas initialization safeguards."""
import asyncio
import json
import inspect
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from src.models.types import DeviceType
from src.ui.components.canvas import render_canvas
from src.ui.components.canvas_container_actions import CANVAS_CONTAINER_ACTIONS_JS
from src.ui.components.canvas_container_drag_events import CANVAS_CONTAINER_DRAG_EVENTS_JS
from src.ui.components.canvas_container_events import CANVAS_CONTAINER_EVENTS_JS
from src.ui.components.canvas_draft import CANVAS_DRAFT_JS
from src.ui.components.canvas_draft_events import CANVAS_DRAFT_EVENTS_JS
from src.ui.components.canvas_draft_publish import CANVAS_DRAFT_PUBLISH_JS
from src.ui.components.canvas_js_interactions import CANVAS_INTERACTIONS_JS
from src.ui.components.canvas_js import CANVAS_INIT_JS_TEMPLATE as _CANVAS_INIT_JS_TEMPLATE
from src.ui.components.canvas_js_resize import CANVAS_RESIZE_JS
from src.ui.components.canvas_js_helpers import CANVAS_HELPERS_JS
from src.ui.components.canvas_js_resize_part_b import CANVAS_RESIZE_JS_PART_B
from src.ui.components.canvas_js_resize_part_c import CANVAS_RESIZE_JS_PART_C
from src.ui.components.canvas_styles import _container_watermark_uri
from src.ui.components.canvas_tooltip import _CANVAS_TOOLTIP_JS
from src.ui.components.canvas_undo_action_dispatch import handle_canvas_action_request
from src.ui.components.canvas_undo_js_core import CANVAS_UNDO_JS_CORE
from src.ui.components.canvas_undo_js_graph import CANVAS_UNDO_JS_GRAPH
from src.ui.components.canvas_undo_operation_dispatch import handle_canvas_undo_request
from src.ui.design.tokens import DEVICE_TYPE_ICONS

# _CANVAS_INIT_JS was removed (dead code); tests on template content are equivalent
_CANVAS_INIT_JS = _CANVAS_INIT_JS_TEMPLATE
from src.ui.components.canvas_events import _CANVAS_EVENTS_JS
from src.ui.components.canvas_context_menu import CONTEXT_MENU_JS
from src.ui.pages import topology
from src.ui.pages.login import login_page
from src.ui.pages.topology import topology_page
from src.ui.components.connection_detail_panel import _BRIDGE_JS as _CONNECTION_DETAIL_PANEL_BRIDGE_JS
from src.ui.components.device_detail_panel_bridge import DEVICE_DETAIL_PANEL_BRIDGE_JS
from src.ui.services.topology_data_helpers import _is_draft_data


def _line_count(path: str) -> int:
    return len(Path(path).read_text().splitlines())


def _between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def _resolve_detach_aware_drop_parent_for_test(
    *,
    node_center: tuple[float, float],
    node_id: str,
    origin_parent_id: str | None,
    origin_parent_box: dict[str, float] | None,
    drag_parent_box: dict[str, float] | None = None,
    compounds: list[dict[str, object]],
) -> str | None:
    def _contains(box: dict[str, float], point: tuple[float, float], tol: float = 0.0) -> bool:
        return (
            point[0] >= box["x1"] - tol
            and point[0] <= box["x2"] + tol
            and point[1] >= box["y1"] - tol
            and point[1] <= box["y2"] + tol
        )

    def _resolve(ignore_parent_id: str | None = None) -> str | None:
        ranked: list[tuple[int, float, float, str]] = []
        effective_origin_parent_box = drag_parent_box or origin_parent_box
        for compound in compounds:
            compound_id = str(compound["id"])
            if compound_id == node_id or compound_id == ignore_parent_id:
                continue
            if bool(compound.get("locked", False)):
                continue
            if node_id in compound.get("ancestors", []):
                continue
            box = (
                effective_origin_parent_box
                if compound_id == origin_parent_id and effective_origin_parent_box
                else compound["box"]
            )
            if not _contains(box, node_center):
                continue
            width = max(0.0, box["x2"] - box["x1"])
            height = max(0.0, box["y2"] - box["y1"])
            center_x = (box["x1"] + box["x2"]) / 2.0
            center_y = (box["y1"] + box["y2"]) / 2.0
            ranked.append((
                -int(compound.get("depth", 0)),
                width * height,
                ((node_center[0] - center_x) ** 2 + (node_center[1] - center_y) ** 2) ** 0.5,
                compound_id,
            ))
        ranked.sort()
        return ranked[0][3] if ranked else None

    resolved_parent = _resolve()
    if resolved_parent and resolved_parent != origin_parent_id:
        return resolved_parent

    effective_origin_parent_box = drag_parent_box or origin_parent_box
    if origin_parent_id and effective_origin_parent_box and _contains(effective_origin_parent_box, node_center, tol=4.0):
        return origin_parent_id

    fallback_parent = _resolve(origin_parent_id)
    if fallback_parent:
        return fallback_parent
    return None


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeDiagramClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __aenter__(self) -> "_FakeDiagramClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str], timeout: float) -> _FakeResponse:
        self.calls.append("get")
        return _FakeResponse(200, {"items": [{"id": "layout-id", "name": "Autosave"}]})

    async def put(
        self,
        url: str,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> _FakeResponse:
        self.calls.append("put")
        return _FakeResponse(200)

    async def post(
        self,
        url: str,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> _FakeResponse:
        self.calls.append("post")
        return _FakeResponse(201)


class TestCanvasInitializationGuards:
    def test_init_canvas_retries_are_bounded(self) -> None:
        assert "HT_CANVAS_INIT_MAX_ATTEMPTS = 50" in _CANVAS_INIT_JS
        assert "HT_CANVAS_RETRY_DELAY_MS = 100" in _CANVAS_INIT_JS
        assert _CANVAS_INIT_JS.count("currentAttempt >= HT_CANVAS_INIT_MAX_ATTEMPTS") == 2
        assert _CANVAS_INIT_JS.count("currentAttempt + 1") == 2
        assert re.search(
            r"window\.initCanvas = function\(\s*elements,\s*savedPositions,\s*deviceShapes,\s*attempt\s*\)",
            _CANVAS_INIT_JS,
        )

    def test_init_canvas_waits_for_two_stable_animation_frames(self) -> None:
        assert _CANVAS_INIT_JS.count("window.requestAnimationFrame(function() {") >= 2
        assert "var frameOne = {" in _CANVAS_INIT_JS
        assert "var frameTwo = {" in _CANVAS_INIT_JS
        assert "frameOne.width === frameTwo.width && frameOne.height === frameTwo.height" in _CANVAS_INIT_JS

    def test_init_canvas_emits_console_error_when_retries_exhausted(self) -> None:
        assert (
            "console.error('Hometower canvas init failed: Cytoscape did not load within 5 seconds.');"
            in _CANVAS_INIT_JS
        )
        assert (
            "console.error('Hometower canvas init failed: #cy container not ready within 5 seconds.');"
            in _CANVAS_INIT_JS
        )

    def test_palette_drop_converts_rendered_to_model_with_zoom_and_pan(self) -> None:
        assert "var zoom = cy.zoom();" in _CANVAS_INIT_JS
        assert "var pan = cy.pan();" in _CANVAS_INIT_JS
        assert "var renderedX = e.clientX - rect.left;" in _CANVAS_INIT_JS
        assert "var renderedY = e.clientY - rect.top;" in _CANVAS_INIT_JS
        assert "var pos = { x: (renderedX - pan.x) / zoom, y: (renderedY - pan.y) / zoom };" in _CANVAS_INIT_JS
        assert "renderedToModel" not in _CANVAS_INIT_JS

    def test_canvas_container_uses_absolute_fill_layout(self) -> None:
        source = inspect.getsource(render_canvas)
        assert "position: absolute; top: 0; right: 0; bottom: 0; left: 0;" in source
        assert "width: 100%; height: 100%; background-color:" in source

    def test_canvas_injects_resize_overlay_root(self) -> None:
        source = inspect.getsource(render_canvas)
        assert "id=\"ht-node-resize-overlay\"" in source
        assert "pointer-events: none; z-index: 8;" in source

    def test_canvas_container_events_file_stays_under_repo_cap(self) -> None:
        assert _line_count("src/ui/components/canvas_container_events.py") <= 250

    def test_topology_uses_shell_ids_for_canvas_layout(self) -> None:
        source = inspect.getsource(topology_page)
        assert 'id="ht-topology-shell"' in source
        assert 'id="ht-topology-workspace"' in source
        assert 'id="ht-topology-canvas-stage"' in source
        assert 'id="ht-topology-right-rail"' in source
        assert "render_topology_left_rail(stencil_devices, placed_ids)" in source
        assert "render_network_filter_panel(" not in source

    def test_topology_renders_header_actions_and_device_panel_shell(self) -> None:
        source = inspect.getsource(topology_page)
        assert "render_detail_panel(token, user_role)" in source
        assert "_render_header_actions" in source
        assert "render_topology_left_rail(stencil_devices, placed_ids)" in source
        assert "inject_network_overlay()" in source

    def test_topology_gates_left_rail_to_non_readers_and_arms_shell_runtime(self) -> None:
        source = inspect.getsource(topology_page)
        assert "if role != Role.Reader:" in source
        assert 'id="ht-topology-left-rail"' not in source
        assert "inject_topology_layout_runtime()" in source
        assert "inject_topology_layout_shell_css()" in source
        assert "arm_topology_layout_runtime()" in source

    def test_topology_page_column_explicitly_fills_shell_height(self) -> None:
        source = inspect.getsource(topology_page)

        assert 'id="ht-topology-page"' in source
        assert "height:100%;" in source

    def test_topology_shell_css_caps_left_rail_and_releases_hidden_right_rail(self) -> None:
        from src.ui.components.topology_layout_shell import _TOPOLOGY_LAYOUT_SHELL_CSS

        assert "flex: 0 0 260px;" in _TOPOLOGY_LAYOUT_SHELL_CSS
        assert "max-width: 260px;" in _TOPOLOGY_LAYOUT_SHELL_CSS
        assert "#ht-topology-right-rail:has(> .ht-right-rail-panel[style*=\"display: flex\"])" in _TOPOLOGY_LAYOUT_SHELL_CSS
        assert "width: 0;" in _TOPOLOGY_LAYOUT_SHELL_CSS

    def test_device_and_connection_panel_bridges_dispatch_layout_sync_on_close_paths(self) -> None:
        assert "ht:topology-layout-sync" in DEVICE_DETAIL_PANEL_BRIDGE_JS
        assert "devicePanel.style.display = 'none'" not in DEVICE_DETAIL_PANEL_BRIDGE_JS
        assert "ghostPanel.style.display = 'none'" not in DEVICE_DETAIL_PANEL_BRIDGE_JS
        assert "ht:topology-layout-sync" in _CONNECTION_DETAIL_PANEL_BRIDGE_JS
        assert "panel.style.display = 'none'" not in _CONNECTION_DETAIL_PANEL_BRIDGE_JS

    def test_canvas_close_panel_handler_hides_all_right_rail_panels_via_sync_bridge(self) -> None:
        assert "document.addEventListener('ht:close-panel'" in _CANVAS_EVENTS_JS
        assert "ghost-detail-panel" in _CANVAS_EVENTS_JS
        assert "ht:topology-layout-sync" in _CANVAS_EVENTS_JS
        assert "['device-detail-panel', 'connection-detail-panel']" not in _CANVAS_EVENTS_JS

    def test_topology_renders_restore_summary_banner_and_ghost_panel(self) -> None:
        source = inspect.getsource(topology_page)
        assert "render_restore_summary_banner(restore_summary)" in source
        assert "render_ghost_detail_panel(token, user_role, topology_id)" in source

    def test_canvas_globals_are_defined(self) -> None:
        expected_globals = [
            "initCanvas",
            "getCanvasJson",
            "addNodeToCanvas",
            "addEdgeToCanvas",
            "applyTopologySnapshot",
        ]
        for function_name in expected_globals:
            assert f"window.{function_name} = function" in _CANVAS_INIT_JS

    def test_canvas_init_template_wires_resize_bridge(self) -> None:
        assert "window._htBindCanvasResize" in _CANVAS_INIT_JS_TEMPLATE
        assert "window._htResizeSetEnabled(false)" in _CANVAS_INIT_JS_TEMPLATE
        assert "window._htResizeSetEnabled = function(enabled)" in CANVAS_RESIZE_JS

    def test_snapshot_apply_rehydrates_elements_and_emits_restore_summary_event(self) -> None:
        assert "window._cy.elements().remove();" in _CANVAS_INIT_JS_TEMPLATE
        assert "window._htRestoreSummary = summary;" in _CANVAS_INIT_JS_TEMPLATE
        assert "ht:restore-summary-updated" in _CANVAS_INIT_JS_TEMPLATE

    def test_snapshot_apply_syncs_resize_overlay_from_selection(self) -> None:
        assert "window._htResizeSyncFromSelection" in _CANVAS_INIT_JS_TEMPLATE

    def test_node_tap_emits_device_selected_event(self) -> None:
        """Node tap handler should notify the right-side device panel."""
        assert "new CustomEvent('ht:node-selected'" in _CANVAS_INIT_JS_TEMPLATE
        assert "id: node.id()" in _CANVAS_INIT_JS_TEMPLATE
        assert "data: detail" in _CANVAS_INIT_JS_TEMPLATE

    def test_node_tap_skips_panel_open_on_shift_or_association_mode(self) -> None:
        """Shift+tap and association mode should not open device panel."""
        assert "shiftKey" in _CANVAS_INIT_JS_TEMPLATE
        assert "window._htEdgeSource" in _CANVAS_EVENTS_JS

    def test_canvas_has_zoom_limits(self) -> None:
        """Canvas init should configure minZoom and maxZoom."""
        assert "minZoom" in _CANVAS_INIT_JS_TEMPLATE
        assert "maxZoom" in _CANVAS_INIT_JS_TEMPLATE

    def test_canvas_uses_saved_positions_and_viewport_as_separate_concepts(self) -> None:
        assert "var hasSavedPositions = _htHasSavedNodePositions(savedPositions);" in _CANVAS_INIT_JS
        assert "var hasSavedViewport = _htHasSavedViewport(savedPositions);" in _CANVAS_INIT_JS
        assert "savedPositions && savedPositions.pan\n                ? { name: 'preset' }\n                : { name: 'cose', animate: false }," not in _CANVAS_INIT_JS

    def test_saved_position_detection_treats_group_less_list_entries_as_nodes(self) -> None:
        node_entries_helper = _between(
            _CANVAS_INIT_JS_TEMPLATE,
            "    function _htNodeEntries(rawElements) {",
            "\n\n    function _htStripLayoutMetadata(cytoscapeJson) {",
        )
        assert "if (Array.isArray(rawElements)) {" in node_entries_helper
        assert "if (!elem.group) elem.group = 'nodes';" in node_entries_helper
        assert "return rawElements;" in node_entries_helper

        has_saved_positions_helper = _between(
            _CANVAS_INIT_JS_TEMPLATE,
            "    window._htHasSavedNodePositions = function(cytoscapeJson) {",
            "\n\n    window._htHasSavedViewport = function(cytoscapeJson) {",
        )
        assert "return _htNodeEntries(cytoscapeJson && cytoscapeJson.elements).some(function(elem) {" in has_saved_positions_helper
        assert "return elem.group === 'nodes'" in has_saved_positions_helper

    def test_first_load_runs_cose_and_marks_nodes_positioned(self) -> None:
        assert "function _htRunFirstLoadLayout(cy, hasSavedViewport) {" in _CANVAS_INIT_JS
        assert "cy.layout({ name: 'cose', animate: false, fit: false }).run();" in _CANVAS_INIT_JS
        assert "_htMarkNodesPositioned(cy.nodes());" in _CANVAS_INIT_JS
        assert "if (!hasSavedViewport) cy.fit(undefined, 40);" in _CANVAS_INIT_JS

    def test_auto_layout_bridge_uses_readonly_guard_and_autosave(self) -> None:
        assert "window.htAutoLayout = function(options) {" in _CANVAS_INIT_JS
        assert "if (window.HT_READONLY)" in _CANVAS_INIT_JS
        assert "name: 'breadthfirst'" in _CANVAS_INIT_JS
        assert "animationDuration: 500" in _CANVAS_INIT_JS
        assert "window.scheduleAutosave(300);" in _CANVAS_INIT_JS

    def test_saved_viewport_is_preserved_when_only_new_nodes_need_overflow_placement(self) -> None:
        assert "return n.data('_positioned') !== true;" in _CANVAS_INIT_JS
        assert "var placedCount = _htPlaceOverflowNodes(cy);" in _CANVAS_INIT_JS
        assert "_htRestoreViewport(cy, savedPositions);" in _CANVAS_INIT_JS
        assert "if (placedCount > 0 && !hasSavedViewport) cy.fit(undefined, 40);" in _CANVAS_INIT_JS

    def test_collapsed_state_recovery_runs_even_if_layout_path_throws(self) -> None:
        assert "console.error('Hometower canvas layout init failed:', layoutError);" in _CANVAS_INIT_JS
        assert re.search(
            r"try \{\s*_htApplyCollapsedState\(cy\);\s*\} catch \(collapsedError\)",
            _CANVAS_INIT_JS,
        )

    def test_canvas_serialization_persists_positioned_nodes(self) -> None:
        assert "if (elem.group !== 'nodes') return;" in _CANVAS_INIT_JS_TEMPLATE
        assert "elem.data._positioned = true;" in _CANVAS_INIT_JS_TEMPLATE

    def test_pruned_draft_layout_cleanup_is_logged_and_silent(self) -> None:
        assert "window._htPersistPrunedLayoutCleanup = function(cytoscapeJson) {" in _CANVAS_INIT_JS_TEMPLATE
        assert "console.info('[Hometower] Pruned ' + prunedCount + ' orphaned draft nodes from saved layout.');" in _CANVAS_INIT_JS_TEMPLATE
        cleanup_helper = _between(
            _CANVAS_INIT_JS_TEMPLATE,
            "    window._htPersistPrunedLayoutCleanup = function(cytoscapeJson) {",
            "\n\n    window.getCanvasJson = function() {",
        )
        assert "window.HT_CAN_PATCH_DIAGRAMS !== true" in cleanup_helper
        assert "window.HT_READONLY" not in cleanup_helper
        assert "_htNotify" not in cleanup_helper

    def test_topology_injects_diagram_patch_capability_separate_from_readonly(self) -> None:
        source = inspect.getsource(topology_page)
        assert "can_patch_diagrams = role in (Role.Admin, Role.Contributor)" in source
        assert "window.HT_CAN_PATCH_DIAGRAMS" in source
        assert "window.HT_READONLY = true" in source


class TestUiRegressionFixes:
    def test_topology_context_menu_omits_edit_action(self) -> None:
        assert "Start Association" in CONTEXT_MENU_JS
        assert "Duplicate" in CONTEXT_MENU_JS
        assert "Delete" in CONTEXT_MENU_JS
        assert "{ label: 'Edit'" not in CONTEXT_MENU_JS

    def test_context_menu_skips_ghost_placeholders(self) -> None:
        assert "var isGhost" in CONTEXT_MENU_JS
        assert "if (isGhost) return;" in CONTEXT_MENU_JS

    def test_context_menu_exits_before_rendering_when_readonly(self) -> None:
        readonly_guard = "if (window.HT_READONLY) return;"
        assert readonly_guard in CONTEXT_MENU_JS
        assert CONTEXT_MENU_JS.index(readonly_guard) < CONTEXT_MENU_JS.index(
            "var existing = document.getElementById('ht-ctx-menu');"
        )

    def test_context_menu_exposes_remove_from_container_for_children_only(self) -> None:
        assert "var hasParent" in CONTEXT_MENU_JS
        assert "Remove from container" in CONTEXT_MENU_JS
        assert "hide: !hasParent" in CONTEXT_MENU_JS

    def test_context_menu_allows_convert_to_container_for_drafts(self) -> None:
        assert "Convert to Container" in CONTEXT_MENU_JS
        assert "hide: isContainer" in CONTEXT_MENU_JS
        assert "hide: isContainer || isDraft" not in CONTEXT_MENU_JS

    def test_association_mode_supports_context_menu_start(self) -> None:
        assert "ht:association-source" in _CANVAS_EVENTS_JS
        assert "Association source selected." in _CANVAS_EVENTS_JS
        assert "_createAssociation(sourceId, targetId);" in _CANVAS_EVENTS_JS

    def test_node_delete_surfaces_api_error_feedback(self) -> None:
        assert "Delete device '" in _CANVAS_EVENTS_JS
        assert "This cannot be undone." in _CANVAS_EVENTS_JS


class TestHt077DragDetachSemantics:
    def test_detach_aware_drop_prefers_non_origin_container_before_detach(self) -> None:
        assert "var effectiveOriginParentBox = (origin && origin.dragParentBox) || (origin && origin.parentBox);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var resolvedParent = _htResolveDropParent(node, originParentId, effectiveOriginParentBox);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (resolvedParent && resolvedParent !== originParentId) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "return resolvedParent;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var fallbackParent = _htResolveDropParentIgnoring(node, originParentId);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (fallbackParent) return fallbackParent;" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_drop_parent_uses_absolute_node_bounds_center_for_cross_container_reparent(self) -> None:
        assert "function _htNodeDropPoint(node) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var box = node.boundingBox" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "x: (box.x1 + box.x2) / 2," in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "y: (box.y1 + box.y2) / 2" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var nodePoint = _htNodeDropPoint(node);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var nodePos = node.position();" not in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_cross_container_drop_reparents_even_when_child_local_position_is_origin_relative(self) -> None:
        destination_box = {"x1": 200.0, "y1": 200.0, "x2": 320.0, "y2": 320.0}
        origin_box = {"x1": 0.0, "y1": 0.0, "x2": 140.0, "y2": 140.0}
        local_child_position = (24.0, 18.0)
        absolute_child_center = (248.0, 244.0)

        assert not (
            destination_box["x1"] <= local_child_position[0] <= destination_box["x2"]
            and destination_box["y1"] <= local_child_position[1] <= destination_box["y2"]
        )

        resolved = _resolve_detach_aware_drop_parent_for_test(
            node_center=absolute_child_center,
            node_id="child-id",
            origin_parent_id="origin-container",
            origin_parent_box=origin_box,
            compounds=[
                {"id": "origin-container", "box": origin_box},
                {"id": "destination-container", "box": destination_box},
            ],
        )

        assert resolved == "destination-container"

    def test_drop_outside_all_valid_containers_detaches_to_top_level(self) -> None:
        resolved = _resolve_detach_aware_drop_parent_for_test(
            node_center=(188.0, 188.0),
            node_id="child-id",
            origin_parent_id="origin-container",
            origin_parent_box={"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0},
            compounds=[{"id": "origin-container", "box": {"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0}}],
        )

        assert resolved is None

    def test_drop_inside_origin_container_keeps_origin_parent(self) -> None:
        resolved = _resolve_detach_aware_drop_parent_for_test(
            node_center=(64.0, 62.0),
            node_id="child-id",
            origin_parent_id="origin-container",
            origin_parent_box={"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0},
            compounds=[{"id": "origin-container", "box": {"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0}}],
        )

        assert resolved == "origin-container"

    def test_drop_inside_live_grown_origin_container_keeps_origin_parent(self) -> None:
        resolved = _resolve_detach_aware_drop_parent_for_test(
            node_center=(156.0, 60.0),
            node_id="child-id",
            origin_parent_id="origin-container",
            origin_parent_box={"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0},
            drag_parent_box={"x1": 0.0, "y1": 0.0, "x2": 180.0, "y2": 120.0},
            compounds=[{"id": "origin-container", "box": {"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0}}],
        )

        assert resolved == "origin-container"

    def test_detach_aware_drop_uses_live_origin_bounds_for_keep_or_detach(self) -> None:
        assert "var effectiveOriginParentBox = (origin && origin.dragParentBox) || (origin && origin.parentBox);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var parentBox = parent && parent.length" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "? _htRenderedBounds(parent)" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "return originParentId;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "return null;" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_drop_parent_allows_ignoring_origin_parent_id(self) -> None:
        assert "function _htResolveDropParentIgnoring(node, ignoreParentId) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var ignoredParentId = _htNormalizeParentId(ignoreParentId);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "compoundId === nodeId || compoundId === ignoredId" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "_confirmDelete(" in _CANVAS_EVENTS_JS
        assert "window._htRequestCanvasAction" in _CANVAS_EVENTS_JS
        assert "type: 'delete_published_node'" in _CANVAS_EVENTS_JS
        assert "fetch('/api/devices/' + d.id" not in _CANVAS_EVENTS_JS

    def test_edge_delete_requires_confirmation(self) -> None:
        assert "Delete this connection? This cannot be undone." in _CANVAS_EVENTS_JS
        assert "Delete connection '" in _CANVAS_EVENTS_JS
        assert "_confirmDelete(edgePrompt" in _CANVAS_EVENTS_JS
        assert "ht:edge-delete" in _CANVAS_EVENTS_JS
        assert "_deleteAssociation(evt.detail || {});" in _CANVAS_EVENTS_JS
        assert "type: 'delete_edge'" in CANVAS_HELPERS_JS
        assert "window._htRequestCanvasAction" in CANVAS_HELPERS_JS
        assert "fetch('/api/connections/' + d.id" not in CANVAS_HELPERS_JS

    def test_published_edge_create_uses_undo_request_bridge(self) -> None:
        assert "type: 'create_edge'" in CANVAS_HELPERS_JS
        assert "scope: 'published'" in CANVAS_HELPERS_JS
        assert "fetch('/api/connections/'" not in CANVAS_HELPERS_JS

    def test_remove_from_view_routes_through_local_undo_helper(self) -> None:
        assert "window._htCommitLocalRemoveFromView" in CANVAS_DRAFT_EVENTS_JS
        assert "window._htCommitLocalRemoveFromView(el);" in CANVAS_DRAFT_EVENTS_JS
        assert "el.connectedEdges().remove();" not in CANVAS_DRAFT_EVENTS_JS

    def test_canvas_events_include_html_escape_helper(self) -> None:
        assert "var _escapeHtml = window._htEscapeHtml;" in _CANVAS_EVENTS_JS
        assert "_escapeHtml(edgeLabel)" in _CANVAS_EVENTS_JS
        assert "_escapeHtml(deviceName)" in _CANVAS_EVENTS_JS

    def test_edge_delete_escapes_raw_label_in_delete_prompt(self) -> None:
        assert "var edgeLabel = d.raw_label || d.label || (d.data && (d.data.raw_label || d.data.label));" in CANVAS_HELPERS_JS
        assert "Delete connection '" in CANVAS_HELPERS_JS
        assert "_escapeHtml(edgeLabel)" in CANVAS_HELPERS_JS

    def test_custom_field_delete_requires_confirmation_dialog(self) -> None:
        from src.ui.components import device_detail_custom_fields_section

        source = inspect.getsource(
            device_detail_custom_fields_section.render_custom_fields_section
        )
        assert "Delete custom field '" in source
        assert "lambda dlg=confirm_dlg: dlg.open()" in source
        assert 'secondary_button(ui.button("Cancel"' in source
        assert 'danger_button(ui.button("Delete"' in source

    def test_tag_detach_requires_confirmation_dialog(self) -> None:
        from src.ui.components import device_detail_tags_section

        source = inspect.getsource(device_detail_tags_section.render_tags_section)
        assert "Remove tag '" in source
        assert "lambda dlg=confirm_dlg: dlg.open()" in source
        assert 'secondary_button(ui.button("Cancel"' in source
        assert 'danger_button(ui.button("Remove"' in source

    def test_login_password_input_submits_on_enter(self) -> None:
        source = inspect.getsource(login_page)
        assert '.on("keydown.enter", handle_login)' in source

    def test_topology_accepts_device_id_query_param(self) -> None:
        source = inspect.getsource(topology_page)
        assert "device_id: str = \"\"" in source
        assert "if device_id:" in source

    def test_topology_expired_redirect_preserves_deep_link_query_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, str | None] = {}

        def _fake_redirect_if_unauthenticated(*, current_path: str | None = None) -> bool:
            captured["current_path"] = current_path
            return True

        monkeypatch.setattr(topology, "redirect_if_unauthenticated", _fake_redirect_if_unauthenticated)

        asyncio.run(
            topology_page(
                request=SimpleNamespace(
                    url=SimpleNamespace(
                        path="/topology",
                        query="workspace_id=ws-1&topology_id=topo-1&device_id=dev-1",
                    )
                ),
                device_id="dev-1",
                topology_id="topo-1",
                workspace_id="ws-1",
            )
        )

        assert captured["current_path"] == "/topology?workspace_id=ws-1&topology_id=topo-1&device_id=dev-1"

    def test_topology_deeplink_focus_script_dispatches_node_selected(self) -> None:
        assert "window._cy.getElementById(targetId)" in topology._FOCUS_DEVICE_JS_TEMPLATE
        assert "new CustomEvent('ht:node-selected'" in topology._FOCUS_DEVICE_JS_TEMPLATE
        assert "node.select();" in topology._FOCUS_DEVICE_JS_TEMPLATE

    def test_topology_deeplink_focus_script_dispatches_fallback_when_node_missing(self) -> None:
        script = topology._FOCUS_DEVICE_JS_TEMPLATE
        assert "if (!node || !node.length) {" in script
        assert "id: targetId" in script
        assert "data: {}" in script

    def test_topology_deeplink_focus_script_waits_for_bridge_and_socket_readiness(self) -> None:
        script = topology._FOCUS_DEVICE_JS_TEMPLATE
        assert "window._htDetailBridgeInit" in script
        assert "window.did_handshake === true" in script
        assert "window.socket &&" in script
        assert "window.socket.connected" in script
        assert "dispatchNodeSelected(" in script

    def test_topology_reentry_resets_events_guard_on_pagehide(self) -> None:
        source = inspect.getsource(topology_page)
        assert "window._htEventsWired=false" in source
        assert "window.addEventListener('pagehide'" in source

    def test_draft_tooltip_skips_device_fetch_and_uses_static_copy(self) -> None:
        assert "Unpublished draft — publish to save" in _CANVAS_TOOLTIP_JS
        assert "nodeId.indexOf('draft-') === 0" in _CANVAS_TOOLTIP_JS
        assert _CANVAS_TOOLTIP_JS.index("nodeId.indexOf('draft-') === 0") < _CANVAS_TOOLTIP_JS.index(
            "fetch('/api/devices/' + nodeId + '?include=services'"
        )

    def test_draft_tooltip_mouseover_short_circuits_before_cache_or_fetch(self) -> None:
        mouseover_handler = _between(
            _CANVAS_TOOLTIP_JS,
            "        cy.on('mouseover', 'node', function(evt) {",
            "\n\n        cy.on('mouseout', 'node', function() {",
        )
        draft_branch = _between(
            mouseover_handler,
            "            if (nodeId.indexOf('draft-') === 0) {",
            "\n            if (window._htServicesCache[nodeId] !== undefined) {",
        )

        assert "window._htShowDraftTooltip(evt);" in draft_branch
        assert "return;" in draft_branch
        assert "window._htServicesCache[nodeId]" not in draft_branch
        assert "fetch('/api/devices/' + nodeId + '?include=services'" not in draft_branch


class TestHt060ContainerCoordination:
    def test_stencil_drop_dispatcher_forwards_inventory_device_version(self) -> None:
        assert "deviceVersion: e.dataTransfer.getData('inventoryDeviceVersion')" in CANVAS_INTERACTIONS_JS

    def test_published_reparent_does_not_prefetch_device_before_patch(self) -> None:
        assert "fetch('/api/devices/' + nodeId, { credentials: 'include' })" not in CANVAS_CONTAINER_EVENTS_JS

    def test_published_reparent_uses_dedicated_undo_bridge_action(self) -> None:
        assert "type: 'reparent_device'" in CANVAS_CONTAINER_ACTIONS_JS
        assert "forward': {\"op\": \"reparent_device\"" not in CANVAS_CONTAINER_EVENTS_JS
        assert "window._htRequestCanvasAction({" in CANVAS_CONTAINER_ACTIONS_JS

    def test_drag_reparent_contract_is_composed_from_dedicated_module(self) -> None:
        from src.ui.components import canvas_container_events

        source = inspect.getsource(canvas_container_events)
        assert "CANVAS_CONTAINER_DRAG_EVENTS_JS" in source
        assert "function _htResolveDetachAwareDropParent(node, origin)" in CANVAS_CONTAINER_EVENTS_JS

    def test_convert_container_event_marks_node_with_container_class(self) -> None:
        assert "document.addEventListener('ht:node-convert-container'" in CANVAS_CONTAINER_EVENTS_JS
        assert "node.addClass('container');" in CANVAS_CONTAINER_EVENTS_JS

    def test_drag_parent_resolution_includes_css_container_nodes(self) -> None:
        assert "cy.nodes(':parent, .container')" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_draft_reparent_stays_layout_local(self) -> None:
        assert "window._htIsDraft && window._htIsDraft(node.id())" in CANVAS_CONTAINER_ACTIONS_JS
        assert "execution: 'local'" in CANVAS_CONTAINER_ACTIONS_JS

    def test_reparent_tracks_drag_origin_rendered_position(self) -> None:
        assert "_htContainerDragOrigin" in CANVAS_CONTAINER_EVENTS_JS
        assert "renderedPosition: _htCurrentRenderedPosition(node)" in CANVAS_CONTAINER_EVENTS_JS
        assert "_htSnapBackNode(" in CANVAS_CONTAINER_EVENTS_JS

    def test_drag_out_detach_and_growth_are_wired_with_readonly_guard(self) -> None:
        assert "cy.on('drag', 'node'" in CANVAS_CONTAINER_EVENTS_JS
        assert "window._htMaybeGrowContainerForDraggedChild" in CANVAS_CONTAINER_EVENTS_JS
        assert "document.addEventListener('ht:node-remove-from-container'" in CANVAS_CONTAINER_EVENTS_JS
        assert "_htResolveDetachAwareDropParent" in CANVAS_CONTAINER_EVENTS_JS

    def test_drag_out_detach_uses_center_vs_parent_bounds_with_tolerance(self) -> None:
        assert "var effectiveOriginParentBox = (origin && origin.dragParentBox) || (origin && origin.parentBox);" in CANVAS_CONTAINER_EVENTS_JS
        assert "var resolvedParent = _htResolveDropParent(node, originParentId, effectiveOriginParentBox);" in CANVAS_CONTAINER_EVENTS_JS
        assert "var originParentId = _htNormalizeParentId(origin && origin.parentId);" in CANVAS_CONTAINER_EVENTS_JS
        assert "if (resolvedParent && resolvedParent !== originParentId) {" in CANVAS_CONTAINER_EVENTS_JS
        assert "function _htCollectDropParentCandidates(node, ignoredParentId, frozenParentId, frozenParentBounds) {" in CANVAS_CONTAINER_EVENTS_JS
        assert "var ranked = _htCollectDropParentCandidates(node, null, frozenParentId, frozenParentBounds);" in CANVAS_CONTAINER_EVENTS_JS
        assert "return ranked.length ? _htNormalizeParentId(ranked[0].id) : null;" in CANVAS_CONTAINER_EVENTS_JS
        assert "function _htDropCandidateIsLocked(node) {" in CANVAS_CONTAINER_EVENTS_JS
        assert "var centerX = (nodeBox.x1 + nodeBox.x2) / 2;" in CANVAS_CONTAINER_EVENTS_JS
        assert "var centerY = (nodeBox.y1 + nodeBox.y2) / 2;" in CANVAS_CONTAINER_EVENTS_JS
        assert "var tol = 4;" in CANVAS_CONTAINER_EVENTS_JS
        assert "return null;" in CANVAS_CONTAINER_EVENTS_JS

    def test_detach_helpers_remain_top_level_and_capture_parent_bounds(self) -> None:
        resolve_parent = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "        function _htResolveDropParent(node, frozenParentId, frozenParentBounds) {",
            "\n\n        function _htResolveDetachAwareDropParent(node, origin) {",
        )
        resolve_detach = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "        function _htResolveDetachAwareDropParent(node, origin) {",
            "\n\n        function _htSnapBackNode(node) {",
        )

        assert "function _htResolveDetachAwareDropParent" not in resolve_parent
        assert "function _htSnapBackNode" not in resolve_parent
        assert "function _htSnapBackNode" not in resolve_detach
        assert "var parentBox = parent && parent.length" in CANVAS_CONTAINER_EVENTS_JS
        assert "parentBox: _htCloneBounds(parentBox)," in CANVAS_CONTAINER_EVENTS_JS
        assert "parentRenderedBounds: parent && parent.length ? _htRenderedBounds(parent) : null," in CANVAS_CONTAINER_EVENTS_JS
        assert "dragParentBox: _htCloneBounds(parentBox)," in CANVAS_CONTAINER_EVENTS_JS
        assert "if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {" in CANVAS_CONTAINER_EVENTS_JS

    def test_drag_reparent_requires_preselected_leaf_node(self) -> None:
        assert "wasSelected: !!(node.selected && node.selected())," in CANVAS_CONTAINER_EVENTS_JS
        assert "isContainerNode: !!((node.hasClass && node.hasClass('container')) || (node.isParent && node.isParent()))," in CANVAS_CONTAINER_EVENTS_JS
        assert "if (origin && origin.isContainerNode) {" not in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var isSelectedForReparent = !!(" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "ownership && ownership.ownershipFrozen && ownership.selectedAtPointerdown" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "!ownership && origin && origin.wasSelected && dragDistance >= 5" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "node.selected && node.selected() && dragDistance >= 5 && origin" not in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (!isSelectedForReparent) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_drag_out_prefers_a_different_valid_container_before_detaching(self) -> None:
        resolve_detach = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "        function _htResolveDetachAwareDropParent(node, origin) {",
            "\n\n        function _htSnapBackNode(node) {",
        )

        assert "if (resolvedParent && resolvedParent !== originParentId) {" in resolve_detach
        assert "return resolvedParent;" in resolve_detach
        assert resolve_detach.index("if (resolvedParent && resolvedParent !== originParentId) {") < resolve_detach.index("var parent = originParentId")
        assert resolve_detach.index("if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {") < resolve_detach.index("var fallbackParent = _htResolveDropParentIgnoring(node, originParentId);")

    def test_drag_out_detaches_to_top_level_when_drop_leaves_origin_without_new_container(self) -> None:
        resolve_detach = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "        function _htResolveDetachAwareDropParent(node, origin) {",
            "\n\n        function _htSnapBackNode(node) {",
        )

        assert "if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {" in resolve_detach
        assert "return originParentId;" in resolve_detach
        assert "return null;" in resolve_detach

    def test_drag_out_keeps_original_parent_when_released_inside_origin_container(self) -> None:
        resolve_detach = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "        function _htResolveDetachAwareDropParent(node, origin) {",
            "\n\n        function _htSnapBackNode(node) {",
        )

        assert "if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {" in resolve_detach
        assert "return originParentId;" in resolve_detach
        assert resolve_detach.index("if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {") < resolve_detach.index("return null;")

    def test_drag_growth_uses_separate_bounds_without_mutating_detach_snapshot(self) -> None:
        assert "var origin = window._htContainerDragOrigin && window._htContainerDragOrigin[String(node.id())];" in CANVAS_CONTAINER_ACTIONS_JS
        assert "var parentBox = _htCloneBounds(origin && origin.dragParentBox)" in CANVAS_CONTAINER_ACTIONS_JS
        assert "|| _htCloneBounds(origin && origin.parentBox)" in CANVAS_CONTAINER_ACTIONS_JS
        assert "origin.dragParentBox = { x1: nextCenterX - (nextWidth / 2), y1: nextCenterY - (nextHeight / 2), x2: nextCenterX + (nextWidth / 2), y2: nextCenterY + (nextHeight / 2) };" in CANVAS_CONTAINER_ACTIONS_JS
        assert "origin.parentRenderedBounds = _htRenderedBoundsFromModelBounds" not in CANVAS_CONTAINER_ACTIONS_JS

    def test_successful_reparent_clears_source_container_growth_styles(self) -> None:
        success_branch = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "            if (_htRequestNodeReparent(node, {",
            "\n\n            _htSnapBackNode(node);",
        )

        assert "var sourceParentNode = cy.getElementById(currentParent);" in success_branch
        assert "sourceParentNode.removeStyle('min-width min-height width height');" in success_branch
        assert success_branch.index("sourceParentNode.removeStyle('min-width min-height width height');") < success_branch.index("_htFinalizeDragNode(nodeId, true);")

    def test_successful_reparent_suppresses_generic_move_gesture_commit(self) -> None:
        success_branch = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "            if (_htRequestNodeReparent(node, {",
            "\n\n            _htSnapBackNode(node);",
        )

        assert "window._htContainerDragCancelled = true;" in success_branch
        assert "window._htMoveGesture = null;" in success_branch
        assert success_branch.index("window._htContainerDragCancelled = true;") < success_branch.index("_htFinalizeDragNode(nodeId, true);")
        assert success_branch.index("window._htMoveGesture = null;") < success_branch.index("_htFinalizeDragNode(nodeId, true);")

    def test_detach_to_top_level_preserves_rendered_position_and_remove_label(self) -> None:
        assert "window._htRequestDetachToTopLevel = function(nodeId) {" in CANVAS_CONTAINER_ACTIONS_JS
        assert "toParentId: null," in CANVAS_CONTAINER_ACTIONS_JS
        assert "fromRenderedPosition: rendered," in CANVAS_CONTAINER_ACTIONS_JS
        assert "toRenderedPosition: rendered," in CANVAS_CONTAINER_ACTIONS_JS
        assert "label: 'Remove from container'" in CANVAS_CONTAINER_ACTIONS_JS

    def test_container_actions_wrap_api_failure_for_optimistic_reparent(self) -> None:
        assert "window._htPendingPublishedReparent" in CANVAS_CONTAINER_ACTIONS_JS
        assert "window._htResolveUndoApiFailure = function(direction, entryId, message)" in CANVAS_CONTAINER_ACTIONS_JS
        assert "window._htApplyCanvasReparent" in CANVAS_CONTAINER_ACTIONS_JS

    def test_local_detach_uses_reparent_node_undo_contract(self) -> None:
        assert "type: 'reparent_node'" in CANVAS_CONTAINER_ACTIONS_JS
        assert "forward: { op: 'reparent_node', payload: payload }" in CANVAS_CONTAINER_ACTIONS_JS
        assert "reverse: { op: 'reparent_node', payload: payload }" in CANVAS_CONTAINER_ACTIONS_JS

    def test_reparent_node_patch_only_moves_target_node_not_descendants(self) -> None:
        reparent_body = _between(
            CANVAS_UNDO_JS_GRAPH,
            "    function _reparentNode(payload) {",
            "\n\n    function _patchNode(payload) {",
        )
        assert "window._cy.getElementById(String(payload.node_id))" in reparent_body
        assert "window._htApplyCanvasReparent(node, payload.parent_id, payload.rendered_position, payload.version);" in reparent_body
        assert ".children()" not in reparent_body
        assert "descendants" not in reparent_body

    def test_canvas_drag_undo_is_batched_on_dragstart_dragend(self) -> None:
        assert "cy.on('dragstart', 'node'" in CANVAS_INTERACTIONS_JS
        assert "cy.on('dragend', 'node'" in CANVAS_INTERACTIONS_JS
        assert "window._htBeginMoveGesture" in CANVAS_INTERACTIONS_JS
        assert "window._htCommitMoveGesture" in CANVAS_INTERACTIONS_JS


class TestHt077DeterministicContainerOwnershipContract:
    def test_pointerdown_ownership_freeze_model_exists_and_is_consumed(self) -> None:
        assert "cy.on('pointerdown', 'node'" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htContainerPointerOwnership" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htContainerPointerOwnership[node.id()]" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var ownership = _htGetPointerOwnership(nodeId);" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_first_click_is_selection_only_until_ownership_gate_is_satisfied(self) -> None:
        assert "var isSelectedForReparent" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (!isSelectedForReparent) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htContainerDragCancelled = true;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "_htFinalizeDragNode(nodeId, true);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "return;" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_pointerdown_frozen_selection_gate_rejects_late_selection(self) -> None:
        assert "var selectedAtPointerdown = !!(node.selected && node.selected());" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "selectedAtPointerdown: selectedAtPointerdown" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "ownership.selectedAtPointerdown" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_selection_time_mixed_ancestor_descendant_selection_is_normalized(self) -> None:
        assert "cy.on('select unselect boxselect', 'node'" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htSelectionNormalizationInProgress" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "candidate.node.ancestors()" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "candidate.node.descendants()" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "_htNormalizeSelectionForContainerDrag" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_pointerdown_arms_ownership_without_stale_selection_normalization(self) -> None:
        assert "cy.on('pointerdown', 'node'" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htContainerPointerOwnership[node.id()]" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htContainerGestureOwner" in CANVAS_CONTAINER_DRAG_EVENTS_JS

        pointerdown_body = _between(
            CANVAS_CONTAINER_DRAG_EVENTS_JS,
            "        cy.on('pointerdown', 'node', function(evt) {",
            "\n\n        cy.on('drag', 'node', function(evt) {",
        )
        assert "_htNormalizeSelectionForContainerDrag(node);" not in pointerdown_body

    def test_grab_phase_normalizes_selection_and_assigns_ownership_for_all_selected_nodes(self) -> None:
        grab_body = _between(
            CANVAS_CONTAINER_DRAG_EVENTS_JS,
            "        cy.on('grab', 'node', function(evt) {",
            "\n\n        cy.on('pointerdown', 'node', function(evt) {",
        )
        assert "window._htNormalizeSelectionForContainerDrag(node);" in grab_body
        assert "cy.$('node:selected').forEach(function(selectedNode) {" in grab_body
        assert "selectedAtPointerdown: true" in grab_body
        assert "window._htContainerDragInProgress = true;" in grab_body

    def test_drag_hysteresis_uses_strict_five_pixel_threshold(self) -> None:
        assert "Math.hypot(" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "dragDistance" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (dragDistance < 5)" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_overlap_tie_break_order_is_depth_then_area_then_distance_then_lexical_id(self) -> None:
        assert "candidateDepth" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "candidateArea" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "candidateCenterDistance" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "localeCompare" in CANVAS_CONTAINER_DRAG_EVENTS_JS

        sort_body = _between(
            CANVAS_CONTAINER_DRAG_EVENTS_JS,
            "            ranked.sort(function(a, b) {",
            "            });\n            return ranked;",
        )
        assert sort_body.index("candidateDepth") < sort_body.index("candidateArea")
        assert sort_body.index("candidateArea") < sort_body.index("candidateCenterDistance")
        assert sort_body.index("candidateCenterDistance") < sort_body.index("localeCompare")

    def test_interruptions_cancel_drag_ownership_for_all_contract_paths(self) -> None:
        assert "pointercancel" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "Escape" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "pagehide" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "transition === 'edit-view' || transition === 'view-edit'" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "_htCancelContainerDrag" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "HT_READONLY" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_mode_transition_defers_cancel_until_drag_settles(self) -> None:
        assert "window._htContainerDragInProgress" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htDeferredContainerDragCancelReason = transition;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (!hasActiveOrigins && window._htDeferredContainerDragCancelReason) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "_htCancelContainerDrag(deferredReason);" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_interruptions_snapback_and_clear_pending_move_gesture(self) -> None:
        assert "_htSnapBackNode(draggedNode);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htContainerDragCancelled = true;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htMoveGesture = null;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htContainerGestureOwner = null;" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_readonly_cancel_notifies_only_for_active_drag_interruptions(self) -> None:
        cancel_body = _between(
            CANVAS_CONTAINER_DRAG_EVENTS_JS,
            "        function _htCancelContainerDrag(reason) {",
            "\n\n        function _htClearDragOrigin(nodeId) {",
        )
        assert "var hadActiveDrag = !!(" in cancel_body
        assert "window._htContainerDragInProgress" in cancel_body
        assert "if (reason === 'readonly-cancel' && hadActiveDrag) {" in cancel_body
        assert "_notify('Container move canceled: canvas is read-only.', 'warning');" in cancel_body

    def test_dragend_skips_move_commit_after_cancellation(self) -> None:
        assert "if (window._htContainerDragCancelled) {" in CANVAS_INTERACTIONS_JS
        assert "window._htCommitMoveGesture" in CANVAS_INTERACTIONS_JS
        assert CANVAS_INTERACTIONS_JS.index("if (window._htContainerDragCancelled) {") < CANVAS_INTERACTIONS_JS.index("window._htCommitMoveGesture")

    def test_published_reparent_keeps_pending_optimistic_lock_message_and_rollback_hooks(self) -> None:
        assert "window._htPendingPublishedReparent" in CANVAS_CONTAINER_ACTIONS_JS
        assert "version_cursor" in CANVAS_CONTAINER_ACTIONS_JS
        assert "window._htResolveUndoApiFailure = function(direction, entryId, message)" in CANVAS_CONTAINER_ACTIONS_JS
        assert "rollback" in CANVAS_CONTAINER_ACTIONS_JS
        assert "_htMoveReparentedNode(" in CANVAS_CONTAINER_ACTIONS_JS

    def test_published_reparent_success_triggers_compensating_autosave_after_api_settlement(self) -> None:
        match = re.search(
            r"window\._htResolveUndoApiSuccess = function\(direction, entryId, result\) \{(?P<body>.*?)\n\s*\};\n\n\s*var baseFailure = window\._htResolveUndoApiFailure;",
            CANVAS_CONTAINER_ACTIONS_JS,
            re.S,
        )
        assert match is not None

        success_body = match.group("body")
        assert "if (direction === 'forward') {" in success_body
        assert "_htTakePendingPublishedReparent(entryId);" in success_body
        assert "_htShouldPersistPublishedReparent(direction, hadPendingReparent, result)" in success_body
        assert "_htPersistPublishedReparentDraft();" in success_body

        persist_helper = _between(
            CANVAS_CONTAINER_ACTIONS_JS,
            "        function _htPersistPublishedReparentDraft() {",
            "\n\n        function _htShouldPersistPublishedReparent(direction, hadPendingReparent, result) {",
        )
        assert "window.scheduleAutosave(0);" in persist_helper
        assert "window._htFlushAutosave();" in persist_helper

        persist_guard = _between(
            CANVAS_CONTAINER_ACTIONS_JS,
            "        function _htShouldPersistPublishedReparent(direction, hadPendingReparent, result) {",
            "\n\n        function _htWrapPublishedReparentResolvers() {",
        )
        assert "} else if (window.requestAnimationFrame) {" in success_body
        assert "window.requestAnimationFrame(function() {" in success_body
        assert "window.setTimeout(function() {" in success_body
        assert "String(entry.type || '') === 'reparent_device'" in persist_guard
        assert "String((forward && forward.op) || '') === 'reparent_device'" in persist_guard
        assert "String((graphPatch && graphPatch.op) || '') === 'reparent_node'" in persist_guard

    def test_published_reparent_replay_success_triggers_compensating_autosave_after_api_settlement(self) -> None:
        persist_guard = _between(
            CANVAS_CONTAINER_ACTIONS_JS,
            "        function _htShouldPersistPublishedReparent(direction, hadPendingReparent, result) {",
            "\n\n        function _htWrapPublishedReparentResolvers() {",
        )

        assert "if (direction !== 'forward') return false;" not in persist_guard
        assert "entry_patch" in persist_guard
        assert "reparent_device" in persist_guard

    def test_container_child_mutual_exclusion_exists_for_drag_and_dragfree(self) -> None:
        assert "cy.on('drag', 'node'" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "cy.on('dragfree', 'node'" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (origin && origin.isContainerNode) {" not in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "isContainerNode: !!((node.hasClass && node.hasClass('container')) || (node.isParent && node.isParent()))" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (node.isParent && node.isParent()) return;" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_context_menu_bridge_uses_deterministic_event_dedup_without_timeout_race(self) -> None:
        assert "function _htDedupContextMenuRequest(id, eventId)" in CANVAS_INTERACTIONS_JS
        assert "var key = String(id) + ':' + String(eventId);" in CANVAS_INTERACTIONS_JS
        assert "window._htCtxMenuRequestKeys" in CANVAS_INTERACTIONS_JS
        assert "if (_htDedupContextMenuRequest(id, eventId)) return;" in CANVAS_INTERACTIONS_JS
        assert "window.setTimeout(function() { window._htCtxMenuBridgeHandled = false; }, 50);" not in CANVAS_INTERACTIONS_JS
        assert "_htCtxMenuBridgeHandled" not in CANVAS_INTERACTIONS_JS

    def test_context_menu_requests_include_actual_pointer_coordinates(self) -> None:
        assert "source: 'cxttap'" in CANVAS_INTERACTIONS_JS
        assert "source: 'contextmenu'" in CANVAS_INTERACTIONS_JS
        assert "clientX: e.clientX" in CANVAS_INTERACTIONS_JS
        assert "clientY: e.clientY" in CANVAS_INTERACTIONS_JS
        assert "var x = Number(d && d.clientX);" in CONTEXT_MENU_JS
        assert "var y = Number(d && d.clientY);" in CONTEXT_MENU_JS

    def test_contextmenu_fallback_prefers_rendered_bounds_before_center_distance(self) -> None:
        assert "node.renderedBoundingBox({ includeLabels: false, includeOverlays: false })" in CANVAS_INTERACTIONS_JS
        assert "var contains = rx >= box.x1 && rx <= box.x2 && ry >= box.y1 && ry <= box.y2;" in CANVAS_INTERACTIONS_JS
        assert "if (hitNode) {" in CANVAS_INTERACTIONS_JS
        assert "var nearest = null;" not in CANVAS_INTERACTIONS_JS

    def test_parent_drag_cannot_trigger_descendant_detach_path(self) -> None:
        assert "var owner = window._htContainerGestureOwner || null;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (owner && String(owner.nodeId) !== String(nodeId)) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (owner.isContainerNode && ownerIsAncestor) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "_htFinalizeDragNode(nodeId, true);" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_dragfree_is_null_safe_when_ownership_map_is_missing(self) -> None:
        assert "function _htGetPointerOwnership(nodeId) {" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "if (!ownershipMap || typeof ownershipMap !== 'object') return null;" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var ownership = _htGetPointerOwnership(nodeId);" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "var ownership = window._htContainerPointerOwnership[nodeId];" not in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_resolver_order_checks_origin_retention_before_fallback(self) -> None:
        resolve_detach = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "        function _htResolveDetachAwareDropParent(node, origin) {",
            "\n\n        function _htSnapBackNode(node) {",
        )

        assert resolve_detach.index("if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {") < resolve_detach.index("var fallbackParent = _htResolveDropParentIgnoring(node, originParentId);")

    def test_grab_handler_seeds_primary_selection_from_settled_state_after_normalization(self) -> None:
        grab_body = _between(
            CANVAS_CONTAINER_DRAG_EVENTS_JS,
            "        cy.on('grab', 'node', function(evt) {",
            "\n\n        cy.on('pointerdown', 'node', function(evt) {",
        )
        assert "window._htNormalizeSelectionForContainerDrag(node);" in grab_body
        assert "var selectedAtPointerdown = !!(" in grab_body
        assert "existingOwnership && existingOwnership.selectedAtPointerdown" in grab_body
        assert "|| (node.selected && node.selected())" in grab_body

    def test_dragfree_fallback_selection_state_for_reparent_validation(self) -> None:
        dragfree_body = _between(
            CANVAS_CONTAINER_DRAG_EVENTS_JS,
            "        cy.on('dragfree', 'node', function(evt) {",
            "\n        document.addEventListener('pointercancel'",
        )
        assert "var isSelectedForReparent = !!(" in dragfree_body
        assert "ownership && ownership.ownershipFrozen && ownership.selectedAtPointerdown" in dragfree_body
        assert "!ownership && origin && origin.wasSelected && dragDistance >= 5" in dragfree_body
        assert "|| (node.selected && node.selected() && dragDistance >= 5 && origin)" not in dragfree_body
        assert "node.selected && node.selected()" not in dragfree_body

    def test_contextmenu_target_prefers_depth_then_area_for_nested_nodes(self) -> None:
        contextmenu_body = _between(
            CANVAS_INTERACTIONS_JS,
            "            cy.nodes().forEach(function(node) {",
            "            if (hitNode) {",
        )
        assert "var depth = Number(node.ancestors" in contextmenu_body
        assert "var isDeeper = !hitNode ||" in contextmenu_body
        assert "var isSmallerAtSameDepth = !isDeeper && area < hitArea;" in contextmenu_body
        assert "if (isDeeper || isSmallerAtSameDepth)" in contextmenu_body

    def test_context_menu_coordinate_clamping_prevents_offscreen_positioning(self) -> None:
        assert "var viewportWidth = window.innerWidth || document.documentElement.clientWidth;" in CONTEXT_MENU_JS
        assert "var viewportHeight = window.innerHeight || document.documentElement.clientHeight;" in CONTEXT_MENU_JS
        assert "var menuWidth = menu.offsetWidth || 160;" in CONTEXT_MENU_JS
        assert "var menuHeight = menu.offsetHeight || 32;" in CONTEXT_MENU_JS
        assert "var clampedX = Math.max(0, Math.min(x, viewportWidth - menuWidth - 4));" in CONTEXT_MENU_JS
        assert "var clampedY = Math.max(0, Math.min(y, viewportHeight - menuHeight - 4));" in CONTEXT_MENU_JS
        assert "menu.style.left = clampedX + 'px';" in CONTEXT_MENU_JS
        assert "menu.style.top  = clampedY + 'px';" in CONTEXT_MENU_JS


class TestHt077CurrentHeadBugProofs:
    def test_pending_published_reparent_lock_blocks_resize_on_locked_selection(self) -> None:
        assert "selection_ids: _htSelectedNodeIds()" in CANVAS_CONTAINER_ACTIONS_JS

        resize_selection_guard_body = _between(
            CANVAS_RESIZE_JS,
            "    function _htResizeIsLocked(node) {",
            "\n\n    function _htResizePlaceHandle(direction, x, y) {",
        )

        assert "state.cy.$('node:selected')" in resize_selection_guard_body
        assert re.search(
            r"pending.*published.*reparent|selection_ids|selection.*lock",
            resize_selection_guard_body,
            re.I | re.S,
        ) is not None, "Expected resize selection gating to consult the pending published-reparent lock."

    def test_pending_published_reparent_lock_blocks_local_structural_reparent_on_locked_selection(self) -> None:
        assert "selection_ids: _htSelectedNodeIds()" in CANVAS_CONTAINER_ACTIONS_JS

        dragfree_body = _between(
            CANVAS_CONTAINER_DRAG_EVENTS_JS,
            "        cy.on('dragfree', 'node', function(evt) {",
            "\n        document.addEventListener('pointercancel'",
        )
        request_reparent_body = _between(
            CANVAS_CONTAINER_ACTIONS_JS,
            "        function _htRequestNodeReparent(node, spec) {",
            "\n\n        window._htRequestDetachToTopLevel = function(nodeId) {",
        )

        assert "_htNormalizeSelectionForContainerDrag(node);" in dragfree_body
        assert "_htRequestNodeReparent(node, {" in dragfree_body
        assert "_htCommitLocalReparent(node, spec);" in request_reparent_body

        dragfree_lock_check = re.search(
            r"(?:pending.*published.*reparent|selection_ids|selection.*lock)[\s\S]+_htRequestNodeReparent\(node, \{",
            dragfree_body,
            re.I,
        )
        request_lock_check = re.search(
            r"(?:pending.*published.*reparent|selection_ids|selection.*lock)[\s\S]+_htCommitLocalReparent\(node, spec\);",
            request_reparent_body,
            re.I,
        )

        assert dragfree_lock_check is not None or request_lock_check is not None, (
            "Expected the structural drag/reparent path to block local reparent while a pending "
            "published-reparent selection lock is active."
        )

    def test_remove_from_container_respects_data_draft_flag_before_api_reparent(self) -> None:
        assert _is_draft_data({"id": "single-child-1776457558", "draft": True}) is True

        request_reparent_body = _between(
            CANVAS_CONTAINER_ACTIONS_JS,
            "        function _htRequestNodeReparent(node, spec) {",
            "\n\n        window._htRequestDetachToTopLevel = function(nodeId) {",
        )

        assert re.search(r"node\.data\(['\"]draft['\"]\)|node\.hasClass\(['\"]draft['\"]\)", request_reparent_body) is not None
        assert "_htCommitLocalReparent(node, spec);" in request_reparent_body

    def test_context_menu_right_click_selects_target_before_write_actions_open(self) -> None:
        cxttap_body = _between(
            CANVAS_INTERACTIONS_JS,
            "        cy.on('cxttap', 'node', function(evt) {",
            "\n\n        container.addEventListener('contextmenu', function(e) {",
        )
        assert re.search(
            r"if \(_htNodeIsLocked\(node\)\) \{\s*emitNodeSelected\(node\);\s*return;\s*\}\s*emitNodeSelected\(node\);",
            cxttap_body,
            re.S,
        ) is not None

        contextmenu_hit_body = _between(
            CANVAS_INTERACTIONS_JS,
            "            if (hitNode) {",
            "\n            // No nearest-center fallback: write actions must only target nodes whose",
        )
        assert "emitNodeSelected(hitNode);" in contextmenu_hit_body
        assert contextmenu_hit_body.index("emitNodeSelected(hitNode);") < contextmenu_hit_body.index(
            "dispatchContextMenuRequest({"
        )

    def test_convert_to_container_schedules_persistence_when_it_mutates_local_canvas_state(self) -> None:
        convert_body = _between(
            CANVAS_CONTAINER_EVENTS_JS,
            "        document.addEventListener('ht:node-convert-container', function(evt) {",
            "\n\n        function _htStripClasses(classes) {",
        )

        assert "node.addClass('container');" in convert_body
        assert re.search(r"scheduleAutosave\(800\)|_htFlushAutosave\(", convert_body) is not None

    def test_readonly_dom_contextmenu_suppresses_browser_menu_before_returning(self) -> None:
        contextmenu_body = _between(
            CANVAS_INTERACTIONS_JS,
            "        container.addEventListener('contextmenu', function(e) {",
            "\n\n        container.addEventListener('dragover', function(e) { e.preventDefault(); });",
        )

        assert "e.preventDefault();" in contextmenu_body
        assert contextmenu_body.index("e.preventDefault();") < contextmenu_body.index(
            "if (window.HT_READONLY) return;"
        )


class TestHt075GhostStyles:
    def test_canvas_theme_styles_include_ghost_selector(self) -> None:
        from src.ui.components.canvas_styles import build_theme_style_json

        styles = json.loads(build_theme_style_json("dark"))
        ghost_style = next((entry for entry in styles if entry.get("selector") == "node.ghost"), None)

        assert isinstance(ghost_style, dict)
        style_map = ghost_style.get("style")
        assert isinstance(style_map, dict)
        assert style_map.get("border-style") == "dashed"
        assert "window._htUndoStack" not in CANVAS_INTERACTIONS_JS

    def test_unconvert_requires_saved_diagram_and_inflight_guard(self) -> None:
        assert "Open a topology before converting containers." in CANVAS_CONTAINER_EVENTS_JS
        assert "Save in progress — wait a moment and try again." in CANVAS_CONTAINER_EVENTS_JS
        assert "window.cancelAutosave" in CANVAS_CONTAINER_EVENTS_JS

    def test_unconvert_uses_rfc_confirmation_copy(self) -> None:
        assert "Convert container to node?" in CANVAS_CONTAINER_EVENTS_JS
        assert "Devices stay in inventory. This removes them from this topology version." in CANVAS_CONTAINER_EVENTS_JS
        assert "Remove from Version" in CANVAS_CONTAINER_EVENTS_JS

    def test_unconvert_patches_diagram_before_live_mutation_and_refreshes_stencils(self) -> None:
        assert "fetch('/api/topologies/' + window._htTopologyId + '/personal-draft'" in CANVAS_CONTAINER_EVENTS_JS
        assert "_htApplyUnconvertPlan(plan);" in CANVAS_CONTAINER_EVENTS_JS
        assert "ht:stencil-refresh" in CANVAS_CONTAINER_EVENTS_JS
        assert "Convert to node failed — this topology version was not changed." in CANVAS_CONTAINER_EVENTS_JS

    def test_unconvert_does_not_schedule_second_autosave(self) -> None:
        unconvert_section = CANVAS_CONTAINER_EVENTS_JS.split(
            "document.addEventListener('ht:node-unconvert-container'",
            1,
        )[1]
        assert "window.scheduleAutosave(800);" not in unconvert_section

    def test_history_api_returns_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_layouts in topology_layout_api fetches and returns history entries."""
        from src.ui.components import topology_layout_api

        class _FakeResp:
            status_code = 200

            def json(self) -> dict[str, object]:
                return {
                    "items": [
                        {"id": "history-id", "snapshot_name": "Version 1"},
                    ]
                }

        class _FakeClient:
            def __init__(self) -> None:
                self.calls: list[str] = []

            async def __aenter__(self) -> "_FakeClient":
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

            async def get(self, url: str, **kwargs: object) -> "_FakeResp":
                self.calls.append("get")
                return _FakeResp()

        fake = _FakeClient()
        monkeypatch.setattr(
            topology_layout_api.httpx, "AsyncClient", lambda: fake
        )

        result = asyncio.run(topology_layout_api.get_layouts("token", lambda: fake, topology_id="topo-1"))
        assert len(result) == 1
        assert result[0]["snapshot_name"] == "Version 1"

    def test_layout_bar_click_handlers_do_not_detach_tasks(self) -> None:
        from src.ui.components import topology_layout_bar

        source = inspect.getsource(topology_layout_bar.render_layout_bar)
        assert "asyncio.ensure_future" not in source


class TestCanvasAutosaveTemplate:
    """Regression tests for canvas autosave JS (BUG-1101-03)."""

    def test_flush_autosave_function_defined(self) -> None:
        assert "window._htFlushAutosave = function()" in _CANVAS_INIT_JS
        assert "window.scheduleAutosave = function(delayMs)" in _CANVAS_INIT_JS

    def test_dragfree_uses_shared_autosave_scheduler(self) -> None:
        assert "window.scheduleAutosave(800);" in _CANVAS_INIT_JS
        assert "window._htAutosaveTimer" in _CANVAS_INIT_JS
        assert "window._htAutosaveTimer = setTimeout(window._htFlushAutosave, 800);" not in _CANVAS_INIT_JS

    def test_beforeunload_listener_handles_large_pending_payloads(self) -> None:
        assert "window.addEventListener('beforeunload'" in _CANVAS_INIT_JS
        assert "65536" in _CANVAS_INIT_JS
        assert "function _confirmAutosaveUnload(event)" in _CANVAS_INIT_JS
        assert "return _confirmAutosaveUnload(event);" in _CANVAS_INIT_JS
        assert "_sendUnloadAutosave(request);" in _CANVAS_INIT_JS

    def test_keepalive_is_scoped_to_unload_only(self) -> None:
        assert "function _dispatchAutosaveRequest(request, useKeepalive)" in _CANVAS_INIT_JS
        assert "keepalive: !!useKeepalive" in _CANVAS_INIT_JS
        assert "_dispatchAutosaveRequest(request, false)" in _CANVAS_INIT_JS
        assert "_dispatchAutosaveRequest(request, true)" in _CANVAS_INIT_JS

    def test_autosave_serializes_concurrent_flushes(self) -> None:
        assert "window._htAutosaveInFlight" in _CANVAS_INIT_JS
        assert "if (window._htAutosaveInFlight)" in _CANVAS_INIT_JS
        assert "window._htAutosavePending = true;" in _CANVAS_INIT_JS

    def test_autosave_replays_one_pending_flush_after_current_save(self) -> None:
        assert "if (window._htAutosavePending) {" in _CANVAS_INIT_JS
        assert "window._htAutosavePending = false;" in _CANVAS_INIT_JS
        assert "window._htFlushAutosave();" in _CANVAS_INIT_JS

    def test_conflict_handling_is_actionable_and_suspends_autosave(self) -> None:
        assert "Your personal draft was modified elsewhere \\u2014 reload to sync" in _CANVAS_INIT_JS
        assert "Reload" in _CANVAS_INIT_JS
        assert "window.location.reload()" in _CANVAS_INIT_JS
        assert "window._htAutosaveSuspended = true;" in _CANVAS_INIT_JS

    def test_retry_backoff_and_failure_notice_are_present(self) -> None:
        assert "[1000, 2000, 4000]" in _CANVAS_INIT_JS
        assert "Autosave failed. Your changes may not be saved." in _CANVAS_INIT_JS
        assert "Retry" in _CANVAS_INIT_JS

    def test_retry_backoff_tracks_active_request_state_for_unload_safety(self) -> None:
        assert "window._htAutosaveRequestInFlight = true;" in _CANVAS_INIT_JS
        assert "window._htAutosaveRequestInFlight = false;" in _CANVAS_INIT_JS
        assert "window._htAutosaveRetryTimer" in _CANVAS_INIT_JS
        assert "_sendUnloadAutosave(request);" in _CANVAS_INIT_JS

    def test_beforeunload_prompts_instead_of_sending_when_request_active(self) -> None:
        assert "if (window._htAutosaveRequestInFlight) {" in _CANVAS_INIT_JS
        assert "return HT_AUTOSAVE_UNLOAD_MESSAGE;" in _CANVAS_INIT_JS

    def test_beforeunload_respects_leave_guard_bypass(self) -> None:
        assert "window._htLeaveGuardBypassOnce" in _CANVAS_INIT_JS
        assert "if (window._htLeaveGuardBypassOnce) return;" in _CANVAS_INIT_JS

    def test_success_path_keeps_request_active_until_completion(self) -> None:
        match = re.search(
            r"_dispatchAutosaveRequest\(request, false\)\.then\(function\(r\) \{(?P<response_block>.*?)\}\)\s*"
            r"\.then\(function\(data\) \{(?P<success_block>.*?)\}\)\s*"
            r"\.catch",
            _CANVAS_INIT_JS,
            re.S,
        )
        assert match is not None
        response_block = match.group("response_block")
        success_block = match.group("success_block")
        assert "window._htAutosaveRequestInFlight = false;" not in response_block
        assert "window._htAutosaveRequestInFlight = false;" not in success_block
        assert success_block.index("window._htDraftVersion = data.version;") < success_block.index(
            "_finishAutosave(true);"
        )
        assert success_block.index("window._htAutosaveDirty = false;") < success_block.index(
            "_finishAutosave(true);"
        )

    def test_success_path_syncs_unsaved_draft_flag_from_server_response(self) -> None:
        assert "Object.prototype.hasOwnProperty.call(data, 'has_unsaved_changes')" in _CANVAS_INIT_JS
        assert "window._htSetDraftStatus(!!data.has_unsaved_changes);" in _CANVAS_INIT_JS

    def test_canvas_js_files_stay_under_line_budget(self) -> None:
        assert _line_count("src/ui/components/canvas_js.py") <= 250
        assert _line_count("src/ui/components/canvas_js_utils.py") <= 250

    def test_canvas_event_bundle_uses_shared_scheduler(self) -> None:
        assert "window.scheduleAutosave(800);" in _CANVAS_EVENTS_JS
        assert "clearTimeout(window._htAutosaveTimer)" not in _CANVAS_EVENTS_JS

    def test_palette_drop_guards_draft_id_factory(self) -> None:
        assert re.search(
            r"window\._htDraftId\s*=\s*window\._htDraftId\s*\|\|\s*function\(\)\s*\{\s*"
            r"return 'draft-' \+ crypto\.randomUUID\(\);\s*\};\s*"
            r"var draftId = window\._htDraftId\(\);",
            _CANVAS_EVENTS_JS,
        ) is not None

    def test_container_events_use_shared_scheduler(self) -> None:
        assert "window.scheduleAutosave(800);" in CANVAS_CONTAINER_EVENTS_JS
        assert "clearTimeout(window._htAutosaveTimer)" not in CANVAS_CONTAINER_EVENTS_JS

    def test_compound_resize_no_longer_repositions_children_during_drag(self) -> None:
        assert "child.position({" not in CANVAS_RESIZE_JS_PART_B
        assert "_htResizeCompoundMin(node, compoundState.minPadding)" in CANVAS_RESIZE_JS_PART_B
        assert "CANVAS_RESIZE_JS_PART_C" in inspect.getsource(__import__('src.ui.components.canvas_js_resize', fromlist=['CANVAS_RESIZE_JS']))

    def test_compound_resize_floor_uses_live_child_bounds_plus_padding(self) -> None:
        assert "var childBox = children.boundingBox({ includeLabels: false, includeOverlays: false });" in CANVAS_RESIZE_JS
        assert "minWidth = Math.max(minWidth, childWidth + padding.left + padding.right);" in CANVAS_RESIZE_JS
        assert "minHeight = Math.max(minHeight, childHeight + padding.top + padding.bottom);" in CANVAS_RESIZE_JS
        assert "var liveMin = _htResizeCompoundMin(node, compoundState.minPadding);" in CANVAS_RESIZE_JS_PART_B
        assert "width: Math.max(calc.width, liveMin.width)," in CANVAS_RESIZE_JS_PART_B
        assert "height: Math.max(calc.height, liveMin.height)," in CANVAS_RESIZE_JS_PART_B

    def test_canvas_resize_bundle_keeps_single_iife_and_valid_final_box_sequence(self) -> None:
        assert CANVAS_RESIZE_JS.count("})();") == 1
        assert "var finalBox = node.boundingBox({ includeLabels: false, includeOverlays: false });" in CANVAS_RESIZE_JS_PART_B
        assert "var finalWidth = _htResizeParsePx(finalBox ? (finalBox.w || (finalBox.x2 - finalBox.x1)) : nextCalc.width, nextCalc.width);" in CANVAS_RESIZE_JS_PART_B
        assert "var finalHeight = _htResizeParsePx(finalBox ? (finalBox.h || (finalBox.y2 - finalBox.y1)) : nextCalc.height, nextCalc.height);" in CANVAS_RESIZE_JS_PART_B

    def test_canvas_styles_render_container_watermarks_from_device_type_icons(self) -> None:
        from src.ui.components.canvas_styles import build_theme_style_json

        styles = json.loads(build_theme_style_json("dark"))
        entry = next(
            (row for row in styles if row.get("selector") == ':parent[device_type = "Server"]'),
            None,
        )
        assert isinstance(entry, dict)
        style_map = entry.get("style")
        assert isinstance(style_map, dict)
        assert str(style_map.get("background-image", "")).startswith("data:image/svg+xml")
        assert style_map.get("background-image-opacity") == 0.15
        assert style_map.get("background-fit") == "contain"

    def test_container_watermark_uri_uses_material_icon_svg_contract(self) -> None:
        icon_name = DEVICE_TYPE_ICONS[DeviceType.Server]
        uri = _container_watermark_uri(icon_name, "#123456")

        assert uri.startswith("data:image/svg+xml;utf8,")
        svg = unquote(uri.split(",", 1)[1])
        assert "font-family='Material Icons'" in svg
        assert "fill='#123456'" in svg
        assert "fill-opacity='0.15'" in svg
        assert f">{icon_name}</text>" in svg


class TestHt077UndoBridge:
    def test_handle_canvas_action_request_reparents_via_patch_and_graph_patch(self) -> None:
        device_id = "3db93d18-8c2f-4f1e-a6e3-9f7d3f0d1221"
        captured: dict[str, object] = {}
        api_calls: list[tuple[str, str, dict[str, object] | None]] = []

        async def resolve_success(direction: str, entry_id: str, result: dict[str, object]) -> None:
            captured["success"] = (direction, entry_id, result)

        async def resolve_failure(direction: str, entry_id: str, message: str) -> None:
            captured["failure"] = (direction, entry_id, message)

        async def call_api(method: str, path: str, payload: dict[str, object] | None) -> _FakeResponse:
            api_calls.append((method, path, payload))
            return _FakeResponse(200, {"id": device_id, "version": 8})

        asyncio.run(handle_canvas_action_request(
            args={
                "entry_id": "entry-1",
                "action": {
                    "type": "reparent_device",
                    "payload": {
                        "device_id": device_id,
                        "from_parent_id": "outer-id",
                        "to_parent_id": None,
                        "from_rendered_position": {"x": 420.0, "y": 310.0},
                        "to_rendered_position": {"x": 612.0, "y": 344.0},
                        "version_cursor": 7,
                        "label": "Remove from container",
                    },
                },
            },
            can_write=True,
            token="token",
            resolve_success=resolve_success,
            resolve_failure=resolve_failure,
            call_api=call_api,
        ))

        assert "failure" not in captured
        assert api_calls == [
            ("PATCH", f"/api/devices/{device_id}", {"parent_id": None, "version": 7})
        ]
        direction, entry_id, result = captured["success"]
        assert direction == "forward"
        assert entry_id == "entry-1"
        assert result["entry"]["type"] == "reparent_device"
        assert result["entry"]["forward"]["op"] == "reparent_device"
        assert result["entry"]["reverse"]["op"] == "reparent_device"
        assert result["graph_patch"] == {
            "op": "reparent_node",
            "node_id": device_id,
            "parent_id": None,
            "rendered_position": {"x": 612.0, "y": 344.0},
            "version": 8,
        }

    def test_handle_canvas_undo_request_restores_parent_via_reparent_contract(self) -> None:
        device_id = "3db93d18-8c2f-4f1e-a6e3-9f7d3f0d1221"
        captured: dict[str, object] = {}
        api_calls: list[tuple[str, str, dict[str, object] | None]] = []

        async def resolve_success(direction: str, entry_id: str, result: dict[str, object]) -> None:
            captured["success"] = (direction, entry_id, result)

        async def resolve_failure(direction: str, entry_id: str, message: str) -> None:
            captured["failure"] = (direction, entry_id, message)

        async def call_api(method: str, path: str, payload: dict[str, object] | None) -> _FakeResponse:
            api_calls.append((method, path, payload))
            return _FakeResponse(200, {"id": device_id, "version": 9})

        asyncio.run(handle_canvas_undo_request(
            args={
                "direction": "undo",
                "entry": {
                    "entry_id": "entry-undo",
                    "reverse": {
                        "op": "reparent_device",
                        "payload": {
                            "device_id": device_id,
                            "from_parent_id": "outer-id",
                            "to_parent_id": None,
                            "from_rendered_position": {"x": 420.0, "y": 310.0},
                            "to_rendered_position": {"x": 612.0, "y": 344.0},
                            "version_cursor": 8,
                            "label": "Remove from container",
                        },
                    },
                },
            },
            can_write=True,
            token="token",
            resolve_success=resolve_success,
            resolve_failure=resolve_failure,
            call_api=call_api,
        ))

        assert "failure" not in captured
        assert api_calls == [
            ("PATCH", f"/api/devices/{device_id}", {"parent_id": "outer-id", "version": 8})
        ]
        direction, entry_id, result = captured["success"]
        assert direction == "undo"
        assert entry_id == "entry-undo"
        assert result["entry_patch"]["forward"]["op"] == "reparent_device"
        assert result["entry_patch"]["reverse"]["op"] == "reparent_device"
        assert result["entry_patch"]["forward"]["payload"]["version_cursor"] == 9
        assert result["graph_patch"] == {
            "op": "reparent_node",
            "node_id": device_id,
            "parent_id": "outer-id",
            "rendered_position": {"x": 420.0, "y": 310.0},
            "version": 9,
        }

    def test_handle_canvas_action_request_converges_reparent_conflict_when_target_already_matches(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.canvas_undo_action_device_support as action_support_module

        device_id = "3db93d18-8c2f-4f1e-a6e3-9f7d3f0d1221"
        captured: dict[str, object] = {}
        api_calls: list[tuple[str, str, dict[str, object] | None]] = []

        async def fake_fetch_current_device_version(
            _token: str,
            *,
            device_id: object,
            fallback: int,
        ) -> int:
            _ = device_id
            return fallback

        async def resolve_success(direction: str, entry_id: str, result: dict[str, object]) -> None:
            captured["success"] = (direction, entry_id, result)

        async def resolve_failure(direction: str, entry_id: str, message: str) -> None:
            captured["failure"] = (direction, entry_id, message)

        async def call_api(method: str, path: str, payload: dict[str, object] | None) -> _FakeResponse:
            api_calls.append((method, path, payload))
            if method == "PATCH":
                return _FakeResponse(409, {"detail": "Conflict"})
            if method == "GET":
                return _FakeResponse(200, {"id": device_id, "parent_id": None, "version": 8})
            raise AssertionError(f"Unexpected API call: {(method, path, payload)}")

        monkeypatch.setattr(
            action_support_module,
            "fetch_current_device_version",
            fake_fetch_current_device_version,
        )

        asyncio.run(
            handle_canvas_action_request(
                args={
                    "entry_id": "entry-conflict",
                    "action": {
                        "type": "reparent_device",
                        "payload": {
                            "device_id": device_id,
                            "from_parent_id": "outer-id",
                            "to_parent_id": None,
                            "from_rendered_position": {"x": 420.0, "y": 310.0},
                            "to_rendered_position": {"x": 612.0, "y": 344.0},
                            "version_cursor": 7,
                            "label": "Remove from container",
                        },
                    },
                },
                can_write=True,
                token="token",
                resolve_success=resolve_success,
                resolve_failure=resolve_failure,
                call_api=call_api,
            )
        )

        assert "failure" not in captured
        assert api_calls == [
            ("PATCH", f"/api/devices/{device_id}", {"parent_id": None, "version": 7}),
            ("GET", f"/api/devices/{device_id}", None),
        ]

        direction, entry_id, result = captured["success"]
        assert direction == "forward"
        assert entry_id == "entry-conflict"
        assert result["entry"]["forward"]["payload"]["version_cursor"] == 8
        assert result["graph_patch"]["version"] == 8

    def test_handle_canvas_undo_request_retries_reparent_once_after_conflict(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.canvas_undo_operation_device_support as operation_support_module

        device_id = "3db93d18-8c2f-4f1e-a6e3-9f7d3f0d1221"
        captured: dict[str, object] = {}
        api_calls: list[tuple[str, str, dict[str, object] | None]] = []
        patch_attempts = 0

        async def fake_fetch_current_device_version(
            _token: str,
            *,
            device_id: object,
            fallback: int,
        ) -> int:
            _ = device_id
            return fallback

        async def resolve_success(direction: str, entry_id: str, result: dict[str, object]) -> None:
            captured["success"] = (direction, entry_id, result)

        async def resolve_failure(direction: str, entry_id: str, message: str) -> None:
            captured["failure"] = (direction, entry_id, message)

        async def call_api(method: str, path: str, payload: dict[str, object] | None) -> _FakeResponse:
            nonlocal patch_attempts
            api_calls.append((method, path, payload))
            if method == "PATCH":
                patch_attempts += 1
                if patch_attempts == 1:
                    return _FakeResponse(409, {"detail": "Conflict"})
                return _FakeResponse(200, {"id": device_id, "version": 10})
            if method == "GET":
                return _FakeResponse(200, {"id": device_id, "parent_id": None, "version": 9})
            raise AssertionError(f"Unexpected API call: {(method, path, payload)}")

        monkeypatch.setattr(
            operation_support_module,
            "fetch_current_device_version",
            fake_fetch_current_device_version,
        )

        asyncio.run(
            handle_canvas_undo_request(
                args={
                    "direction": "undo",
                    "entry": {
                        "entry_id": "entry-retry",
                        "reverse": {
                            "op": "reparent_device",
                            "payload": {
                                "device_id": device_id,
                                "from_parent_id": "outer-id",
                                "to_parent_id": None,
                                "from_rendered_position": {"x": 420.0, "y": 310.0},
                                "to_rendered_position": {"x": 612.0, "y": 344.0},
                                "version_cursor": 8,
                                "label": "Remove from container",
                            },
                        },
                    },
                },
                can_write=True,
                token="token",
                resolve_success=resolve_success,
                resolve_failure=resolve_failure,
                call_api=call_api,
            )
        )

        assert "failure" not in captured
        assert api_calls == [
            ("PATCH", f"/api/devices/{device_id}", {"parent_id": "outer-id", "version": 8}),
            ("GET", f"/api/devices/{device_id}", None),
            ("PATCH", f"/api/devices/{device_id}", {"parent_id": "outer-id", "version": 9}),
        ]

        direction, entry_id, result = captured["success"]
        assert direction == "undo"
        assert entry_id == "entry-retry"
        assert result["entry_patch"]["forward"]["payload"]["version_cursor"] == 10
        assert result["graph_patch"]["version"] == 10

    def test_notify_helper_supports_actionable_toasts(self) -> None:
        assert "window._htNotify = function(message, color, opts)" in CANVAS_DRAFT_JS
        assert "options.actions" in CANVAS_DRAFT_JS

    def test_draft_publish_chains_final_flush_after_promotion_completion(self) -> None:
        assert "return _htPromoteConnections(newId).then(function() {" in CANVAS_DRAFT_PUBLISH_JS
        assert (
            "_htPromoteConnections(newId);\n\n            if (window._htFlushAutosave) window._htFlushAutosave();"
            not in CANVAS_DRAFT_PUBLISH_JS
        )

    def test_draft_publish_prunes_stale_duplicate_edges_after_promotion_settlement(self) -> None:
        match = re.search(
            r"return Promise\.all\(promotions\)\.then\(function\(\) \{(?P<cleanup>.*?)\}\);",
            CANVAS_DRAFT_PUBLISH_JS,
            re.S,
        )
        assert match is not None
        assert "_htPrunePromotedDraftEdges(cy, node);" in match.group("cleanup")

    def test_draft_publish_uses_event_bridge_for_stencil_inventory_update(self) -> None:
        assert "ht:stencil-device-published" in CANVAS_DRAFT_PUBLISH_JS
        assert "window.htStencilUpsertPublishedDevice" not in CANVAS_DRAFT_PUBLISH_JS

    def test_device_detail_draft_uses_shared_scheduler(self) -> None:
        from src.ui.components import device_detail_draft

        source = inspect.getsource(device_detail_draft.show_draft_panel)
        assert "window.scheduleAutosave(800);" in source
        assert "window._htAutosaveTimer" not in source

    def test_device_detail_draft_uses_shared_panel_visibility_contract(self) -> None:
        from src.ui.components import device_detail_draft

        source = inspect.getsource(device_detail_draft.show_draft_panel)
        assert 'build_panel_visibility_js("device-detail-panel", False)' in source
        assert 'build_panel_visibility_js("device-detail-panel", True)' in source
        assert ".style.display" not in source
