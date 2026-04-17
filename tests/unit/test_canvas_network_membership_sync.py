"""Unit tests for live canvas membership sync from the device detail panel."""

import inspect
import uuid

from src.models.device_network import DeviceNetworkNetworkRef
from src.ui.components import device_detail_panel
from src.ui.components.canvas_network_membership_sync import (
    build_patch_node_network_memberships_js,
)


def test_build_patch_node_network_memberships_js_includes_membership_payload() -> None:
    device_id = uuid.uuid4()
    memberships = [
        DeviceNetworkNetworkRef(
            network_id=uuid.uuid4(),
            name="Management",
            vlan_id=10,
            cidr="10.0.10.0/24",
            gateway="10.0.10.1",
            color="#3b82f6",
            ip_address="10.0.10.25",
        )
    ]

    script = build_patch_node_network_memberships_js(device_id, memberships)
    assert "htPatchNodeNetworkMemberships" in script
    assert str(device_id) in script
    assert "network_id" in script
    assert "Management" in script


def test_device_detail_panel_triggers_canvas_membership_sync() -> None:
    source = inspect.getsource(device_detail_panel.render_detail_panel)
    assert "sync_canvas_device_network_memberships" in source
