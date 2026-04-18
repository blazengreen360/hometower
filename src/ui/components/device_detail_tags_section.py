"""Tags section renderer for the device detail panel."""
import html
import uuid
from collections.abc import Callable

import httpx
from nicegui import ui

from src.models.tag import TagResponse
from src.ui.design.primitives import card_section, card_surface, danger_button, on_accent_icon_button, secondary_button, secondary_icon_button
from src.utils.logger import logger
from src.utils.settings import settings


def _failure_message(response: object, fallback: str) -> str:
    status_code = getattr(response, "status_code", None)
    response_json = getattr(response, "json", None)
    try:
        payload = response_json() if callable(response_json) else None
    except Exception:
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
    if isinstance(status_code, int):
        return f"{fallback} ({status_code})"
    return fallback


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
                    "font-size:0.75rem; color:var(--ht-text-on-accent); font-weight:500;"
                )
                if is_editor:

                    confirm_dlg = ui.dialog()

                    async def _detach(t_id: uuid.UUID = tag.id, dlg=confirm_dlg) -> None:
                        try:
                            async with httpx.AsyncClient() as c:
                                response = await c.delete(
                                    f"{settings.api_base_url}/api/devices/{device_id}"
                                    f"/tags/{t_id}",
                                    headers={"Authorization": f"Bearer {token}"},
                                    timeout=5.0,
                                )
                        except httpx.HTTPError as exc:
                            logger.error("Tag detach: {}", str(exc))
                            ui.notify("Connection error", type="negative")
                            return
                        if response.status_code not in (200, 204):
                            ui.notify(_failure_message(response, "Remove tag failed"), type="negative")
                            return
                        dlg.close()
                        on_change()

                    with confirm_dlg:
                        with card_surface(ui.card()).classes("min-w-[300px]"):
                            with card_section(ui.column()):
                                ui.label(
                                    f"Remove tag '{html.escape(tag.name)}' from this device?"
                                ).classes("ht-section-title")
                                with ui.row().classes("justify-end gap-2"):
                                    secondary_button(ui.button("Cancel", on_click=confirm_dlg.close))
                                    danger_button(ui.button("Remove", on_click=_detach))

                    on_accent_icon_button(
                        ui.button(icon="close", on_click=lambda dlg=confirm_dlg: dlg.open()).props(
                            "aria-label='Remove tag'"
                        )
                    ).style("padding:0;")

    if not is_editor:
        return

    attached_ids = {t.id for t in tags}
    available = [t for t in all_tags if t.id not in attached_ids]
    if not available:
        empty_state = (
            "No tags available to add yet"
            if not all_tags
            else "All available tags are already attached"
        )
        with ui.row().classes("items-center justify-between gap-2 w-full"):
            ui.label(empty_state).style(
                "font-size:0.8125rem; color:var(--ht-text-secondary);"
            )
            secondary_icon_button(
                ui.button(icon="add").props("disable aria-label='Add tag unavailable'")
            )
        return

    opts = {str(t.id): html.escape(t.name) for t in available}

    async def _attach(e: object) -> None:
        val = getattr(e, "value", None)
        if not val:
            return
        try:
            async with httpx.AsyncClient() as c:
                response = await c.post(
                    f"{settings.api_base_url}/api/devices/{device_id}/tags",
                    json={"tag_id": val},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )
        except httpx.HTTPError as exc:
            logger.error("Tag attach: {}", str(exc))
            ui.notify("Connection error", type="negative")
            return
        if response.status_code not in (200, 201, 204):
            ui.notify(_failure_message(response, "Add tag failed"), type="negative")
            return
        on_change()

    ui.select(options=opts, label="+ Add tag").classes("w-full").props(
        "dense outlined"
    ).style("font-size:0.875rem;").on_value_change(_attach)
