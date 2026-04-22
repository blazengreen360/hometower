"""Toolbar controls for canvas undo/redo (HT-032)."""

from nicegui import ui


_EDITOR_ROLES = {"Admin", "Contributor"}


def render_topology_undo_bar(user_role: str) -> None:
    """Render undo/redo buttons for editor roles only."""
    if user_role not in _EDITOR_ROLES:
        return

    async def _request_undo() -> None:
        await ui.run_javascript(
            "if(window._htRequestUndo) window._htRequestUndo();"
        )

    async def _request_redo() -> None:
        await ui.run_javascript(
            "if(window._htRequestRedo) window._htRequestRedo();"
        )

    with ui.row().classes("items-center gap-1"):
        ui.button(icon="undo", on_click=_request_undo).props(
            'flat dense round id="ht-undo-button" title="Undo unavailable"'
        )
        ui.button(icon="redo", on_click=_request_redo).props(
            'flat dense round id="ht-redo-button" title="Redo unavailable"'
        )
