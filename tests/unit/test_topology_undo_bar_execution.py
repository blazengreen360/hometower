"""Execution tests for topology undo/redo toolbar component (HT-032)."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable

import pytest

from tests.unit.nicegui_fakes import FakeUI, install_fake_ui


async def _invoke(handler: Callable[..., object]) -> object:
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


class TestTopologyUndoBarExecution:
    def test_editor_roles_render_disabled_undo_redo_buttons(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_undo_bar as undo_bar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, undo_bar_module, fake_ui)

        undo_bar_module.render_topology_undo_bar("Contributor")

        buttons = fake_ui.created["button"]
        assert len(buttons) == 2
        button_values = {button.value for button in buttons}
        assert "undo" in button_values
        assert "redo" in button_values

        undo_button = next(button for button in buttons if button.value == "undo")
        redo_button = next(button for button in buttons if button.value == "redo")
        assert any("ht-undo-button" in props for props in undo_button.props_calls)
        assert any("ht-redo-button" in props for props in redo_button.props_calls)
        assert any("disable" in props for props in undo_button.props_calls)
        assert any("disable" in props for props in redo_button.props_calls)

    def test_reader_role_hides_undo_bar(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_undo_bar as undo_bar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, undo_bar_module, fake_ui)

        undo_bar_module.render_topology_undo_bar("Reader")

        assert fake_ui.created["button"] == []

    def test_button_clicks_call_stack_entrypoints(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.topology_undo_bar as undo_bar_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, undo_bar_module, fake_ui)

        undo_bar_module.render_topology_undo_bar("Admin")

        undo_button = next(button for button in fake_ui.created["button"] if button.value == "undo")
        redo_button = next(button for button in fake_ui.created["button"] if button.value == "redo")

        async def exercise() -> None:
            await _invoke(undo_button.handlers["click"])
            await _invoke(redo_button.handlers["click"])

        asyncio.run(exercise())

        assert any("_htRequestUndo" in call for call in fake_ui.run_javascript_calls)
        assert any("_htRequestRedo" in call for call in fake_ui.run_javascript_calls)
