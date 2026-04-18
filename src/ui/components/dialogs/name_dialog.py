"""Reusable 'enter a name' dialog for create/rename operations."""
from collections.abc import Awaitable, Callable
from typing import Optional

from nicegui import ui

from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import secondary_button

SubmitHandler = Callable[[str], Awaitable[str | None]]


async def show_name_dialog(
    title: str,
    placeholder: str = "Name",
    current_value: str = "",
    on_submit: Optional[SubmitHandler] = None,
) -> None:
    """Open a dialog prompting for a name, then call on_submit with the value."""

    with ui.dialog() as dialog, card_surface(ui.card()).classes("w-80"):
        with card_section(ui.column()).style("max-height:80vh; overflow:auto"):
            ui.label(title).classes("ht-section-title")
            name_input: ui.input = ui.input(
                placeholder=placeholder, value=current_value,
            ).classes("w-full").props("outlined")
            error_label = ui.label("").classes("ht-form-error")
            error_label.set_visibility(False)

            name_input.on(
                "keydown.enter",
                lambda: _submit(dialog, name_input, error_label, on_submit),
            )
            name_input.on_value_change(lambda _e: _clear_error(name_input, error_label))

            with ui.row().classes("justify-end w-full gap-2"):
                secondary_button(ui.button("Cancel", on_click=dialog.close))
                primary_button(ui.button(
                    "Save",
                    on_click=lambda: _submit(dialog, name_input, error_label, on_submit),
                ))

    dialog.open()


def _show_error(name_input: ui.input, error_label: ui.label, message: str) -> None:
    error_label.set_text(message)
    error_label.set_visibility(True)
    name_input.props("error")


def _clear_error(name_input: ui.input, error_label: ui.label) -> None:
    error_label.set_text("")
    error_label.set_visibility(False)
    name_input.props(remove="error")


async def _submit(
    dialog: ui.dialog,
    name_input: ui.input,
    error_label: ui.label,
    on_submit: Optional[SubmitHandler],
) -> None:
    value = name_input.value.strip() if name_input.value else ""
    if not value:
        _show_error(name_input, error_label, "Name is required")
        return

    _clear_error(name_input, error_label)

    if on_submit:
        error = await on_submit(value)
        if error:
            _show_error(name_input, error_label, error)
            return

    dialog.close()
