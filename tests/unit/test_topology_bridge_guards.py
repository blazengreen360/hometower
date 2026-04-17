"""Unit tests for topology page bridge singleton guards (HT-067)."""

from src.ui.components.canvas_context_menu import CONTEXT_MENU_JS
from src.ui.components.connection_detail_panel import (
    _BRIDGE_JS as CONNECTION_DETAIL_PANEL_BRIDGE_JS,
)
from src.ui.components.device_detail_panel_bridge import DEVICE_DETAIL_PANEL_BRIDGE_JS


def _assert_singleton_guard(
    js: str,
    init_check: str,
    init_set: str,
    listener_marker: str,
) -> None:
    assert init_check in js
    assert init_set in js
    assert js.index(init_check) < js.index(listener_marker)
    assert js.index(init_set) < js.index(listener_marker)


class TestCanvasContextMenuJS:
    def test_singleton_guard_precedes_listener_registration(self) -> None:
        _assert_singleton_guard(
            js=CONTEXT_MENU_JS,
            init_check="if (window._htContextMenuInit) return;",
            init_set="window._htContextMenuInit = true;",
            listener_marker="document.addEventListener('ht:context-menu-request'",
        )

    def test_context_menu_still_tracks_request_and_pointer_events(self) -> None:
        assert "ht:context-menu-request" in CONTEXT_MENU_JS
        assert "document.addEventListener('mousemove'" in CONTEXT_MENU_JS


class TestDeviceDetailPanelBridgeJS:
    def test_singleton_guard_precedes_listener_registration(self) -> None:
        _assert_singleton_guard(
            js=DEVICE_DETAIL_PANEL_BRIDGE_JS,
            init_check="if (window._htDetailBridgeInit) return;",
            init_set="window._htDetailBridgeInit = true;",
            listener_marker="document.addEventListener('ht:node-selected'",
        )


class TestConnectionDetailPanelBridgeJS:
    def test_singleton_guard_precedes_listener_registration(self) -> None:
        _assert_singleton_guard(
            js=CONNECTION_DETAIL_PANEL_BRIDGE_JS,
            init_check="if (window._htConnBridgeInit) return;",
            init_set="window._htConnBridgeInit = true;",
            listener_marker="document.addEventListener('ht:edge-selected'",
        )