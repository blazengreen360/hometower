"""Tags section renderer for the device detail panel."""
import html
import uuid
from collections.abc import Callable

import httpx
from nicegui import ui

from src.models.tag import TagResponse
from src.utils.logger import logger
from src.utils.settings import settings


def render_tags_section(
    device_id: uuid.UUID,
    tags: list[TagResponse],
    all_tags: list[TagResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    """Colored tag chips with add/remove for Contributors."""
    if not tags and not is_editor:
        ui.label("No tags").style("font-size:0.875rem; color:var(--ht-text-secondary);")
        return

    with ui.row().classes("flex-wrap gap-1"):
        for tag in tags:
            with ui.row().classes("items-center gap-0").style(
                f"background:{tag.color}; border-radius: var(--ht-radius-pill); "
                "padding:2px 10px; max-width:fit-content;"
            ):
                ui.label(html.escape(tag.name)).style(
                    "font-size:0.75rem; color:white; font-weight:500;"
                )
                if is_editor:

                    confirm_dlg = ui.dialog()

                    async def _detach(t_id: uuid.UUID = tag.id, dlg=confirm_dlg) -> None:
                        try:
                            async with httpx.AsyncClient() as c:
                                await c.delete(
                                    f"{settings.api_base_url}/api/devices/{device_id}"
                                    f"/tags/{t_id}",
                                    headers={"Authorization": f"Bearer {token}"},
                                    timeout=5.0,
                                )
                        except httpx.HTTPError as exc:
                            logger.error("Tag detach: {}", str(exc))
                            ui.notify("Connection error", type="negative")
                            return
                        dlg.close()
                        on_change()

                    with confirm_dlg:
                        with ui.card().style("min-width:300px"):
                            ui.label(
                                f"Remove tag '{html.escape(tag.name)}' from this device?"
                            ).style(
                                "font-weight:600;"
                            )
                            with ui.row().classes("justify-end gap-2"):
                                ui.button("Remove", on_click=_detach).props(
                                    "color=negative"
                                )
                                ui.button("Cancel", on_click=confirm_dlg.close).props(
                                    "flat"
                                )

                    ui.button(
                        icon="close", on_click=lambda dlg=confirm_dlg: dlg.open()
                    ).props(
                        "flat dense round size=xs aria-label='Remove tag'"
                    ).style("color:white; padding:0;")

    if not is_editor:
        return

    attached_ids = {t.id for t in tags}
    available = [t for t in all_tags if t.id not in attached_ids]
    if not available:
        return

    opts = {str(t.id): html.escape(t.name) for t in available}

    async def _attach(e: object) -> None:
        val = getattr(e, "value", None)
        if not val:
            return
        try:
            async with httpx.AsyncClient() as c:
                await c.post(
                    f"{settings.api_base_url}/api/devices/{device_id}/tags",
                    json={"tag_id": val},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )
        except httpx.HTTPError as exc:
            logger.error("Tag attach: {}", str(exc))
            ui.notify("Connection error", type="negative")
            return
        on_change()

    ui.select(options=opts, label="+ Add tag").classes("w-full").props(
        "dense outlined"
    ).style("font-size:0.875rem;").on_value_change(_attach)
