"""Toast notification component.

Provides show_toast() callable from any NiceGUI page or component.
Wraps NiceGUI's ui.notify() with consistent styling, positioning, and
accessibility for all four toast types (success, error, warning, info).

Usage::

    from src.ui.components.toast import show_toast

    show_toast(type="success", title="Device saved", description="pihole updated")
    show_toast(type="error", title="Save failed", description="Connection refused")
    show_toast(type="warning", title="Unsaved changes")
    show_toast(type="info", title="Copied to clipboard", duration_ms=2000)
"""
from typing import Literal, Optional

from nicegui import ui

ToastType = Literal["success", "error", "warning", "info"]

# Quasar notify type literals accepted by NiceGUI
_QuasarType = Literal["positive", "negative", "warning", "info", "ongoing"]

# Map our toast types to Quasar / NiceGUI notify types
_QUASAR_TYPE: dict[str, _QuasarType] = {
    "success": "positive",
    "error": "negative",
    "warning": "warning",
    "info": "info",
}

_DEFAULT_DURATION_MS = 4000


def show_toast(
    type: ToastType,
    title: str,
    description: Optional[str] = None,
    duration_ms: int = _DEFAULT_DURATION_MS,
) -> None:
    """Display a toast notification in the top-right corner of the viewport.

    Args:
        type: Visual category — ``"success"``, ``"error"``, ``"warning"``, or ``"info"``.
        title: Short, bold headline shown in the notification.
        description: Optional detail text appended below the title.
        duration_ms: Auto-dismiss delay in milliseconds (default 4000).
    """
    message = title if description is None else f"{title}\n{description}"

    ui.notify(
        message,
        type=_QUASAR_TYPE[type],
        position="top-right",
        close_button=True,
        timeout=duration_ms,
        multi_line=description is not None,
    )
