"""JS bridge used by the device detail panel to react to canvas events."""

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
            if (devicePanel) devicePanel.style.display = 'none';
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

        if (ghostPanel) ghostPanel.style.display = 'none';
        if (id) emitEvent('panel_select', {device_id: String(id), node_data: nodeData});
    });
    document.addEventListener('ht:edge-selected', function() {
        var p = document.getElementById('device-detail-panel');
        if (p) p.style.display = 'none';
        var gp = document.getElementById('ghost-detail-panel');
        if (gp) gp.style.display = 'none';
    });
    document.addEventListener('ht:canvas-bg-click', function() {
        var p = document.getElementById('device-detail-panel');
        if (p) p.style.display = 'none';
        var gp = document.getElementById('ghost-detail-panel');
        if (gp) gp.style.display = 'none';
    });
})();
"""
