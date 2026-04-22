"""Unit tests for topology network panel bridge wiring."""

import inspect

from src.ui.components import device_detail_panel
from src.ui.components import device_detail_panel_content
from src.ui.components import topology_network_panel


def test_panel_pushes_active_network_set_to_bridge() -> None:
    source = inspect.getsource(topology_network_panel.render_network_filter_panel)
    assert "render_network_highlight_controls(networks, sync_empty_state=True)" in source


def test_option_label_includes_vlan_when_present() -> None:
    label = topology_network_panel._option_label(
        {
            "name": "Management",
            "vlan_id": 10,
            "cidr": "10.0.10.0/24",
            "device_count": 4,
        }
    )
    assert "VLAN 10" in label
    assert "10.0.10.0/24" in label


def test_panel_uses_token_fallback_color_not_hardcoded_hex() -> None:
    source = inspect.getsource(topology_network_panel.render_network_filter_panel)
    assert "#22d3ee" not in source
    assert topology_network_panel._DEFAULT_NETWORK_COLOR == "var(--ht-accent)"
    assert "_network_color(" in source


def test_build_network_filter_records_keeps_membership_only_networks() -> None:
    source = inspect.getsource(topology_network_panel.build_network_filter_records)
    assert "for network in all_networks:" in source
    assert "for membership in memberships:" in source
    assert '"device_count": 0' in source
    assert "if network_id in seen:" in source


def test_read_active_network_ids_sanitizes_bridge_values() -> None:
    source = inspect.getsource(topology_network_panel.read_active_network_ids)
    assert "window.htGetActiveNetworks ? window.htGetActiveNetworks() : []" in source
    assert "_sanitize_active_ids(raw_ids)" in source


def test_device_networks_section_embeds_inline_highlight_controls() -> None:
    source = inspect.getsource(device_detail_panel_content.render_network_section)
    assert 'aria-label="Device networks"' in source
    assert '_section_label("Memberships")' in source
    assert '_section_label("Canvas Highlights")' in source
    assert "render_network_highlight_controls(" in source
    assert "build_network_filter_records(all_networks, device.networks)" in source
    assert "inline=True" in source


def test_device_detail_panel_reads_active_networks_for_integrated_networks_section() -> None:
    source = inspect.getsource(device_detail_panel.render_detail_panel)
    assert "all_networks = await _api_get_all_networks(token)" in source
    assert "active_network_ids = await read_active_network_ids()" in source
    assert 'with ui.expansion("Networks", icon="lan", value=True)' in source
    assert "render_network_section(" in source
