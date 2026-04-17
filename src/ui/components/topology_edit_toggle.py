"""Edit / Stop Editing toggle for the topology canvas (HT-048).

Hides the toggle button widget, its RBAC visibility logic, and the
draft-device warning prompt. If the button style or placement changes,
only this file needs updating.
"""
from typing import Awaitable, Callable

from nicegui import ui

from src.utils.logger import logger

_ROLES_WITH_EDIT = {"Admin", "Contributor"}


def render_edit_toggle(
    user_role: str,
    on_enter_edit: Callable[[], Awaitable[None]],
    on_exit_edit: Callable[[], Awaitable[None]],
) -> None:
    """Render an Edit / Stop Editing button for Contributor/Admin users.

    Readers see nothing — the function returns immediately.
    """
    if user_role not in _ROLES_WITH_EDIT:
        return

    state: dict[str, bool] = {
        "editing": False,
        "toggle_locked": False,
        "dialog_open": False,
        "release_toggle_on_hide": True,
    }

    def _apply_button_state() -> None:
        if state["editing"]:
            btn.props('icon="edit_off"')
            btn.text = "Stop Editing"
            btn.style(
                "background:var(--ht-accent);"
                " color:var(--ht-text-on-accent);"
                " font-size:0.875rem;"
            )
        else:
            btn.props('icon="edit"')
            btn.text = "Edit"
            btn.style(
                "background:var(--ht-bg-surface-raised);"
                " color:var(--ht-text-primary);"
                " font-size:0.875rem;"
            )

        if state["toggle_locked"]:
            btn.disable()
            btn.style("opacity:0.5; cursor:not-allowed;")
            return

        btn.enable()
        btn.style("opacity:1; cursor:pointer;")

    def _set_toggle_lock(locked: bool) -> None:
        state["toggle_locked"] = locked
        _apply_button_state()

    def _set_editing(editing: bool) -> None:
        state["editing"] = editing
        _apply_button_state()

    async def _toggle() -> None:
        if state["toggle_locked"]:
            return

        _set_toggle_lock(True)
        try:
            if state["editing"]:
                draft_count: int = 0
                try:
                    result = await ui.run_javascript(
                        "window._cy ? window._cy.nodes('.draft').length : 0"
                    )
                    draft_count = int(result) if result else 0
                except Exception:
                    draft_count = 0

                if draft_count > 0:
                    state["dialog_open"] = True
                    state["release_toggle_on_hide"] = True
                    with ui.dialog() as dlg, ui.card():
                        ui.label(
                            f"You have {draft_count} unpublished draft device(s). "
                            "They will remain as drafts on this View. Continue?"
                        )
                        with ui.row():
                            ui.button("Cancel", on_click=dlg.close).props("flat")
                            ui.button(
                                "Continue",
                                on_click=lambda: _confirm_exit(dlg),
                            ).style(
                                "background:var(--ht-accent);"
                                " color:var(--ht-text-on-accent);"
                            )
                    dlg.on("hide", _handle_dialog_hide)
                    dlg.open()
                    return

                await _do_exit()
                return

            await _do_enter()
        finally:
            if not state["dialog_open"]:
                _set_toggle_lock(False)

    def _handle_dialog_hide() -> None:
        state["dialog_open"] = False
        if state["release_toggle_on_hide"]:
            _set_toggle_lock(False)
        state["release_toggle_on_hide"] = True

    async def _confirm_exit(dlg: ui.dialog) -> None:
        if not state["dialog_open"]:
            return

        state["dialog_open"] = False
        state["release_toggle_on_hide"] = False
        dlg.close()
        try:
            await _do_exit()
        finally:
            state["release_toggle_on_hide"] = True
            _set_toggle_lock(False)

    async def _do_enter() -> None:
        _set_editing(True)
        try:
            await on_enter_edit()
        except Exception:
            _set_editing(False)
            raise
        logger.debug("Edit mode entered by {}", user_role)

    async def _do_exit() -> None:
        _set_editing(False)
        try:
            await on_exit_edit()
        except Exception:
            _set_editing(True)
            raise
        logger.debug("Edit mode exited by {}", user_role)

    btn = ui.button("Edit", icon="edit", on_click=_toggle).props('dense')
    _apply_button_state()
