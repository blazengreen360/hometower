"""Unit tests for the inventory stencils panel (HT-049).

Tests cover:
 - JS bridge presence (stencil drag, stencil drop handler, duplicate prevention)
 - Python helper functions (filter devices, compute placed IDs, search matching)
 - NiceGUI component existence
 - Event consumer presence (ht:stencil-placed, ht:stencil-refresh)
 - Collapse toggle (htStencilToggle, ht-stencils-collapsed)
 - Virtual scroll (IntersectionObserver, htStencilInit, htStencilFilter)
"""
from src.models.types import DeviceType
from src.ui.components.stencils_panel_js import (
    STENCIL_DRAG_JS,
    STENCIL_DROP_HANDLER_JS,
    STENCIL_PANEL_JS,
)
from src.ui.components.canvas_draft_events import CANVAS_DRAFT_EVENTS_JS
from src.ui.components.stencils_panel import (
    filter_stencil_devices,
    compute_placed_ids,
)


# ── JS bridge presence tests ─────────────────────────────────────────────


class TestStencilDragJS:
    """Verify STENCIL_DRAG_JS sets the correct dataTransfer keys."""

    def test_sets_inventory_device_id(self) -> None:
        assert "inventoryDeviceId" in STENCIL_DRAG_JS

    def test_sets_inventory_device_name(self) -> None:
        assert "inventoryDeviceName" in STENCIL_DRAG_JS

    def test_sets_inventory_device_type(self) -> None:
        assert "inventoryDeviceType" in STENCIL_DRAG_JS

    def test_sets_inventory_device_version(self) -> None:
        assert "inventoryDeviceVersion" in STENCIL_DRAG_JS

    def test_sets_effect_allowed_copy(self) -> None:
        assert "effectAllowed" in STENCIL_DRAG_JS

    def test_sets_draggable_attribute(self) -> None:
        assert "draggable" in STENCIL_DRAG_JS

    def test_dragend_restores_opacity(self) -> None:
        assert "dragend" in STENCIL_DRAG_JS


class TestStencilDropHandlerJS:
    """Verify STENCIL_DROP_HANDLER_JS handles placement and dedup."""

    def test_listens_for_stencil_drop_event(self) -> None:
        assert "ht:stencil-drop" in STENCIL_DROP_HANDLER_JS

    def test_checks_readonly_guard(self) -> None:
        assert "HT_READONLY" in STENCIL_DROP_HANDLER_JS

    def test_duplicate_prevention_check(self) -> None:
        assert "getElementById" in STENCIL_DROP_HANDLER_JS

    def test_creates_node_via_cy_add(self) -> None:
        assert "cy.add(" in STENCIL_DROP_HANDLER_JS or ".add({" in STENCIL_DROP_HANDLER_JS

    def test_triggers_autosave(self) -> None:
        assert "window.scheduleAutosave(800);" in STENCIL_DROP_HANDLER_JS
        assert "clearTimeout(window._htAutosaveTimer)" not in STENCIL_DROP_HANDLER_JS

    def test_dispatches_placed_event(self) -> None:
        assert "ht:stencil-placed" in STENCIL_DROP_HANDLER_JS

    def test_uses_device_shapes(self) -> None:
        assert "deviceShapes" in STENCIL_DROP_HANDLER_JS

    def test_reads_inventory_device_version(self) -> None:
        assert "deviceVersion" in STENCIL_DROP_HANDLER_JS

    def test_stores_version_on_published_node_data(self) -> None:
        assert "version: deviceVersion" in STENCIL_DROP_HANDLER_JS

    def test_drag_payload_and_drop_handler_share_version_bridge_contract(self) -> None:
        assert "inventoryDeviceVersion" in STENCIL_DRAG_JS
        assert "var deviceVersion = Number(d.deviceVersion || 1);" in STENCIL_DROP_HANDLER_JS

    def test_no_timer_based_refresh_relay(self) -> None:
        """Timer-based ht:stencil-refresh relay was removed (timing race fix)."""
        assert "ht:node-remove-from-view" not in STENCIL_DROP_HANDLER_JS


# ── Python helper function tests ─────────────────────────────────────────


