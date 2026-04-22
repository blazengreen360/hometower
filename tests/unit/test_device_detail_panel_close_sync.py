"""Regression test for device detail panel close-path layout sync."""

from __future__ import annotations

import asyncio
import inspect

import pytest

from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


async def _invoke(handler: object) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


class TestDeviceDetailPanelCloseSync:
    def test_build_right_rail_panel_uses_current_ui_element(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_panel_shell as panel_shell_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, panel_shell_module, fake_ui)

        panel = panel_shell_module.build_right_rail_panel(
            "device-detail-panel",
            "Device details",
        )

        assert panel in fake_ui.created["element"]

    def test_close_button_dispatches_topology_layout_sync(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_panel as detail_panel_module
        import src.ui.components.device_detail_panel_shell as panel_shell_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, detail_panel_module, fake_ui)
        install_fake_ui(monkeypatch, panel_shell_module, fake_ui)

        detail_panel_module.render_detail_panel("token", "Contributor")

        close_button = next(button for button in fake_ui.created["button"] if button.value == "close")

        asyncio.run(_invoke(close_button.handlers["click"]))

        expected_js = panel_shell_module.build_panel_visibility_js("device-detail-panel", False)
        assert fake_ui.run_javascript_calls == [expected_js]
        assert "ht:topology-layout-sync" in expected_js