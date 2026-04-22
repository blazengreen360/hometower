"""Device detail panel — interactive right-side panel for node selection (HT-010)."""
import asyncio
from collections.abc import Awaitable, Callable
import html
import uuid

import httpx
from nicegui import ui

from src.models.device import DeviceResponseEnriched
from src.ui.components.device_detail_container import (
    _api_get_attachments,
    _api_get_all_tags,
    _api_get_all_networks,
    _api_get_connections,
    _api_get_device,
    render_children_section,
    render_parent_breadcrumb,
)
from src.ui.components.device_detail_draft import show_draft_panel
from src.ui.components.device_detail_duplicate import duplicate_device
from src.ui.components.device_detail_panel_bridge import DEVICE_DETAIL_PANEL_BRIDGE_JS
from src.ui.components.device_detail_panel_content import (
    render_attachments_block,
    render_connections_block,
    render_custom_fields_block,
    render_general_content,
    render_location_content,
    render_network_section,
    render_status_content,
    render_tags_block,
)
from src.ui.components.device_detail_panel_shell import (
    build_detail_panel,
    build_neighbor_names,
    build_panel_visibility_js,
    handle_panel_select,
    push_device_field_change,
)
from src.ui.components.canvas_network_membership_sync import (
    sync_canvas_device_network_memberships,
)
from src.ui.components.topology_network_panel import read_active_network_ids
from src.ui.components.toast import show_toast
from src.utils.logger import logger
from src.utils.settings import settings

_ROLES_WITH_EDIT = {"Admin", "Contributor"}


def render_detail_panel(token: str, user_role: str) -> None:
    """Render the device detail panel. Called from topology page with token and role."""
    is_editor: bool = user_role in _ROLES_WITH_EDIT
    state: dict[str, object] = {"device_id": None, "last_device": None}

    ui.add_body_html(f"<script>{DEVICE_DETAIL_PANEL_BRIDGE_JS}</script>")

    async def _on_duplicate() -> None:
        device = state.get("last_device")
        if isinstance(device, DeviceResponseEnriched):
            new_id = await duplicate_device(token, device)
            if new_id is not None:
                state["device_id"] = new_id
                await _refresh()

    async def _close() -> None:
        await ui.run_javascript(build_panel_visibility_js("device-detail-panel", False))
        state["device_id"] = state["last_device"] = None

    live_lbl, content = build_detail_panel(is_editor, _on_duplicate, _close)

    async def _refresh() -> None:
        raw = state["device_id"]
        if not isinstance(raw, uuid.UUID):
            return
        did: uuid.UUID = raw
        device = await _api_get_device(
            token, did, include="location,tags,custom_fields,children,ancestors,networks"
        )
        if device is None:
            return
        state["last_device"] = device
        await sync_canvas_device_network_memberships(did, device.networks)
        parent_chain = device.parent_chain
        children_list = device.children
        connections = await _api_get_connections(token, did)
        attachments = await _api_get_attachments(token, did)
        all_tags = await _api_get_all_tags(token) if is_editor else []
        all_networks = await _api_get_all_networks(token)
        active_network_ids = await read_active_network_ids()
        neighbor_names = await build_neighbor_names(
            did, connections, lambda neighbor_id: _api_get_device(token, neighbor_id)
        )

        async def _save_device_field(
            field: str,
            before_value: object,
            after_value: object,
            label: str,
        ) -> bool:
            if before_value == after_value:
                return True

            try:
                async with httpx.AsyncClient() as c:
                    response = await c.patch(
                        f"{settings.api_base_url}/api/devices/{did}",
                        json={field: after_value, "version": device.version},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5.0,
                    )
            except httpx.HTTPError as exc:
                logger.error("Device detail PATCH {}: {}", field, str(exc))
                show_toast(type="error", title="Connection error")
                return False

            if response.status_code != 200:
                show_toast(type="error", title=f"{label} update failed")
                return False

            parsed_body = response.json()
            body = parsed_body if isinstance(parsed_body, dict) else {}
            raw_version = body.get("version", device.version)
            try:
                next_version = int(raw_version)
            except (TypeError, ValueError):
                next_version = device.version
            device.version = next_version
            await push_device_field_change(
                did,
                field,
                before_value,
                after_value,
                next_version,
                label,
                "update_device_field",
            )

            show_toast(type="success", title=f"{label} updated")
            return True

        def _save_callback(
            field: str,
            before_value: object,
            label: str,
        ) -> Callable[[object], Awaitable[bool]]:
            async def _save_value(next_value: object) -> bool:
                return await _save_device_field(field, before_value, next_value, label)

            return _save_value

        def _on_change() -> None:
            asyncio.ensure_future(_refresh())

        async def _on_status_change(e: object) -> None:
            value = getattr(e, "value", None)
            if isinstance(value, str) and await _save_device_field(
                "status", device.status.value, value, "Status"
            ):
                _on_change()

        _on_attachments_change = _refresh
        content.clear()
        with content:
            render_parent_breadcrumb(parent_chain, state, _refresh)

            with ui.expansion("General", icon="info_outline", value=True).classes("w-full"):
                render_general_content(
                    device,
                    did,
                    token,
                    is_editor,
                    device.version,
                    _on_change,
                    save_value=_save_callback("name", device.name, "Name"),
                    save_notes=_save_callback("notes", device.notes, "Notes"),
                    power_label="Power (W)",
                    save_power=_save_callback("power_watts", device.power_watts, "Power"),
                )

            with ui.expansion("Networks", icon="lan", value=True).classes("w-full"):
                render_network_section(
                    device,
                    did,
                    token,
                    is_editor,
                    device.version,
                    _on_change,
                    _save_callback("ip", device.ip, "IP"),
                    _save_callback("mac", device.mac, "MAC"),
                    _save_callback("os", device.os, "OS"),
                    all_networks,
                    active_network_ids,
                )

            with ui.expansion("Status", icon="circle", value=True).classes("w-full"):
                render_status_content(device, is_editor, _on_status_change)

            with ui.expansion("Location", icon="location_on", value=True).classes("w-full"):
                render_location_content(device)

            with ui.expansion("Tags", icon="label", value=True).classes("w-full"):
                render_tags_block(did, device.tags, all_tags, token, is_editor, _on_change)

            with ui.expansion("Custom Fields", icon="tune", value=True).classes("w-full"):
                render_custom_fields_block(device, token, is_editor, _on_change)

            with ui.expansion("Attachments", icon="attach_file", value=True).classes("w-full"):
                render_attachments_block(
                    did,
                    attachments,
                    token,
                    is_editor,
                    _on_attachments_change,
                )

            with ui.expansion("Connections", icon="device_hub", value=True).classes("w-full"):
                render_connections_block(did, connections, neighbor_names)

            render_children_section(children_list, state, _refresh)

        await ui.run_javascript(build_panel_visibility_js("device-detail-panel", True))
        live_lbl.set_text(f"Loaded {html.escape(device.name)}")

    async def _on_panel_select(e: object) -> None:
        await handle_panel_select(
            e,
            state,
            content,
            _refresh,
            show_draft_panel,
            lambda raw_id: logger.warning("panel_select: invalid UUID {!r}", raw_id),
        )

    ui.on("panel_select", _on_panel_select)
