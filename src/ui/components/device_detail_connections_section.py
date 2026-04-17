"""Connections section renderer for the device detail panel."""
import html
import uuid

from nicegui import ui

from src.models.connection import ConnectionResponse



def render_connections_section(
    device_id: uuid.UUID,
    connections: list[ConnectionResponse],
    neighbor_names: dict[uuid.UUID, str],
) -> None:
    """List of connected devices with navigation links."""
    if not connections:
        ui.label("No connections").style(
            "font-size:0.875rem; color:var(--ht-text-secondary);"
        )
        return

    for conn in connections:
        nid = conn.target_id if conn.source_id == device_id else conn.source_id
        name = neighbor_names.get(nid, str(nid)[:8] + "\u2026")
        label_text = f"\u2194 {html.escape(name)} ({conn.type.value})"

        ui.button(
            label_text,
            on_click=lambda n=nid: ui.navigate.to(f"/topology?device_id={n}"),
        ).props("flat dense no-caps").style(
            "font-size:0.875rem; color:var(--ht-text-primary); "
            "text-align:left; justify-content:flex-start; width:100%;"
        )
