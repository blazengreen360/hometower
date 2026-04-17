"""Unit tests for topology_edit_toggle module (HT-062).

Tests render_edit_toggle visibility logic by role and callback wiring.
NiceGUI rendering requires a running context, so we mock ui calls.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ui.components.topology_edit_toggle import render_edit_toggle


def _make_button_mock() -> MagicMock:
    button = MagicMock()
    button.style.return_value = button
    button.props.return_value = button
    return button


class _FakeContext:
    def __enter__(self) -> "_FakeContext":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class _FakeDialog:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.open_count = 0

    def __enter__(self) -> "_FakeDialog":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def on(self, event: str, handler: object) -> "_FakeDialog":
        self.handlers[event] = handler
        return self

    def open(self) -> None:
        self.open_count += 1

    def close(self) -> None:
        hide_handler = self.handlers.get("hide")
        if callable(hide_handler):
            hide_handler()


class TestRenderEditToggleRbac:
    """render_edit_toggle must hide the button for Readers."""

    @patch("src.ui.components.topology_edit_toggle.ui")
    def test_reader_renders_nothing(self, mock_ui: MagicMock) -> None:
        render_edit_toggle("Reader", AsyncMock(), AsyncMock())
        mock_ui.button.assert_not_called()

    @patch("src.ui.components.topology_edit_toggle.ui")
    def test_admin_renders_button(self, mock_ui: MagicMock) -> None:
        mock_btn = _make_button_mock()
        mock_ui.button.return_value = mock_btn
        render_edit_toggle("Admin", AsyncMock(), AsyncMock())
        mock_ui.button.assert_called_once()

    @patch("src.ui.components.topology_edit_toggle.ui")
    def test_contributor_renders_button(self, mock_ui: MagicMock) -> None:
        mock_btn = _make_button_mock()
        mock_ui.button.return_value = mock_btn
        render_edit_toggle("Contributor", AsyncMock(), AsyncMock())
        mock_ui.button.assert_called_once()


class TestRenderEditToggleCallbacks:
    """Edit toggle must accept async callbacks."""

    @patch("src.ui.components.topology_edit_toggle.ui")
    def test_accepts_async_enter_callback(self, mock_ui: MagicMock) -> None:
        enter_cb = AsyncMock()
        mock_btn = _make_button_mock()
        mock_ui.button.return_value = mock_btn
        render_edit_toggle("Admin", enter_cb, AsyncMock())
        # Should not raise

    @patch("src.ui.components.topology_edit_toggle.ui")
    def test_accepts_async_exit_callback(self, mock_ui: MagicMock) -> None:
        exit_cb = AsyncMock()
        mock_btn = _make_button_mock()
        mock_ui.button.return_value = mock_btn
        render_edit_toggle("Admin", AsyncMock(), exit_cb)
        # Should not raise


class TestRenderEditToggleDraftDialogLock:
    """Draft confirmation must lock the toggle until the dialog closes."""

    @pytest.mark.asyncio
    @patch("src.ui.components.topology_edit_toggle.ui")
    async def test_dialog_lock_blocks_concurrent_exit_clicks_before_draft_probe(
        self,
        mock_ui: MagicMock,
    ) -> None:
        enter_cb = AsyncMock()
        exit_cb = AsyncMock()
        main_button = _make_button_mock()
        dialog = _FakeDialog()

        extra_buttons = [_make_button_mock() for _ in range(4)]
        mock_ui.button.side_effect = [main_button, *extra_buttons]
        mock_ui.dialog.return_value = dialog
        mock_ui.card.return_value = _FakeContext()
        mock_ui.row.return_value = _FakeContext()

        release_probe = asyncio.Event()
        first_probe_started = asyncio.Event()
        probe_calls = 0

        async def _probe_drafts(_: str) -> int:
            nonlocal probe_calls
            probe_calls += 1
            first_probe_started.set()
            await release_probe.wait()
            return 2

        mock_ui.run_javascript.side_effect = _probe_drafts

        render_edit_toggle("Admin", enter_cb, exit_cb)
        toggle = mock_ui.button.call_args_list[0].kwargs["on_click"]

        await toggle()
        enter_cb.assert_awaited_once()
        main_button.reset_mock()

        first_exit = asyncio.create_task(toggle())
        await first_probe_started.wait()
        second_exit = asyncio.create_task(toggle())
        await asyncio.sleep(0)

        assert probe_calls == 1
        assert mock_ui.dialog.call_count == 0

        release_probe.set()
        await asyncio.gather(first_exit, second_exit)

        assert dialog.open_count == 1
        assert mock_ui.dialog.call_count == 1
        exit_cb.assert_not_awaited()
        main_button.disable.assert_called_once()
        assert any(
            "opacity:0.5" in call.args[0] and "cursor:not-allowed" in call.args[0]
            for call in main_button.style.call_args_list
        )

        await toggle()
        assert dialog.open_count == 1
        assert mock_ui.dialog.call_count == 1

        enable_count_before_hide = main_button.enable.call_count
        dialog.close()
        assert main_button.enable.call_count == enable_count_before_hide + 1

        await toggle()
        assert dialog.open_count == 2
        assert mock_ui.dialog.call_count == 2

    @pytest.mark.asyncio
    @patch("src.ui.components.topology_edit_toggle.ui")
    async def test_enter_failure_restores_edit_state_and_reenables_button(
        self,
        mock_ui: MagicMock,
    ) -> None:
        enter_cb = AsyncMock(side_effect=RuntimeError("enter failed"))
        main_button = _make_button_mock()

        mock_ui.button.return_value = main_button

        render_edit_toggle("Admin", enter_cb, AsyncMock())
        toggle = mock_ui.button.call_args.kwargs["on_click"]
        main_button.reset_mock()

        with pytest.raises(RuntimeError, match="enter failed"):
            await toggle()

        main_button.enable.assert_called()
        assert main_button.text == "Edit"

    @pytest.mark.asyncio
    @patch("src.ui.components.topology_edit_toggle.ui")
    async def test_exit_failure_restores_stop_editing_state_and_reenables_button(
        self,
        mock_ui: MagicMock,
    ) -> None:
        enter_cb = AsyncMock()
        exit_cb = AsyncMock(side_effect=RuntimeError("exit failed"))
        main_button = _make_button_mock()

        mock_ui.button.return_value = main_button
        mock_ui.run_javascript = AsyncMock(return_value=0)

        render_edit_toggle("Admin", enter_cb, exit_cb)
        toggle = mock_ui.button.call_args.kwargs["on_click"]

        await toggle()
        enter_cb.assert_awaited_once()
        main_button.reset_mock()

        with pytest.raises(RuntimeError, match="exit failed"):
            await toggle()

        main_button.enable.assert_called()
        assert main_button.text == "Stop Editing"
