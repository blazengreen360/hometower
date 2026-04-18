"""Dedicated device editor page for inventory actions."""
import asyncio
import html
import uuid

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import DeviceStatus, Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import get_ui_role, redirect_if_unauthenticated
from src.ui.components.device_type_options import get_editable_device_type_values
from src.ui.components.toast import show_toast
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import secondary_button
from src.ui.pages.device_edit_support import clean_optional as _clean_optional
from src.ui.pages.device_edit_support import clean_optional_int as _clean_optional_int
from src.ui.pages.device_edit_support import extract_error_detail as _extract_error_detail
from src.ui.pages.device_edit_support import load_device as _load_device
from src.utils.settings import settings


@ui.page("/inventory/edit/{device_id}")
async def inventory_device_edit_page(device_id: str) -> None:
    """Dedicated editor page for one device."""
    current_path = f"/inventory/edit/{device_id}"
    if redirect_if_unauthenticated(current_path=current_path):
        return

    token: str = nicegui_app.storage.user.get("access_token", "")
    role = get_ui_role()
    can_edit = role in {Role.Admin, Role.Contributor}

    try:
        parsed_device_id = uuid.UUID(device_id)
    except ValueError:
        with app_shell("Edit Device", "/inventory", breadcrumb=["Inventory", "Edit Device"]):
            with page_container(ui.column()):
                with card_surface(ui.card()).classes("max-w-[620px]"):
                    with card_section(ui.column()).classes("items-start"):
                        ui.label("Invalid device id").classes("ht-danger-copy")
                        secondary_button(ui.button("Back to Inventory", on_click=lambda: ui.navigate.to("/inventory")))
        return

    device = await _load_device(token, parsed_device_id)
    if device is None:
        with app_shell("Edit Device", "/inventory", breadcrumb=["Inventory", "Edit Device"]):
            with page_container(ui.column()):
                with card_surface(ui.card()).classes("max-w-[620px]"):
                    with card_section(ui.column()).classes("items-start"):
                        ui.label("Device not found or unavailable").classes("ht-danger-copy")
                        secondary_button(ui.button("Back to Inventory", on_click=lambda: ui.navigate.to("/inventory")))
        return

    type_options = get_editable_device_type_values(device.type)
    status_options = [status.value for status in DeviceStatus]

    with app_shell("Edit Device", "/inventory", breadcrumb=["Inventory", "Edit Device"]):
        with page_container(ui.column()):
            with ui.row().classes("w-full items-end justify-between gap-4 flex-wrap"):
                render_page_intro(
                    ui,
                    "Edit Device",
                    "Update inventory metadata from a dedicated editing surface with the same density and action hierarchy as the rest of the app.",
                    "Inventory",
                )
                with ui.row().classes("gap-2 flex-wrap"):
                    secondary_button(ui.button("Back to Inventory", on_click=lambda: ui.navigate.to("/inventory")))
                    secondary_button(
                        ui.button(
                            "Open in Topology",
                            on_click=lambda: ui.navigate.to(f"/topology?device_id={device.id}"),
                        ).props("icon=account_tree")
                    )

            with card_surface(ui.card()).classes("max-w-[920px]"):
                with card_section(ui.column()):
                    ui.label(f"Device ID: {device.id}").classes("ht-small-copy")

                    if not can_edit:
                        ui.label("Read-only: your role cannot update devices.").classes("ht-small-copy")

                    with ui.row().classes("w-full gap-3"):
                        name_input = ui.input("Name", value=device.name).classes("flex-1").props("dense outlined")
                        type_select = (
                            ui.select(type_options, label="Type", value=device.type.value)
                            .classes("w-48")
                            .props("dense outlined")
                        )
                        status_select = (
                            ui.select(
                                status_options,
                                label="Status",
                                value=device.status.value,
                            )
                            .classes("w-48")
                            .props("dense outlined")
                        )

                    with ui.row().classes("w-full gap-3"):
                        ip_input = ui.input("IP", value=device.ip or "").classes("flex-1").props("dense outlined")
                        mac_input = ui.input("MAC", value=device.mac or "").classes("flex-1").props("dense outlined")
                        os_input = ui.input("OS", value=device.os or "").classes("flex-1").props("dense outlined")
                        power_input = (
                            ui.input("Power (W)", value="" if device.power_watts is None else str(device.power_watts))
                            .props("inputmode=numeric dense outlined")
                            .classes("w-40")
                        )

                    notes_input = (
                        ui.textarea("Notes", value=device.notes or "")
                        .props("autogrow outlined")
                        .classes("w-full")
                    )

                    error_label = ui.label("").style("font-size:0.82rem; color:var(--ht-error);")
                    error_label.set_visibility(False)

                    with ui.row().classes("w-full justify-end gap-2 pt-2"):
                        secondary_button(ui.button("Cancel", on_click=lambda: ui.navigate.to("/inventory")))
                        save_btn = primary_button(
                            ui.button("Save Changes", on_click=lambda: asyncio.ensure_future(_save()))
                        )
                        if not can_edit:
                            save_btn.props("disable")

        if not can_edit:
            for field in [
                name_input,
                type_select,
                status_select,
                ip_input,
                mac_input,
                os_input,
                power_input,
                notes_input,
            ]:
                field.props("readonly")

        async def _save() -> None:
            if not can_edit:
                return

            error_label.set_text("")
            error_label.set_visibility(False)

            name_value = str(name_input.value or "").strip()
            if not name_value:
                error_label.set_text("Name is required")
                error_label.set_visibility(True)
                return

            power_value = _clean_optional_int(str(power_input.value or ""))
            if isinstance(power_value, str):
                error_label.set_text("Power must be a whole number 0 or greater")
                error_label.set_visibility(True)
                return

            payload: dict[str, str | None | int] = {
                "name": name_value,
                "type": str(type_select.value or device.type.value),
                "status": str(status_select.value or device.status.value),
                "ip": _clean_optional(str(ip_input.value or "")),
                "mac": _clean_optional(str(mac_input.value or "")),
                "os": _clean_optional(str(os_input.value or "")),
                "notes": _clean_optional(str(notes_input.value or "")),
                "power_watts": power_value,
                "version": int(device.version),
            }

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.patch(
                        f"{settings.api_base_url}/api/devices/{device.id}",
                        json=payload,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=8.0,
                    )
            except httpx.HTTPError:
                error_label.set_text("Connection error while saving")
                error_label.set_visibility(True)
                return

            if resp.status_code == 200:
                show_toast(type="success", title="Device updated")
                ui.navigate.to("/inventory")
                return

            error_label.set_text(html.escape(_extract_error_detail(resp)))
            error_label.set_visibility(True)
