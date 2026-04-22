"""Unit tests for canvas_js view-mode changes (HT-048).

Validates that canvas_js.py defers event handler wiring and sets
view-only Cytoscape options after init, and that canvas_events.py
mutation handlers are guarded by HT_READONLY.
"""
from src.ui.components.canvas_js_interactions import CANVAS_INTERACTIONS_JS
from src.ui.components.canvas_events import _CANVAS_EVENTS_JS
from src.ui.components.canvas_js import CANVAS_INIT_JS_TEMPLATE


def _between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


class TestCanvasJsViewModeDefaults:
    """After cy init, view-only interaction flags must be set."""

    def test_autoungrabify_true_after_init(self) -> None:
        # After window._cy = cy; the script must set autoungrabify(true)
        assert "cy.autoungrabify(true)" in CANVAS_INIT_JS_TEMPLATE

    def test_autounselectify_not_set_after_init(self) -> None:
        # autounselectify(true) must NOT be set: it globally locks selectable:false
        # on all nodes, causing Ctrl+A / Escape shortcuts to silently no-op (BUG-001).
        assert "cy.autounselectify(true)" not in CANVAS_INIT_JS_TEMPLATE

    def test_box_selection_disabled_after_init(self) -> None:
        assert "cy.boxSelectionEnabled(false)" in CANVAS_INIT_JS_TEMPLATE

    def test_native_contextmenu_fallback_registered(self) -> None:
        assert "container.addEventListener('contextmenu'" in CANVAS_INIT_JS_TEMPLATE

    def test_contextmenu_fallback_dispatches_custom_menu_event(self) -> None:
        assert "ht:context-menu-request" in CANVAS_INIT_JS_TEMPLATE

    def test_contextmenu_dedup_uses_flag_bridge_instead_of_timestamp_window(self) -> None:
        assert "function _htDedupContextMenuRequest(id, eventId)" in CANVAS_INIT_JS_TEMPLATE
        assert "window._htCtxMenuRequestKeys" in CANVAS_INIT_JS_TEMPLATE
        assert "if (_htDedupContextMenuRequest(id, eventId)) return;" in CANVAS_INIT_JS_TEMPLATE
        assert "window.setTimeout(function() { window._htCtxMenuBridgeHandled = false; }, 50);" not in CANVAS_INIT_JS_TEMPLATE
        assert "_htCtxMenuBridgeHandled" not in CANVAS_INIT_JS_TEMPLATE
        assert "_htLastCtxMenuTime" not in CANVAS_INIT_JS_TEMPLATE

    def test_contextmenu_bridge_helper_guards_then_dispatches(self) -> None:
        assert "function _htDedupContextMenuRequest(id, eventId)" in CANVAS_INTERACTIONS_JS
        assert "var key = String(id) + ':' + String(eventId);" in CANVAS_INTERACTIONS_JS
        
        helper = _between(
            CANVAS_INTERACTIONS_JS,
            "        function dispatchContextMenuRequest(detail) {",
            "\n\n        cy.on('tap', 'node', function(evt) {",
        )
        dedup_call_idx = helper.index("if (_htDedupContextMenuRequest(id, eventId)) return;")
        dispatch_idx = helper.index(
            "document.dispatchEvent(new CustomEvent('ht:context-menu-request', { detail: detail }));"
        )

        assert dedup_call_idx < dispatch_idx

    def test_contextmenu_handlers_route_through_bridge_helper_only(self) -> None:
        cxttap_handler = _between(
            CANVAS_INTERACTIONS_JS,
            "        cy.on('cxttap', 'node', function(evt) {",
            "\n\n        container.addEventListener('contextmenu', function(e) {",
        )
        native_handler = _between(
            CANVAS_INTERACTIONS_JS,
            "        container.addEventListener('contextmenu', function(e) {",
            "\n\n        container.addEventListener('dragover', function(e) { e.preventDefault(); });",
        )

        assert "id: node.id()," in cxttap_handler
        assert "data: node.data()," in cxttap_handler
        assert "source: 'cxttap'" in cxttap_handler
        assert "document.dispatchEvent(new CustomEvent('ht:context-menu-request'" not in cxttap_handler
        assert "_htCtxMenuBridgeHandled = true" not in cxttap_handler

        assert "id: hitNode.id()," in native_handler
        assert "data: hitNode.data()," in native_handler
        assert "source: 'contextmenu'" in native_handler
        assert "document.dispatchEvent(new CustomEvent('ht:context-menu-request'" not in native_handler
        assert "_htCtxMenuBridgeHandled = true" not in native_handler
        assert "_htCtxMenuBridgeHandled" not in native_handler


