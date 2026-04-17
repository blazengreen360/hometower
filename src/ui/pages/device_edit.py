"""Dedicated device editor page for inventory actions."""
import asyncio
import html
import uuid

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.device import DeviceResponseEnriched
from src.models.types import DeviceStatus, Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import get_ui_role, redirect_if_unauthenticated
from src.ui.components.device_type_options import get_editable_device_type_values
from src.ui.components.toast import show_toast
from src.utils.logger import logger
from src.utils.settings import settings


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_optional_int(value: str | None) -> int | str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = int(stripped)
    except ValueError:
        return stripped
    if parsed < 0:
        return stripped
    return parsed


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


async def _load_device(token: str, device_id: uuid.UUID) -> DeviceResponseEnriched | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.api_base_url}/api/devices/{device_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8.0,
            )
    except httpx.HTTPError as exc:
        logger.error("Inventory editor load failed: {}", str(exc))
        return None

    if resp.status_code != 200:
        logger.warning("Inventory editor load status={} id={}", resp.status_code, str(device_id))
        return None

    try:
        return DeviceResponseEnriched.model_validate(resp.json())
    except Exception as exc:
        logger.error("Inventory editor parse failed: {}", str(exc))
        return None


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
            ui.label("Invalid device id").classes("text-negative")
            ui.button("Back to Inventory", on_click=lambda: ui.navigate.to("/inventory"))
        return

    device = await _load_device(token, parsed_device_id)
    if device is None:
        with app_shell("Edit Device", "/inventory", breadcrumb=["Inventory", "Edit Device"]):
            ui.label("Device not found or unavailable").classes("text-negative")
            ui.button("Back to Inventory", on_click=lambda: ui.navigate.to("/inventory"))
        return

    type_options = get_editable_device_type_values(device.type)
    status_options = [status.value for status in DeviceStatus]

    with app_shell("Edit Device", "/inventory", breadcrumb=["Inventory", "Edit Device"]):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Edit Device").style("font-size:1.5rem; font-weight:700;")
            with ui.row().classes("gap-2"):
                ui.button("Back to Inventory", on_click=lambda: ui.navigate.to("/inventory")).props("flat")
                ui.button("Open in Topology", on_click=lambda: ui.navigate.to(f"/topology?device_id={device.id}")).props(
                    "flat icon=account_tree"
                )

        ui.label(f"Device ID: {device.id}").style("font-size:0.82rem; color:var(--ht-text-secondary);")

        if not can_edit:
            ui.label("Read-only: your role cannot update devices.").style(
                "font-size:0.82rem; color:var(--ht-text-secondary);"
            )

        with ui.row().classes("w-full gap-3"):
            name_input = ui.input("Name", value=device.name).classes("flex-1")
            type_select = ui.select(type_options, label="Type", value=device.type.value).classes("w-48")
            status_select = ui.select(
                status_options,
                label="Status",
                value=device.status.value,
            ).classes("w-48")

        with ui.row().classes("w-full gap-3"):
            ip_input = ui.input("IP", value=device.ip or "").classes("flex-1")
            mac_input = ui.input("MAC", value=device.mac or "").classes("flex-1")
            os_input = ui.input("OS", value=device.os or "").classes("flex-1")
            power_input = (
                ui.input("Power (W)", value="" if device.power_watts is None else str(device.power_watts))
                .props("inputmode=numeric")
                .classes("w-40")
            )

        notes_input = ui.textarea("Notes", value=device.notes or "").props("autogrow").classes("w-full")

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
            except httpx.HTTPError as exc:
                logger.error("Inventory editor save failed: {}", str(exc))
                error_label.set_text("Connection error while saving")
                error_label.set_visibility(True)
                return

            if resp.status_code == 200:
                show_toast(type="success", title="Device updated")
                ui.navigate.to("/inventory")
                return

            error_label.set_text(html.escape(_extract_error_detail(resp)))
            error_label.set_visibility(True)

        with ui.row().classes("w-full justify-end gap-2 pt-2"):
            ui.button("Cancel", on_click=lambda: ui.navigate.to("/inventory")).props("flat")
            save_btn = ui.button("Save Changes", on_click=lambda: asyncio.ensure_future(_save())).props("color=primary")
            if not can_edit:
                save_btn.props("disable")
