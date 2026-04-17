"""Unit tests for the toast notification component.

Verifies that show_toast() delegates to ui.notify() with the correct
arguments for every toast type, default duration, and custom duration.
"""
from unittest.mock import call, patch

import pytest


class TestShowToastCallsUiNotify:
    def test_success_toast_calls_notify(self) -> None:
        """show_toast('success', ...) calls ui.notify with positive type."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="success", title="Device saved")
            mock_notify.assert_called_once()
            _, kwargs = mock_notify.call_args
            assert kwargs.get("type") == "positive"

    def test_error_toast_calls_notify(self) -> None:
        """show_toast('error', ...) calls ui.notify with negative type."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="error", title="Save failed")
            mock_notify.assert_called_once()
            _, kwargs = mock_notify.call_args
            assert kwargs.get("type") == "negative"

    def test_warning_toast_calls_notify(self) -> None:
        """show_toast('warning', ...) calls ui.notify with warning type."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="warning", title="Unsaved changes")
            mock_notify.assert_called_once()
            _, kwargs = mock_notify.call_args
            assert kwargs.get("type") == "warning"

    def test_info_toast_calls_notify(self) -> None:
        """show_toast('info', ...) calls ui.notify with info type."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="info", title="Copied to clipboard")
            mock_notify.assert_called_once()
            _, kwargs = mock_notify.call_args
            assert kwargs.get("type") == "info"


class TestDefaultDuration:
    def test_default_timeout_is_4000ms(self) -> None:
        """Default duration is 4000 ms when not specified."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="success", title="Hello")
            _, kwargs = mock_notify.call_args
            assert kwargs.get("timeout") == 4000

    def test_custom_duration_override(self) -> None:
        """Caller-supplied duration_ms is forwarded to notify timeout."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="info", title="Quick note", duration_ms=1500)
            _, kwargs = mock_notify.call_args
            assert kwargs.get("timeout") == 1500


class TestMessageContent:
    def test_title_only_uses_title_as_message(self) -> None:
        """When no description, the message is just the title."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="success", title="Done")
            args, kwargs = mock_notify.call_args
            # message is first positional arg or 'message' kwarg
            message = args[0] if args else kwargs.get("message", "")
            assert "Done" in message

    def test_description_appended_to_message(self) -> None:
        """When description provided, it appears in the notify message."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="error", title="Failed", description="Timeout error")
            args, kwargs = mock_notify.call_args
            message = args[0] if args else kwargs.get("message", "")
            assert "Failed" in message
            assert "Timeout error" in message


class TestPositioning:
    def test_toast_positioned_top_right(self) -> None:
        """show_toast always sets position to top-right."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="success", title="Test")
            _, kwargs = mock_notify.call_args
            assert kwargs.get("position") == "top-right"

    def test_close_button_enabled(self) -> None:
        """Toast always includes a close button."""
        from src.ui.components.toast import show_toast

        with patch("nicegui.ui.notify") as mock_notify:
            show_toast(type="warning", title="Heads up")
            _, kwargs = mock_notify.call_args
            assert kwargs.get("close_button") is True
