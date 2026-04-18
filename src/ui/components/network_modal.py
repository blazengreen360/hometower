"""Reusable create/edit modal for network forms."""
from collections.abc import Callable
from dataclasses import dataclass
import html

from nicegui import ui

from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import secondary_button

@dataclass(frozen=True)
class NetworkModalController:
    open_for_mode: Callable[[str], None]
    close: Callable[[], None]
    set_error: Callable[[str], None]
    clear_error: Callable[[], None]


def create_network_modal(
    form: dict[str, str],
    on_submit: Callable[[], object],
) -> NetworkModalController:
    """Render the network modal and return control callbacks for the page."""
    with ui.dialog() as modal_dialog, card_surface(ui.card()).classes("min-w-[460px]"):
        with card_section(ui.column()):
            modal_title = ui.label("Add Network").classes("ht-section-title")

            with ui.row().classes("w-full gap-2"):
                ui.input("Name").classes("flex-1").props("outlined").bind_value(form, "name")
                ui.input("VLAN ID (optional)").classes("w-40").props("outlined").bind_value(form, "vlan_id")

            with ui.row().classes("w-full gap-2"):
                ui.input("CIDR").classes("flex-1").props("outlined").bind_value(form, "cidr")
                ui.input("Gateway (optional)").classes("flex-1").props("outlined").bind_value(form, "gateway")

            with ui.row().classes("w-full gap-2"):
                ui.input("Color").classes("w-40").props("outlined").bind_value(form, "color")
                ui.input("Description (optional)").classes("flex-1").props("outlined").bind_value(form, "description")

            error_label = ui.label("").classes("ht-form-error")

            with ui.row().classes("w-full justify-end gap-2"):
                secondary_button(ui.button("Cancel", on_click=modal_dialog.close))
                primary_button(ui.button("Save", on_click=on_submit))

    def set_error(message: str) -> None:
        error_label.set_text(html.escape(message))

    def clear_error() -> None:
        error_label.set_text("")

    def open_for_mode(mode: str) -> None:
        modal_title.set_text("Add Network" if mode == "create" else "Edit Network")
        clear_error()
        modal_dialog.open()

    return NetworkModalController(
        open_for_mode=open_for_mode,
        close=modal_dialog.close,
        set_error=set_error,
        clear_error=clear_error,
    )