class TestFilterStencilDevices:
    """Verify filter_stencil_devices applies search and type filters."""

    def _sample_devices(self) -> list[dict[str, str]]:
        return [
            {"id": "aaa", "name": "Web Server", "type": "Server", "ip": "10.0.0.1"},
            {"id": "bbb", "name": "Core Switch", "type": "Switch", "ip": "10.0.0.2"},
            {"id": "ccc", "name": "Edge Router", "type": "Router", "ip": ""},
            {"id": "ddd", "name": "NAS Box", "type": "NAS", "ip": "10.0.0.4"},
        ]

    def test_no_filters_returns_all(self) -> None:
        devices = self._sample_devices()
        result = filter_stencil_devices(devices, search="", type_filter="")
        assert len(result) == 4

    def test_search_by_name_case_insensitive(self) -> None:
        devices = self._sample_devices()
        result = filter_stencil_devices(devices, search="server", type_filter="")
        assert len(result) == 1
        assert result[0]["id"] == "aaa"

    def test_search_substring_match(self) -> None:
        devices = self._sample_devices()
        result = filter_stencil_devices(devices, search="edge", type_filter="")
        assert len(result) == 1
        assert result[0]["id"] == "ccc"

    def test_type_filter_exact_match(self) -> None:
        devices = self._sample_devices()
        result = filter_stencil_devices(devices, search="", type_filter="Switch")
        assert len(result) == 1
        assert result[0]["id"] == "bbb"

    def test_search_and_type_combined(self) -> None:
        devices = self._sample_devices()
        result = filter_stencil_devices(
            devices, search="core", type_filter="Switch"
        )
        assert len(result) == 1
        assert result[0]["id"] == "bbb"

    def test_search_and_type_combined_no_match(self) -> None:
        devices = self._sample_devices()
        result = filter_stencil_devices(
            devices, search="web", type_filter="Switch"
        )
        assert len(result) == 0

    def test_empty_list_returns_empty(self) -> None:
        result = filter_stencil_devices([], search="anything", type_filter="")
        assert result == []


class TestComputePlacedIds:
    """Verify compute_placed_ids extracts node IDs from Cytoscape elements."""

    def test_extracts_node_ids(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "aaa", "label": "Server"}},
            {"data": {"id": "bbb", "label": "Switch"}},
            {"group": "edges", "data": {"id": "e1", "source": "aaa", "target": "bbb"}},
        ]
        result = compute_placed_ids(elements)
        assert result == {"aaa", "bbb"}

    def test_excludes_edges(self) -> None:
        elements: list[dict[str, object]] = [
            {"group": "edges", "data": {"id": "e1", "source": "a", "target": "b"}},
        ]
        result = compute_placed_ids(elements)
        assert result == set()

    def test_excludes_draft_nodes(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "aaa", "label": "Server"}},
            {"data": {"id": "draft-123", "label": "Draft", "draft": True}},
        ]
        result = compute_placed_ids(elements)
        assert result == {"aaa"}

    def test_empty_elements(self) -> None:
        result = compute_placed_ids([])
        assert result == set()


# ── STENCIL_PANEL_JS event consumer + virtual scroll + collapse tests ────


class TestStencilPanelJSEventConsumers:
    """Verify STENCIL_PANEL_JS consumes placed-state events."""

    def test_listens_for_stencil_placed_event(self) -> None:
        assert "ht:stencil-placed" in STENCIL_PANEL_JS

    def test_listens_for_stencil_refresh_event(self) -> None:
        assert "ht:stencil-refresh" in STENCIL_PANEL_JS

    def test_listens_for_published_device_event(self) -> None:
        assert "ht:stencil-device-published" in STENCIL_PANEL_JS

    def test_placed_event_adds_placed_class(self) -> None:
        assert "ht-stencil-placed" in STENCIL_PANEL_JS

    def test_refresh_event_checks_cy_nodes(self) -> None:
        assert "window._cy" in STENCIL_PANEL_JS
        assert ".nodes()" in STENCIL_PANEL_JS

    def test_refresh_excludes_draft_nodes(self) -> None:
        assert "draft-" in STENCIL_PANEL_JS

    def test_placed_event_removes_draggable(self) -> None:
        assert "removeAttribute" in STENCIL_PANEL_JS
        assert "draggable" in STENCIL_PANEL_JS

    def test_placed_event_appends_badge(self) -> None:
        assert "ht-placed-badge" in STENCIL_PANEL_JS

    def test_published_device_event_upserts_and_marks_placed(self) -> None:
        assert "function _upsert(dev)" in STENCIL_PANEL_JS
        assert "_d.unshift(dev);" in STENCIL_PANEL_JS
        assert "_p.add(String(dev.id || ''));" in STENCIL_PANEL_JS
        assert "_consumePublishedDevice(dev);" in STENCIL_PANEL_JS


