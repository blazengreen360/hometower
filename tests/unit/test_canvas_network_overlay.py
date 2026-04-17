"""Unit tests for topology network highlight overlay JS bridge."""

from src.ui.components.canvas_network_overlay import _NETWORK_OVERLAY_JS, inject_network_overlay


class TestCanvasNetworkOverlay:
    def test_overlay_exposes_multi_set_apply_and_clear_functions(self) -> None:
        assert "window.htSetActiveNetworks" in _NETWORK_OVERLAY_JS
        assert "window.htApplyNetworkFilter" in _NETWORK_OVERLAY_JS
        assert "window.htClearNetworkFilter" in _NETWORK_OVERLAY_JS
        assert "window.htGetActiveNetworks" in _NETWORK_OVERLAY_JS

    def test_overlay_uses_network_memberships_payload(self) -> None:
        assert "network_memberships" in _NETWORK_OVERLAY_JS
        assert "membership.network_id" in _NETWORK_OVERLAY_JS

    def test_overlay_toggles_match_and_dim_classes(self) -> None:
        assert "ht-network-match" in _NETWORK_OVERLAY_JS
        assert "ht-network-dim" in _NETWORK_OVERLAY_JS

    def test_overlay_renders_stacked_badges_for_active_memberships(self) -> None:
        assert "ht-network-badge-stack" in _NETWORK_OVERLAY_JS
        assert "ht-network-badge-dot" in _NETWORK_OVERLAY_JS
        assert "ht-network-badges" in _NETWORK_OVERLAY_JS

    def test_overlay_uses_token_driven_default_highlight_color(self) -> None:
        assert "#22d3ee" not in _NETWORK_OVERLAY_JS
        assert "--ht-accent" in _NETWORK_OVERLAY_JS

    def test_overlay_exposes_device_membership_patch_bridge(self) -> None:
        assert "window.htPatchNodeNetworkMemberships" in _NETWORK_OVERLAY_JS

    def test_inject_network_overlay_is_callable(self) -> None:
        assert callable(inject_network_overlay)
