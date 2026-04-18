"""Inventory device editor modal.

Provides a polished in-place edit flow for devices from the inventory table.
"""
import asyncio
import html
from collections.abc import Awaitable, Callable

import httpx
from nicegui import ui

from src.models.device import DeviceResponseEnriched
from src.models.types import DeviceStatus
from src.ui.components.device_type_options import get_editable_device_type_values
from src.ui.components.toast import show_toast
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import secondary_button
from src.utils.logger import logger
from src.utils.settings import settings


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _extract_error_detail(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
    except Exception:
        return f"Save failed ({resp.status_code})"

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            msg = first.get("msg")
            if isinstance(msg, str):
                return msg
    return f"Save failed ({resp.status_code})"


def create_inventory_edit_modal(
    token: str,
    can_edit: bool,
    refresh_devices: Callable[[], Awaitable[None]],
) -> Callable[[DeviceResponseEnriched], None]:
    """Create a reusable inventory device editor modal.

    Returns a callable that opens the modal for a specific device.
    """
    state: dict[str, DeviceResponseEnriched | None] = {"device": None}

    type_options = get_editable_device_type_values()
    status_options = [status.value for status in DeviceStatus]

    with ui.dialog() as dialog:
        with card_surface(ui.card()).classes("w-full max-w-[760px]"):
            with card_section(ui.column()):
                ui.label("Edit Device").classes("ht-section-title")
                subtitle = ui.label("").classes("ht-small-copy -mt-1")

                if can_edit:
                    ui.label("Update core properties and save changes.").classes("ht-small-copy")
                else:
                    ui.label("Read-only view: your role cannot edit devices.").classes("ht-small-copy")

                with ui.row().classes("w-full gap-3"):
                    name_input = ui.input("Name").classes("flex-1").props("dense outlined")
                    type_select = ui.select(type_options, label="Type").classes("w-48").props("dense outlined")
                    status_select = ui.select(status_options, label="Status").classes("w-48").props("dense outlined")

                with ui.row().classes("w-full gap-3"):
                    ip_input = ui.input("IP").classes("flex-1").props("dense outlined")
                    mac_input = ui.input("MAC").classes("flex-1").props("dense outlined")
                    os_input = ui.input("OS").classes("flex-1").props("dense outlined")

                notes_input = ui.textarea("Notes").props("autogrow outlined").classes("w-full")

                error_label = ui.label("").style("font-size:0.82rem; color:var(--ht-error);")
                error_label.set_visibility(False)

            if not can_edit:
                for field in [
                    name_input,
                    type_select,
                    status_select,
                    ip_input,
                    mac_input,
                    os_input,
                    notes_input,
                ]:
                    field.props("readonly")

            def _open_topology() -> None:
                current = state["device"]
                if current is None:
                    return
                ui.navigate.to(f"/topology?device_id={current.id}")
                dialog.close()

            async def _save() -> None:
                if not can_edit:
                    return
                current = state["device"]
                if current is None:
                    return

                name_value = str(name_input.value or "").strip()
                if not name_value:
                    error_label.set_text("Name is required")
                    error_label.set_visibility(True)
                    return

                payload: dict[str, str | None | int] = {
                    "name": name_value,
                    "type": str(type_select.value or current.type.value),
                    "status": str(status_select.value or current.status.value),
                    "ip": _clean_optional(str(ip_input.value or "")),
                    "mac": _clean_optional(str(mac_input.value or "")),
                    "os": _clean_optional(str(os_input.value or "")),
                    "notes": _clean_optional(str(notes_input.value or "")),
                    "version": int(current.version),
                }

                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.patch(
                            f"{settings.api_base_url}/api/devices/{current.id}",
                            json=payload,
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=8.0,
                        )
                except httpx.HTTPError as exc:
                    logger.error("Inventory device save failed: {}", str(exc))
                    error_label.set_text("Connection error while saving")
                    error_label.set_visibility(True)
                    return

                if resp.status_code == 200:
                    dialog.close()
                    show_toast(type="success", title="Device updated")
                    await refresh_devices()
                    return

                error_label.set_text(html.escape(_extract_error_detail(resp)))
                error_label.set_visibility(True)

            with ui.row().classes("w-full justify-between items-center pt-2"):
                secondary_button(
                    ui.button("Open in Topology", on_click=_open_topology).props("icon=account_tree")
                )
                with ui.row().classes("gap-2"):
                    secondary_button(ui.button("Close", on_click=dialog.close))
                    save_btn = primary_button(
                        ui.button(
                            "Save Changes",
                            on_click=lambda: asyncio.ensure_future(_save()),
                        )
                    )
                    if not can_edit:
                        save_btn.props("disable")

    def open_editor(device: DeviceResponseEnriched) -> None:
        state["device"] = device
        subtitle.set_text(f"ID: {str(device.id)[:8]}... ")
        type_select.set_options(get_editable_device_type_values(device.type), value=device.type.value)
        name_input.set_value(device.name)
        status_select.set_value(device.status.value)
        ip_input.set_value(device.ip or "")
        mac_input.set_value(device.mac or "")
        os_input.set_value(device.os or "")
        notes_input.set_value(device.notes or "")
        error_label.set_text("")
        error_label.set_visibility(False)
        dialog.open()

    return open_editor