class TestCanvasJsDeferredEventWiring:
    """Event handlers must NOT be eagerly wired. They should be deferred."""

    def test_device_shapes_stored_for_deferred_wiring(self) -> None:
        assert "window._htDeviceShapes = deviceShapes" in CANVAS_INIT_JS_TEMPLATE

    def test_no_eager_init_event_handlers_call(self) -> None:
        # The old pattern: `if (!window.HT_READONLY) { window._htInitEventHandlers(...) }`
        # should be gone from the first init block (line ~103)
        # We check that the pattern with HT_READONLY + _htInitEventHandlers does NOT appear
        # in the init section before the node-tap handler
        init_section = CANVAS_INIT_JS_TEMPLATE.split("cy.on('tap', 'node'")[0]
        assert "window._htInitEventHandlers(deviceShapes" not in init_section

    def test_edit_mode_uses_single_node_tap_dispatch_path(self) -> None:
        assert "cy.on('tap', 'node'" not in _CANVAS_EVENTS_JS
        assert "ht:association-target" in _CANVAS_EVENTS_JS
        assert "ht:association-target" in CANVAS_INIT_JS_TEMPLATE


class TestCanvasJsAutosaveGuard:
    """_htFlushAutosave must no-op when HT_READONLY is true."""

    def test_flush_autosave_has_readonly_guard(self) -> None:
        assert "if (window.HT_READONLY) return;" in CANVAS_INIT_JS_TEMPLATE


class TestCanvasEventsReadonlyGuards:
    """Mutation handlers in canvas_events must guard with HT_READONLY."""

    def test_association_target_handler_has_readonly_guard(self) -> None:
        idx = _CANVAS_EVENTS_JS.index("ht:association-target")
        handler_start = _CANVAS_EVENTS_JS[idx:]
        assert "if (window.HT_READONLY) return;" in handler_start[:200]

    def test_cxttap_edge_handler_has_readonly_guard(self) -> None:
        idx = _CANVAS_EVENTS_JS.index("cy.on('cxttap', 'edge',")
        handler_start = _CANVAS_EVENTS_JS[idx:]
        assert "if (window.HT_READONLY) return;" in handler_start[:200]

    def test_palette_drop_has_readonly_guard(self) -> None:
        idx = _CANVAS_EVENTS_JS.index("ht:palette-drop")
        handler_start = _CANVAS_EVENTS_JS[idx:]
        assert "if (window.HT_READONLY) return;" in handler_start[:200]

    def test_node_delete_has_readonly_guard(self) -> None:
        idx = _CANVAS_EVENTS_JS.index("ht:node-delete")
        handler_start = _CANVAS_EVENTS_JS[idx:]
        assert "if (window.HT_READONLY) return;" in handler_start[:200]

    def test_node_duplicate_has_readonly_guard(self) -> None:
        idx = _CANVAS_EVENTS_JS.index("ht:node-duplicate")
        handler_start = _CANVAS_EVENTS_JS[idx:]
        assert "if (window.HT_READONLY) return;" in handler_start[:200]

    def test_association_source_has_readonly_guard(self) -> None:
        idx = _CANVAS_EVENTS_JS.index("ht:association-source")
        handler_start = _CANVAS_EVENTS_JS[idx:]
        assert "if (window.HT_READONLY) return;" in handler_start[:200]

    def test_edge_delete_has_readonly_guard(self) -> None:
        idx = _CANVAS_EVENTS_JS.index("ht:edge-delete")
        handler_start = _CANVAS_EVENTS_JS[idx:]
        assert "if (window.HT_READONLY) return;" in handler_start[:200]

    def test_read_safe_handlers_not_guarded(self) -> None:
        """ht:node-edit and ht:save-version are read-safe and should NOT be guarded."""
        # node-edit handler opens detail panel — read-safe
        idx = _CANVAS_EVENTS_JS.index("ht:node-edit")
        handler_snippet = _CANVAS_EVENTS_JS[idx:idx + 200]
        assert "if (window.HT_READONLY) return;" not in handler_snippet
        # save-version handler clicks the save button — read-safe
        idx2 = _CANVAS_EVENTS_JS.index("ht:save-version")
        handler_snippet2 = _CANVAS_EVENTS_JS[idx2:idx2 + 200]
        assert "if (window.HT_READONLY) return;" not in handler_snippet2
