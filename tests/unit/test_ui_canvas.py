"""Unit tests for Cytoscape canvas initialization safeguards."""
import asyncio
import json
import inspect
from pathlib import Path
import re

import pytest

from src.ui.components.canvas import render_canvas
from src.ui.components.canvas_container_events import CANVAS_CONTAINER_EVENTS_JS
from src.ui.components.canvas_draft import CANVAS_DRAFT_JS
from src.ui.components.canvas_draft_events import CANVAS_DRAFT_EVENTS_JS
from src.ui.components.canvas_draft_publish import CANVAS_DRAFT_PUBLISH_JS
from src.ui.components.canvas_js_interactions import CANVAS_INTERACTIONS_JS
from src.ui.components.canvas_js import CANVAS_INIT_JS_TEMPLATE as _CANVAS_INIT_JS_TEMPLATE
from src.ui.components.canvas_js_resize import CANVAS_RESIZE_JS
from src.ui.components.canvas_js_helpers import CANVAS_HELPERS_JS
from src.ui.components.canvas_tooltip import _CANVAS_TOOLTIP_JS

# _CANVAS_INIT_JS was removed (dead code); tests on template content are equivalent
_CANVAS_INIT_JS = _CANVAS_INIT_JS_TEMPLATE
from src.ui.components.canvas_events import _CANVAS_EVENTS_JS
from src.ui.components.canvas_context_menu import CONTEXT_MENU_JS
from src.ui.pages import topology
from src.ui.pages.login import login_page
from src.ui.pages.topology import topology_page


def _line_count(path: str) -> int:
    return len(Path(path).read_text().splitlines())


def _between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


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

    def test_topology_row_stretches_canvas_column(self) -> None:
        source = inspect.getsource(topology_page)
        assert "flex-wrap: nowrap;" in source
        assert "align-items: stretch;" in source

    def test_topology_renders_device_panel_and_moves_layout_to_header(self) -> None:
        source = inspect.getsource(topology_page)
        assert "render_detail_panel(token, user_role)" in source
        assert "_render_header_actions" in source
        assert "render_palette()" in source
        assert "render_network_filter_panel(network_summaries)" in source
        assert "inject_network_overlay()" in source

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

    def test_association_mode_supports_context_menu_start(self) -> None:
        assert "ht:association-source" in _CANVAS_EVENTS_JS
        assert "Association source selected." in _CANVAS_EVENTS_JS
        assert "_createAssociation(sourceId, targetId);" in _CANVAS_EVENTS_JS

    def test_node_delete_surfaces_api_error_feedback(self) -> None:
        assert "Delete device '" in _CANVAS_EVENTS_JS
        assert "This cannot be undone." in _CANVAS_EVENTS_JS
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

    def test_tag_detach_requires_confirmation_dialog(self) -> None:
        from src.ui.components import device_detail_tags_section

        source = inspect.getsource(device_detail_tags_section.render_tags_section)
        assert "Remove tag '" in source
        assert "lambda dlg=confirm_dlg: dlg.open()" in source

    def test_login_password_input_submits_on_enter(self) -> None:
        source = inspect.getsource(login_page)
        assert '.on("keydown.enter", handle_login)' in source

    def test_topology_accepts_device_id_query_param(self) -> None:
        source = inspect.getsource(topology_page)
        assert "device_id: str = \"\"" in source
        assert "if device_id:" in source

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

    def test_published_reparent_uses_retry_helper_and_conflict_copy(self) -> None:
        assert "_htAttemptReparent(" in CANVAS_CONTAINER_EVENTS_JS
        assert (
            "Reparent failed — the device was modified by another user. Your change was not saved."
            in CANVAS_CONTAINER_EVENTS_JS
        )

    def test_draft_reparent_stays_layout_local(self) -> None:
        assert "window._htIsDraft && window._htIsDraft(nodeId)" in CANVAS_CONTAINER_EVENTS_JS
        assert "node.move({ parent: targetParent });" in CANVAS_CONTAINER_EVENTS_JS

    def test_reparent_snapback_tracks_drag_origin(self) -> None:
        assert "_htContainerDragOrigin" in CANVAS_CONTAINER_EVENTS_JS
        assert "_htSnapBackNode(" in CANVAS_CONTAINER_EVENTS_JS

    def test_canvas_drag_undo_is_batched_on_dragstart_dragend(self) -> None:
        assert "cy.on('dragstart', 'node'" in CANVAS_INTERACTIONS_JS
        assert "cy.on('dragend', 'node'" in CANVAS_INTERACTIONS_JS
        assert "window._htBeginMoveGesture" in CANVAS_INTERACTIONS_JS
        assert "window._htCommitMoveGesture" in CANVAS_INTERACTIONS_JS


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

    def test_device_detail_draft_uses_shared_scheduler(self) -> None:
        from src.ui.components import device_detail_draft

        source = inspect.getsource(device_detail_draft.show_draft_panel)
        assert "window.scheduleAutosave(800);" in source
        assert "window._htAutosaveTimer" not in source
