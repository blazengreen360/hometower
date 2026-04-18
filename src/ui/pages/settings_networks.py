"""Settings — Networks management page at /settings/networks."""
import html
from typing import Optional

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_insufficient_role, redirect_if_unauthenticated
from src.ui.components.network_modal import NetworkModalController, create_network_modal
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import table_surface
from src.ui.design.tokens import DEFAULT_NETWORK_COLOR
from src.ui.pages.settings_page_helpers import show_destructive_confirmation
from src.utils.logger import logger
from src.utils.settings import settings

_API = f"{settings.api_base_url}/api/networks/"

def _auth_headers() -> dict[str, str]:
    token = nicegui_app.storage.user.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _clean_optional(value: str) -> Optional[str]:
    return value.strip() or None


def _parse_vlan(vlan_raw: str) -> int | None:
    cleaned = vlan_raw.strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError("VLAN ID must be an integer") from exc


@ui.page("/settings/networks")
async def settings_networks_page() -> None:
    """Network settings page for creating and managing network definitions."""
    if redirect_if_unauthenticated(current_path="/settings/networks"):
        return
    if redirect_if_insufficient_role(Role.Contributor):
        return

    networks: list[dict[str, object]] = []
    modal_mode = {"value": "create"}
    editing_id: dict[str, Optional[str]] = {"value": None}
    form: dict[str, str] = {
        "name": "",
        "vlan_id": "",
        "cidr": "",
        "gateway": "",
        "description": "",
        "color": DEFAULT_NETWORK_COLOR,
    }
    modal: NetworkModalController

    def _to_rows(items: list[dict[str, object]]) -> list[dict[str, object]]:
        return [{
            "id": str(item.get("id", "")),
            "name": str(item.get("name", "")),
            "vlan_id": "" if item.get("vlan_id") is None else str(item.get("vlan_id")),
            "cidr": str(item.get("cidr", "")),
            "gateway": str(item.get("gateway", "") or ""),
            "description": str(item.get("description", "") or ""),
            "color": str(item.get("color", "")),
            "device_count": _coerce_count(item.get("device_count", 0)),
        } for item in items]

    def _coerce_count(raw_count: object) -> int:
        if isinstance(raw_count, int):
            return raw_count
        if isinstance(raw_count, str) and raw_count.isdigit():
            return int(raw_count)
        return 0

    def _reset_form() -> None:
        form.update({"name": "", "vlan_id": "", "cidr": "", "gateway": "", "description": "", "color": DEFAULT_NETWORK_COLOR})
        modal.clear_error()

    async def load_networks() -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(_API, headers=_auth_headers(), timeout=6.0)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, list):
                payload = []
            networks.clear()
            for row in payload:
                if isinstance(row, dict):
                    networks.append(row)
            table.rows = _to_rows(networks)
            table.update()
        except Exception as exc:
            logger.error("Failed to load networks: {}", exc)

    def open_create_modal() -> None:
        _reset_form()
        modal_mode["value"] = "create"
        editing_id["value"] = None
        modal.open_for_mode("create")

    def open_edit_modal(row: dict[str, object]) -> None:
        _reset_form()
        form["name"] = str(row.get("name", ""))
        form["vlan_id"] = str(row.get("vlan_id", ""))
        form["cidr"] = str(row.get("cidr", ""))
        form["gateway"] = str(row.get("gateway", ""))
        form["description"] = str(row.get("description", ""))
        form["color"] = str(row.get("color", "") or DEFAULT_NETWORK_COLOR)
        modal_mode["value"] = "edit"
        editing_id["value"] = str(row.get("id", ""))
        modal.open_for_mode("edit")

    async def submit_form() -> None:
        modal.clear_error()
        name_value = form["name"].strip()
        cidr_value = form["cidr"].strip()
        color_value = form["color"].strip() or DEFAULT_NETWORK_COLOR
        if not name_value:
            modal.set_error("Name is required")
            return
        if not cidr_value:
            modal.set_error("CIDR is required")
            return

        try:
            payload: dict[str, object] = {
                "name": name_value,
                "vlan_id": _parse_vlan(form["vlan_id"]),
                "cidr": cidr_value,
                "gateway": _clean_optional(form["gateway"]),
                "description": _clean_optional(form["description"]),
                "color": color_value,
            }
        except ValueError as exc:
            modal.set_error(str(exc))
            return

        try:
            async with httpx.AsyncClient() as client:
                if modal_mode["value"] == "create":
                    resp = await client.post(_API, json=payload, headers=_auth_headers(), timeout=6.0)
                else:
                    resp = await client.patch(
                        f"{_API}{editing_id['value']}",
                        json=payload,
                        headers=_auth_headers(),
                        timeout=6.0,
                    )
            if resp.status_code in (200, 201):
                modal.close()
                ui.notify("Saved", type="positive")
                await load_networks()
                return
            detail = resp.json().get("detail", "Unknown error")
            modal.set_error(str(detail))
        except Exception as exc:
            logger.error("Network save failed: {}", exc)
            modal.set_error("Request failed - check logs")

    def confirm_delete(network_id: str, network_name: str) -> None:
        async def do_delete() -> None:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.delete(
                        f"{_API}{network_id}",
                        headers=_auth_headers(),
                        timeout=6.0,
                    )
                if resp.status_code == 204:
                    ui.notify(f"Deleted '{html.escape(network_name)}'", type="positive")
                    await load_networks()
                    return
                detail = resp.json().get("detail", "Delete failed")
                ui.notify(html.escape(str(detail)), type="negative")
            except Exception as exc:
                logger.error("Network delete failed: {}", exc)

        show_destructive_confirmation(
            ui_module=ui,
            title=f"Delete '{html.escape(network_name)}'?",
            description="If devices are attached, delete will be blocked until memberships are removed.",
            on_confirm=do_delete,
        )

    with app_shell("Networks", "/settings/networks", breadcrumb=["Settings", "Networks"]):
        with page_container(ui.column()):
            with ui.row().classes("w-full items-end justify-between gap-4 flex-wrap"):
                render_page_intro(
                    ui,
                    "Networks",
                    "Maintain VLAN, CIDR, gateway, and color metadata so devices and IPAM share a consistent network catalog.",
                    "Settings",
                )
                primary_button(ui.button("+ Add Network", on_click=open_create_modal))

            columns: list[dict[str, str | bool]] = [
                {"name": "name", "label": "Name", "field": "name", "sortable": True},
                {"name": "vlan_id", "label": "VLAN", "field": "vlan_id", "sortable": True},
                {"name": "cidr", "label": "CIDR", "field": "cidr"},
                {"name": "gateway", "label": "Gateway", "field": "gateway"},
                {"name": "color", "label": "Color", "field": "color"},
                {"name": "device_count", "label": "Devices", "field": "device_count", "sortable": True},
                {"name": "actions", "label": "Actions", "field": "actions"},
            ]

            table = table_surface(ui.table(columns=columns, rows=[], row_key="id"))

            table.add_slot(
                "body-cell-color",
                """
                <q-td :props="props">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span :style="'width:12px;height:12px;border-radius:999px;display:inline-block;background:'+props.row.color"></span>
                    <span>{{ props.row.color }}</span>
                  </div>
                </q-td>
                """,
            )
            table.add_slot(
                "body-cell-actions",
                """
                <q-td :props="props">
                  <q-btn flat dense icon="edit" size="sm"
                    @click="$parent.$emit('edit', props.row)" />
                  <q-btn flat dense icon="delete" size="sm" class="ht-btn-icon-danger"
                    @click="$parent.$emit('delete_row', props.row)" />
                </q-td>
                """,
            )
            table.on("edit", lambda e: open_edit_modal(e.args))
            table.on(
                "delete_row",
                lambda e: ui.timer(
                    0,
                    lambda: confirm_delete(str(e.args["id"]), str(e.args["name"])),
                    once=True,
                ),
            ),

    modal = create_network_modal(form=form, on_submit=submit_form)
    await load_networks()
