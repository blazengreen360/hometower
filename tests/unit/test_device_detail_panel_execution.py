"""Execution tests for device detail panel undo-aware save wiring (HT-032)."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Awaitable, Callable

import pytest

from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


class TestDevicePanelHelpersExecution:
    def test_render_editable_row_uses_injected_save_value_callback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_panel_helpers as panel_helpers

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, panel_helpers, fake_ui)

        captured_values: list[str | None] = []
        saved_calls = {"count": 0}

        async def _save_value(value: str | None) -> bool:
            captured_values.append(value)
            return True

        def _on_saved() -> None:
            saved_calls["count"] += 1

        panel_helpers.render_editable_row(
            label="Name",
            current="old-name",
            field="name",
            device_id=uuid.uuid4(),
            token="token",
            is_editor=True,
            version=3,
            on_saved=_on_saved,
            save_value=_save_value,
        )

        edit_button = next(button for button in fake_ui.created["button"] if button.value == "edit")
        save_button = next(button for button in fake_ui.created["button"] if button.value == "check")
        value_input = fake_ui.created["input"][0]

        async def exercise() -> None:
            await _invoke(edit_button.handlers["click"])
            value_input.value = "new-name"
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert captured_values == ["new-name"]
        assert saved_calls["count"] == 1

    def test_render_editable_int_row_maps_empty_to_none_and_numeric_to_int(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_panel_helpers as panel_helpers

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, panel_helpers, fake_ui)

        captured_values: list[object] = []

        async def _save_value(value: object) -> bool:
            captured_values.append(value)
            return True

        panel_helpers.render_editable_int_row(
            label="Power (W)",
            current=75,
            device_id=uuid.uuid4(),
            token="token",
            is_editor=True,
            version=2,
            save_value=_save_value,
        )

        edit_button = next(button for button in fake_ui.created["button"] if button.value == "edit")
        save_button = next(button for button in fake_ui.created["button"] if button.value == "check")
        value_input = fake_ui.created["input"][0]

        async def exercise() -> None:
            await _invoke(edit_button.handlers["click"])
            value_input.value = "120"
            await _invoke(save_button.handlers["click"])

            await _invoke(edit_button.handlers["click"])
            value_input.value = ""
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert captured_values == [120, None]

    def test_render_editable_int_row_rejects_negative_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_panel_helpers as panel_helpers

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, panel_helpers, fake_ui)

        captured_values: list[object] = []

        async def _save_value(value: object) -> bool:
            captured_values.append(value)
            return True

        panel_helpers.render_editable_int_row(
            label="Power (W)",
            current=75,
            device_id=uuid.uuid4(),
            token="token",
            is_editor=True,
            version=2,
            save_value=_save_value,
        )

        edit_button = next(button for button in fake_ui.created["button"] if button.value == "edit")
        save_button = next(button for button in fake_ui.created["button"] if button.value == "check")
        value_input = fake_ui.created["input"][0]

        async def exercise() -> None:
            await _invoke(edit_button.handlers["click"])
            value_input.value = "-20"
            await _invoke(save_button.handlers["click"])

        asyncio.run(exercise())

        assert captured_values == []
        assert any(
            args[0] == "Power must be 0 or greater"
            for args, kwargs in fake_ui.notifications
            if kwargs.get("type") == "negative"
        )


class TestDeviceDetailPanelExecution:
    def test_detail_panel_routes_field_updates_through_undo_stack_contract(self) -> None:
        import src.ui.components.device_detail_panel as detail_panel_module

        source = inspect.getsource(detail_panel_module.render_detail_panel)

        assert "save_value=" in source
        assert "update_device_field" in source
        assert "Attachments" in source
        assert "Power (W)" in source
        assert "power_watts" in source

    def test_detail_bridge_routes_ghost_nodes_to_ghost_panel_event(self) -> None:
        from src.ui.components.device_detail_panel_bridge import DEVICE_DETAIL_PANEL_BRIDGE_JS

        assert "ghost_panel_select" in DEVICE_DETAIL_PANEL_BRIDGE_JS
        assert "nodeData.ghost" in DEVICE_DETAIL_PANEL_BRIDGE_JS
        assert "ghost_device_id" in DEVICE_DETAIL_PANEL_BRIDGE_JS
