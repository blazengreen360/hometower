"""Helpers for live device-network membership sync into the topology canvas."""

import json
import uuid

from nicegui import ui

from src.models.device_network import DeviceNetworkNetworkRef


def build_patch_node_network_memberships_js(
    device_id: uuid.UUID,
    memberships: list[DeviceNetworkNetworkRef],
) -> str:
    """Build JS that patches one node's network_memberships and refreshes overlay state."""
    payload = [
        {
            "network_id": str(membership.network_id),
            "name": membership.name,
            "color": membership.color,
            "ip_address": membership.ip_address,
        }
        for membership in memberships
    ]
    return (
        "if(window.htPatchNodeNetworkMemberships) window.htPatchNodeNetworkMemberships("
        + json.dumps(str(device_id))
        + ", "
        + json.dumps(payload)
        + ");"
    )


async def sync_canvas_device_network_memberships(
    device_id: uuid.UUID,
    memberships: list[DeviceNetworkNetworkRef],
) -> None:
    """Push latest memberships to the active Cytoscape node so overlay stays in sync."""
    await ui.run_javascript(build_patch_node_network_memberships_js(device_id, memberships))
