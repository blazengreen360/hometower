"""Inventory delete confirmation dialog."""
from collections.abc import Callable
import inspect

import httpx
from nicegui import ui

from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import secondary_button
from src.utils.logger import logger
from src.utils.settings import settings


async def show_delete_confirmation(
    device_id: str,
    device_name: str,
    placement_count: int,
    token: str,
    on_deleted: Callable[[], object],
) -> None:
    """Show a delete confirmation dialog and execute deletion on confirm."""

    async def _fetch_placements() -> list[dict[str, str]]:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{settings.api_base_url}/api/devices/{device_id}/placements",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            logger.error("Placement fetch error: {}", str(exc))
        return []

    placements = await _fetch_placements()

    with ui.dialog() as dialog, card_surface(ui.card()).classes("min-w-[400px]"):
        with card_section(ui.column()):
            title = f"Delete {device_name}?" if device_name else "Delete device?"
            ui.label(title).classes("ht-section-title")
            if placements:
                ui.label(
                    f"This device appears in {len(placements)} topology diagram(s). "
                    "Removing it will leave orphaned canvas nodes."
                ).classes("ht-muted-copy")
                with ui.column().classes("q-ml-md"):
                    for p in placements:
                        topo = p.get("topology_name")
                        label = p.get("view_name", "Unknown view")
                        if topo:
                            label += f" ({topo})"
                        ui.label(f"\u2022 {label}").classes("ht-small-copy")
            else:
                ui.label("This device has no topology placements.").classes("ht-muted-copy")

            with ui.row().classes("w-full justify-end q-mt-md gap-2"):
                secondary_button(ui.button("Cancel", on_click=dialog.close))

                async def _do_delete() -> None:
                    try:
                        async with httpx.AsyncClient() as http:
                            resp = await http.delete(
                                f"{settings.api_base_url}/api/devices/{device_id}",
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=10.0,
                            )
                        if resp.status_code == 204:
                            ui.notify(f"Deleted {device_name}", type="positive")
                            dialog.close()
                            await on_deleted()  # type: ignore[misc]
                        else:
                            detail = resp.json().get("detail", "Delete failed")
                            ui.notify(detail, type="negative")
                    except Exception as exc:
                        logger.error("Delete error: {}", str(exc))
                        ui.notify("Delete failed", type="negative")

                danger_button(ui.button("Delete device", on_click=_do_delete))

    dialog.open()


async def show_bulk_delete_confirmation(
    selected_count: int,
    on_confirm: Callable[[], object],
) -> None:
    """Confirm bulk deletion before executing batch action."""

    async def _confirm_and_close(dialog: object) -> None:
        close = getattr(dialog, "close", None)
        if callable(close):
            close()
        maybe_awaitable = on_confirm()
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    with ui.dialog() as dialog, card_surface(ui.card()).classes("min-w-[400px]"):
        with card_section(ui.column()):
            ui.label(f"Delete {selected_count} devices?").classes("ht-section-title")
            ui.label(
                "This cannot be undone. Devices with active connections will be skipped."
            ).classes("ht-muted-copy")

            with ui.row().classes("w-full justify-end q-mt-md gap-2"):
                secondary_button(ui.button("Cancel", on_click=dialog.close))
                danger_button(ui.button(
                    "Delete devices",
                    on_click=lambda: _confirm_and_close(dialog),
                ))

    dialog.open()
