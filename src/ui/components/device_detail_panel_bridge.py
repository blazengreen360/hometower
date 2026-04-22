"""JS bridge used by the device detail panel to react to canvas events."""

from src.ui.components.device_detail_panel_shell import build_panel_visibility_batch_js


_HIDE_DEVICE_PANEL_JS = build_panel_visibility_batch_js(("device-detail-panel",), False)
_HIDE_GHOST_PANEL_JS = build_panel_visibility_batch_js(("ghost-detail-panel",), False)
_HIDE_DEVICE_AND_GHOST_PANELS_JS = build_panel_visibility_batch_js(
    ("device-detail-panel", "ghost-detail-panel"), False
)

DEVICE_DETAIL_PANEL_BRIDGE_JS = """
(function() {
    if (window._htDetailBridgeInit) return;
    window._htDetailBridgeInit = true;
    document.addEventListener('ht:node-selected', function(evt) {
        var detail = evt && evt.detail && typeof evt.detail === 'object' ? evt.detail : {};
        var id = detail.id;
        var nodeData = detail.data && typeof detail.data === 'object' ? detail.data : {};
        var isGhost = !!nodeData.ghost;
        var devicePanel = document.getElementById('device-detail-panel');
        var ghostPanel = document.getElementById('ghost-detail-panel');

        if (isGhost) {
            __HIDE_DEVICE_PANEL_JS__
            if (id) {
                emitEvent('ghost_panel_select', {
                    ghost_id: String(nodeData.ghost_device_id || id),
                    ghost_original_name: String(nodeData.ghost_original_name || nodeData.raw_name || nodeData.label || 'Deleted device'),
                    ghost_original_type: String(nodeData.ghost_original_type || nodeData.raw_device_type || nodeData.device_type || 'Unknown'),
                    ghost_status: String(nodeData.ghost_status || 'Deleted from inventory')
                });
            }
            return;
        }

        __HIDE_GHOST_PANEL_JS__
        if (id) emitEvent('panel_select', {device_id: String(id), node_data: nodeData});
    });
    document.addEventListener('ht:edge-selected', function() {
        __HIDE_DEVICE_AND_GHOST_PANELS_JS__
    });
    document.addEventListener('ht:canvas-bg-click', function() {
        __HIDE_DEVICE_AND_GHOST_PANELS_JS__
    });
})();
""".replace("__HIDE_DEVICE_PANEL_JS__", _HIDE_DEVICE_PANEL_JS).replace(
    "__HIDE_GHOST_PANEL_JS__", _HIDE_GHOST_PANEL_JS
).replace("__HIDE_DEVICE_AND_GHOST_PANELS_JS__", _HIDE_DEVICE_AND_GHOST_PANELS_JS)
