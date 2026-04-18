"""Reusable create/edit modal for location forms."""
from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import secondary_button
from src.ui.design.tokens import FONT_MONO


@dataclass(frozen=True)
class LocationModalController:
    open_for_mode: Callable[[str], None]
    close: Callable[[], None]
    set_error: Callable[[str], None]
    clear_error: Callable[[], None]


def create_location_modal(
    form: dict[str, str],
    on_submit: Callable[[], object],
) -> LocationModalController:
    """Render the location modal and return simple controls for the page."""
    with ui.dialog() as modal_dialog, card_surface(ui.card()).classes("min-w-[400px]"):
        with card_section(ui.column()):
            modal_title = ui.label("Add Location").classes("ht-section-title")

            name_input = ui.input("Name").classes("w-full").props("outlined").bind_value(form, "name")

            type_select = (
                ui.select(["rack", "geo"], label="Type", value="rack")
                .classes("w-full")
                .props("outlined")
                .bind_value(form, "type")
            )

            rack_container = ui.column().classes("w-full gap-2")
            with rack_container:
                rack_input = ui.input("Rack (optional)").classes("w-full").props("outlined").bind_value(form, "rack")
                row_input = ui.input("Row (optional)").classes("w-full").props("outlined").bind_value(form, "row")
                parent_input = ui.input("Parent ID (optional UUID)").classes("w-full").props("outlined").bind_value(
                    form, "parent_id"
                )

            geo_container = ui.column().classes("w-full gap-2")
            with geo_container:
                lat_input = ui.input("Latitude").classes("w-full").props("outlined").style(
                    f"font-family: {FONT_MONO}"
                ).bind_value(form, "lat")
                lng_input = ui.input("Longitude").classes("w-full").props("outlined").style(
                    f"font-family: {FONT_MONO}"
                ).bind_value(form, "lng")

            error_label = ui.label("").classes("ht-form-error")
            error_label.set_visibility(False)

        def set_error(message: str) -> None:
            error_label.set_text(message)
            error_label.set_visibility(True)
            name_input.props("error")

        def clear_error() -> None:
            error_label.set_text("")
            error_label.set_visibility(False)
            name_input.props(remove="error")

        for control in (
            name_input,
            type_select,
            rack_input,
            row_input,
            parent_input,
            lat_input,
            lng_input,
        ):
            control.on_value_change(lambda _event: clear_error())

        def update_type_visibility() -> None:
            is_geo = form["type"] == "geo"
            rack_container.set_visibility(not is_geo)
            geo_container.set_visibility(is_geo)
            if is_geo:
                form["rack"] = ""
                form["row"] = ""
                form["parent_id"] = ""
            else:
                form["lat"] = ""
                form["lng"] = ""

        type_select.on_value_change(lambda _: update_type_visibility())
        update_type_visibility()

        with ui.row().classes("w-full justify-end gap-2"):
            secondary_button(ui.button("Cancel", on_click=modal_dialog.close))
            primary_button(ui.button("Save", on_click=on_submit))

    def open_for_mode(mode: str) -> None:
        modal_title.set_text("Add Location" if mode == "create" else "Edit Location")
        clear_error()
        update_type_visibility()
        modal_dialog.open()

    return LocationModalController(
        open_for_mode=open_for_mode,
        close=modal_dialog.close,
        set_error=set_error,
        clear_error=clear_error,
    )
