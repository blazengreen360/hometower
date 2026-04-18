"""Shared UI helpers for Settings list pages."""
from collections.abc import Awaitable, Callable

from nicegui import ui

from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import secondary_button


def show_destructive_confirmation(
    *,
    ui_module: object,
    title: str,
    description: str | None,
    on_confirm: Callable[[], Awaitable[None]],
    min_width_class: str = "min-w-[340px]",
    confirm_label: str = "Delete",
) -> None:
    """Open a standard destructive confirmation dialog."""
    with getattr(ui_module, "dialog")() as confirm_dlg, card_surface(getattr(ui_module, "card")()).classes(min_width_class):
        with card_section(getattr(ui_module, "column")()):
            getattr(ui_module, "label")(title).classes("ht-section-title")
            if description:
                getattr(ui_module, "label")(description).classes("ht-small-copy")
            with getattr(ui_module, "row")().classes("gap-2 justify-end"):
                secondary_button(getattr(ui_module, "button")("Cancel", on_click=confirm_dlg.close))

                async def _confirm_and_close() -> None:
                    confirm_dlg.close()
                    await on_confirm()

                danger_button(getattr(ui_module, "button")(confirm_label, on_click=_confirm_and_close))
    confirm_dlg.open()
