"""Unit tests for topology network panel bridge wiring."""

import inspect

from src.ui.components import topology_network_panel


def test_panel_pushes_active_network_set_to_bridge() -> None:
    source = inspect.getsource(topology_network_panel.render_network_filter_panel)
    assert "htSetActiveNetworks" in source


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
