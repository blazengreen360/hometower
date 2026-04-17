"""Canvas network overlay JS bridge for topology network filtering/highlighting."""

from nicegui import ui

from src.ui.components.canvas_network_overlay_engine import _NETWORK_OVERLAY_ENGINE_JS

_NETWORK_OVERLAY_PUBLIC_JS = """
(function() {
    if (window._htNetworkOverlayApiLoaded) return;
    window._htNetworkOverlayApiLoaded = true;

    function _overlay() {
        return window._htNetworkOverlay || null;
    }

    window.htSetActiveNetworks = function(networkIds, colorMap) {
        var overlay = _overlay();
        if (!overlay) return;
        overlay.setActiveNetworks(networkIds || [], colorMap || {});
    };

    window.htApplyNetworkFilter = function(networkId, color) {
        var overlay = _overlay();
        if (!overlay) return;
        overlay.applyNetworkFilter(networkId, color);
    };

    window.htClearNetworkFilter = function() {
        var overlay = _overlay();
        if (!overlay) return;
        overlay.clear();
    };

    window.htRefreshNetworkOverlay = function() {
        var overlay = _overlay();
        if (!overlay) return;
        overlay.refresh();
    };

    window.htGetActiveNetworks = function() {
        var overlay = _overlay();
        if (!overlay) return [];
        return overlay.getActiveNetworks();
    };

    window.htPatchNodeNetworkMemberships = function(nodeId, memberships) {
        var overlay = _overlay();
        if (!overlay) return;
        overlay.patchNodeMemberships(nodeId, memberships || []);
    };
})();
"""

_NETWORK_OVERLAY_JS = _NETWORK_OVERLAY_ENGINE_JS + "\n" + _NETWORK_OVERLAY_PUBLIC_JS


def inject_network_overlay() -> None:
    """Inject network overlay helpers used by the topology network filter panel."""
    ui.add_body_html(f"<script>{_NETWORK_OVERLAY_ENGINE_JS}</script>")
    ui.add_body_html(f"<script>{_NETWORK_OVERLAY_PUBLIC_JS}</script>")
