"""Unit tests for connection panel behavior and edge style mapping (HT-030)."""
import html
import json
import inspect

from src.models.types import ConnectionType
from src.ui.components.canvas_styles import EDGE_STYLE_BY_CONNECTION_TYPE
from src.ui.components.connection_detail_panel import (
    _BRIDGE_JS,
    _build_cy_edge_remove_js,
    _build_cy_edge_update_js,
    can_edit_connection,
    render_connection_detail_panel,
)


class TestConnectionEdgeStyleMapping:
    def test_all_connection_types_have_style_overrides_entry(self) -> None:
        for conn_type in ConnectionType:
            assert conn_type.value in EDGE_STYLE_BY_CONNECTION_TYPE

    def test_wifi_and_vm_have_expected_dashed_styles(self) -> None:
        assert EDGE_STYLE_BY_CONNECTION_TYPE["WiFi"].get("line-style") == "dashed"
        assert EDGE_STYLE_BY_CONNECTION_TYPE["VM"].get("line-style") == "dashed"

    def test_fibre_and_other_have_expected_visuals(self) -> None:
        assert EDGE_STYLE_BY_CONNECTION_TYPE["Fibre"].get("width") == 4
        assert EDGE_STYLE_BY_CONNECTION_TYPE["Other"].get("opacity") == 0.7


class TestConnectionPanelBehavior:
    def test_role_gate_for_save_delete_actions(self) -> None:
        assert can_edit_connection("Admin") is True
        assert can_edit_connection("Contributor") is True
        assert can_edit_connection("Reader") is False

    def test_bridge_js_emits_select_and_hides_on_other_selection(self) -> None:
        assert "conn_panel_select" in _BRIDGE_JS
        assert "ht:edge-selected" in _BRIDGE_JS
        assert "ht:node-selected" in _BRIDGE_JS
        assert "ht:canvas-bg-click" in _BRIDGE_JS

    def test_render_function_contains_editor_and_read_only_branches(self) -> None:
        source = inspect.getsource(render_connection_detail_panel)
        assert "if is_editor:" in source
        assert '"Save"' in source
        assert '"Delete"' in source
        assert "else:" in source
        assert "Type: {safe_ctype}" in source
        assert "asyncio.ensure_future" not in source

    def test_js_generation_serializes_untrusted_values(self) -> None:
        conn_id = "edge'\"<svg>"
        conn_type = 'Wi"Fi'
        label = "Bob's \"<script>alert(1)</script>\" link"
        escaped_label = html.escape(label)

        update_js = _build_cy_edge_update_js(conn_id, conn_type, label)
        remove_js = _build_cy_edge_remove_js(conn_id)

        assert f"getElementById({json.dumps(conn_id)})" in update_js
        assert f"e.data('connection_type',{json.dumps(conn_type)})" in update_js
        assert f"e.data('label',{json.dumps(escaped_label)})" in update_js
        assert f"e.data('raw_label',{json.dumps(label)})" in update_js
        assert f"getElementById({json.dumps(conn_id)}).remove()" in remove_js
