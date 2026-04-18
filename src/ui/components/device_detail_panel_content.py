"""Content renderers for device detail panel sections."""

from collections.abc import Awaitable, Callable
import html
import uuid

from nicegui import ui

from src.models.attachment import DeviceAttachmentResponse
from src.models.connection import ConnectionResponse
from src.models.device import DeviceResponseEnriched
from src.models.device_network import DeviceNetworkNetworkRef
from src.models.network import NetworkListResponse
from src.models.tag import TagResponse
from src.models.types import DeviceStatus
from src.ui.components.device_detail_sections import (
    render_attachments_section,
    render_connections_section,
    render_custom_fields_section,
    render_networks_section,
    render_tags_section,
)
from src.ui.components.device_panel_rich_fields import (
    render_ip_quick_links,
    render_markdown_notes_row,
)
from src.ui.components.device_panel_helpers import render_editable_int_row, render_editable_row


def render_general_content(
    device: DeviceResponseEnriched,
    device_id: uuid.UUID,
    token: str,
    is_editor: bool,
    version: int,
    on_change: Callable[[], None],
    save_value: Callable[[object], Awaitable[bool]],
    save_notes: Callable[[object], Awaitable[bool]],
    power_label: str,
    save_power: Callable[[object], Awaitable[bool]],
) -> None:
    render_editable_row(
        "Name",
        device.name,
        "name",
        device_id,
        token,
        is_editor,
        version,
        on_change,
        save_value=save_value,
    )
    render_editable_row(
        "Type", device.type.value, "type", device_id, token, False, version
    )
    render_markdown_notes_row(
        device.notes,
        is_editor,
        on_saved=on_change,
        save_value=save_notes,
    )
    render_editable_int_row(
        power_label,
        device.power_watts,
        device_id,
        token,
        is_editor,
        version,
        on_change,
        save_value=save_power,
    )


def render_network_content(
    device: DeviceResponseEnriched,
    device_id: uuid.UUID,
    token: str,
    is_editor: bool,
    version: int,
    on_change: Callable[[], None],
    save_ip: Callable[[object], Awaitable[bool]],
    save_mac: Callable[[object], Awaitable[bool]],
    save_os: Callable[[object], Awaitable[bool]],
) -> None:
    render_editable_row(
        "IP",
        device.ip,
        "ip",
        device_id,
        token,
        is_editor,
        version,
        on_change,
        save_value=save_ip,
    )
    render_ip_quick_links(device.ip)
    render_editable_row(
        "MAC",
        device.mac,
        "mac",
        device_id,
        token,
        is_editor,
        version,
        on_change,
        save_value=save_mac,
    )
    render_editable_row(
        "OS",
        device.os,
        "os",
        device_id,
        token,
        is_editor,
        version,
        on_change,
        save_value=save_os,
    )


def render_network_memberships_block(
    device_id: uuid.UUID,
    networks: list[DeviceNetworkNetworkRef],
    all_networks: list[NetworkListResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    with ui.element("div").props('aria-label="Network memberships"').classes("w-full"):
        render_networks_section(device_id, networks, all_networks, token, is_editor, on_change)


def render_status_content(
    device: DeviceResponseEnriched,
    is_editor: bool,
    on_status_change: Callable[[object], Awaitable[None]],
) -> None:
    status_opts = [status.value for status in DeviceStatus]
    if is_editor:
        select = ui.select(options=status_opts, value=device.status.value).classes("w-full")
        select.on_value_change(on_status_change)
        return
    ui.label(device.status.value).style(
        "font-size:0.875rem; color:var(--ht-text-primary);"
    )


def render_location_content(device: DeviceResponseEnriched) -> None:
    ui.label(html.escape(device.location_name or "—")).style(
        "font-size:0.875rem; color:var(--ht-text-primary);"
    )


def render_tags_block(
    device_id: uuid.UUID,
    tags: list[TagResponse],
    all_tags: list[TagResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    with ui.element("div").props('aria-label="Device tags"').classes("w-full"):
        render_tags_section(device_id, tags, all_tags, token, is_editor, on_change)


def render_custom_fields_block(
    device: DeviceResponseEnriched,
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    with ui.element("div").props('aria-label="Custom fields"').classes("w-full"):
        render_custom_fields_section(
            device.id,
            device.custom_fields,
            token,
            is_editor,
            on_change,
        )


def render_attachments_block(
    device_id: uuid.UUID,
    attachments: list[DeviceAttachmentResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], Awaitable[None]],
) -> None:
    with ui.element("div").props('aria-label="Attachments"').classes("w-full"):
        render_attachments_section(device_id, attachments, token, is_editor, on_change)


def render_connections_block(
    device_id: uuid.UUID,
    connections: list[ConnectionResponse],
    neighbor_names: dict[uuid.UUID, str],
) -> None:
    with ui.element("div").props('aria-label="Connections"').classes("w-full"):
        render_connections_section(device_id, connections, neighbor_names)