class TestStencilPanelJSVirtualScroll:
    """Verify STENCIL_PANEL_JS uses virtual scroll for large inventories."""

    def test_uses_intersection_observer(self) -> None:
        assert "IntersectionObserver" in STENCIL_PANEL_JS

    def test_exposes_init_function(self) -> None:
        assert "htStencilInit" in STENCIL_PANEL_JS

    def test_exposes_filter_function(self) -> None:
        assert "htStencilFilter" in STENCIL_PANEL_JS

    def test_renders_in_batches(self) -> None:
        # _B (batch size) controls incremental rendering
        assert "_B" in STENCIL_PANEL_JS

    def test_uses_document_fragment(self) -> None:
        """Batch rendering should use DocumentFragment for performance."""
        assert "createDocumentFragment" in STENCIL_PANEL_JS

    def test_exposes_publish_upsert_bridge_for_backward_compatibility(self) -> None:
        assert "window.htStencilUpsertPublishedDevice = function(dev)" in STENCIL_PANEL_JS


class TestStencilPanelJSCollapse:
    """Verify STENCIL_PANEL_JS collapse toggle behavior."""

    def test_exposes_toggle_function(self) -> None:
        assert "htStencilToggle" in STENCIL_PANEL_JS

    def test_toggles_collapsed_class(self) -> None:
        assert "ht-stencils-collapsed" in STENCIL_PANEL_JS

    def test_changes_icon_on_collapse(self) -> None:
        assert "chevron_right" in STENCIL_PANEL_JS
        assert "chevron_left" in STENCIL_PANEL_JS


class TestStencilPanelJSDesignTokens:
    """Verify STENCIL_PANEL_JS uses CSS variables, not hardcoded colors."""

    def test_badge_uses_css_var_success(self) -> None:
        assert "var(--ht-success)" in STENCIL_PANEL_JS

    def test_badge_uses_color_mix(self) -> None:
        assert "color-mix" in STENCIL_PANEL_JS

    def test_no_hardcoded_success_rgba(self) -> None:
        assert "rgba(74,222,128" not in STENCIL_PANEL_JS

    def test_rows_use_css_var_accent_fallback(self) -> None:
        assert "var(--ht-accent)" in STENCIL_PANEL_JS


class TestFilterAndPlacedInteraction:
    """Verify filter + placed-state interaction in Python helpers."""

    def test_filter_preserves_matching_placed_device(self) -> None:
        """Filtering should keep placed devices matching the search."""
        devices = [
            {"id": "aaa", "name": "Placed Server", "type": "Server", "ip": ""},
            {"id": "bbb", "name": "Other Switch", "type": "Switch", "ip": ""},
        ]
        placed = {"aaa"}
        filtered = filter_stencil_devices(devices, search="Server", type_filter="")
        assert any(d["id"] in placed for d in filtered)

    def test_filter_excludes_non_matching_placed(self) -> None:
        """A placed device that doesn't match the filter is excluded."""
        devices = [
            {"id": "aaa", "name": "Placed Server", "type": "Server", "ip": ""},
            {"id": "bbb", "name": "Active Switch", "type": "Switch", "ip": ""},
        ]
        filtered = filter_stencil_devices(devices, search="Switch", type_filter="")
        ids = {d["id"] for d in filtered}
        assert "aaa" not in ids
        assert "bbb" in ids

    def test_compute_placed_excludes_drafts_in_mixed(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "real-1", "label": "R1"}},
            {"data": {"id": "draft-abc", "label": "Draft", "draft": True}},
            {"data": {"id": "real-2", "label": "R2"}},
            {"group": "edges", "data": {"id": "e1"}},
        ]
        result = compute_placed_ids(elements)
        assert result == {"real-1", "real-2"}


# ── Draft events: stencil refresh after removal ──────────────────────────


class TestDraftEventsStencilRefresh:
    """ht:stencil-refresh must be dispatched after node removal, not via timer."""

    def test_dispatches_stencil_refresh_on_remove(self) -> None:
        assert "ht:stencil-refresh" in CANVAS_DRAFT_EVENTS_JS

    def test_refresh_not_wrapped_in_timer(self) -> None:
        """Refresh must be synchronous — no setTimeout around the dispatch."""
        # Find each occurrence of ht:stencil-refresh and check the preceding
        # 80 chars don't contain setTimeout (the autosave timer is separate).
        idx = 0
        while True:
            pos = CANVAS_DRAFT_EVENTS_JS.find("ht:stencil-refresh", idx)
            if pos == -1:
                break
            preceding = CANVAS_DRAFT_EVENTS_JS[max(0, pos - 80):pos]
            assert "setTimeout" not in preceding
            idx = pos + 1

    def test_remove_from_view_uses_shared_autosave_scheduler(self) -> None:
        assert "window.scheduleAutosave(800);" in CANVAS_DRAFT_EVENTS_JS
        assert "clearTimeout(window._htAutosaveTimer)" not in CANVAS_DRAFT_EVENTS_JS
