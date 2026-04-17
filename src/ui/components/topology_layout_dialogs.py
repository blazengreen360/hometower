"""Dialog builders for the topology history toolbar (HT-072)."""
from collections.abc import Awaitable, Callable

from nicegui import ui


def build_restore_dialog(
    restore_dlg: ui.dialog,
    inputs: dict[str, object],
    on_restore: Callable[[], None] | Callable[[], Awaitable[None]],
) -> None:
    """Populate the restore confirmation dialog for topology history management."""
    with restore_dlg:
        with ui.card().style("min-width:300px"):
            inputs["restore_label"] = ui.label(
                "Restore selected history version as the latest version?"
            ).style("font-weight:600;")
            with ui.row().classes("justify-end gap-2"):
                ui.button("Restore", on_click=on_restore).props("color=warning")
                ui.button("Cancel", on_click=restore_dlg.close).props("flat")
