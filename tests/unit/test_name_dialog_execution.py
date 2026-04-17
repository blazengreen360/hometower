"""Execution tests for the shared name dialog component."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


class TestNameDialogExecution:
    def test_show_name_dialog_shows_required_error_and_clears_on_input(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.dialogs.name_dialog as name_dialog_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, name_dialog_module, fake_ui)

        async def exercise() -> None:
            await name_dialog_module.show_name_dialog(
                title="New Workspace",
                placeholder="Workspace name",
            )
            dialog = fake_ui.created["dialog"][0]
            name_input = fake_ui.created["input"][0]
            error_label = fake_ui.created["label"][1]
            save_button = next(button for button in fake_ui.created["button"] if button.value == "Save")

            name_input.value = "   "
            await _invoke(save_button.handlers["click"])

            assert dialog.closed is False
            assert error_label.visible is True
            assert error_label.text_value == "Name is required"
            assert any(call == "error" for call in name_input.props_calls)

            name_input.value = "Core"
            await _invoke(lambda: name_input.handlers["value_change"](SimpleNamespace(value="Core")))

            assert error_label.visible is False
            assert error_label.text_value == ""
            assert any("remove" in call and "error" in call for call in name_input.props_calls)

        asyncio.run(exercise())

    def test_show_name_dialog_keeps_open_on_submit_error_then_closes_on_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.dialogs.name_dialog as name_dialog_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, name_dialog_module, fake_ui)

        submitted_names: list[str] = []

        async def on_submit(name: str) -> str | None:
            submitted_names.append(name)
            if name == "Existing":
                return "A workspace with this name already exists."
            return None

        async def exercise() -> None:
            await name_dialog_module.show_name_dialog(
                title="Rename Workspace",
                placeholder="Workspace name",
                current_value="Current",
                on_submit=on_submit,
            )
            dialog = fake_ui.created["dialog"][0]
            name_input = fake_ui.created["input"][0]
            error_label = fake_ui.created["label"][1]
            save_button = next(button for button in fake_ui.created["button"] if button.value == "Save")

            name_input.value = "Existing"
            await _invoke(save_button.handlers["click"])

            assert dialog.closed is False
            assert error_label.visible is True
            assert error_label.text_value == "A workspace with this name already exists."

            name_input.value = "Renamed Workspace"
            await _invoke(
                lambda: name_input.handlers["value_change"](SimpleNamespace(value="Renamed Workspace"))
            )
            await _invoke(save_button.handlers["click"])

            assert dialog.closed is True
            assert error_label.visible is False
            assert error_label.text_value == ""

        asyncio.run(exercise())
        assert submitted_names == ["Existing", "Renamed Workspace"]