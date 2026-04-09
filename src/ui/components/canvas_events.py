"""Cytoscape.js canvas event handlers — palette drop, node CRUD, edge drawing.

Extracted from canvas.py to keep both files under the 250-line limit.

Defines ``window._htInitEventHandlers`` which is called by ``initCanvas``
in canvas.py after the Cytoscape instance (``window._cy``) is created.
"""
from nicegui import ui

_CANVAS_EVENTS_JS = """
(function() {
    if (typeof window._htInitEventHandlers !== 'undefined') return;

    window._htInitEventHandlers = function(deviceShapes) {
        var cy = window._cy;

        // Palette drop → create device via API and add node to canvas
        document.addEventListener('ht:palette-drop', function(evt) {
            var d = evt.detail;
            var token = sessionStorage.getItem('access_token');
            if (!token || !window._cy) return;
            fetch('/api/devices/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({ name: 'New ' + d.deviceType, type: d.deviceType })
            }).then(function(r) { return r.ok ? r.json() : null; })
              .then(function(device) {
                if (!device) return;
                window._cy.add({
                    data: {
                        id: String(device.id), label: device.name,
                        shape: deviceShapes[device.type] || 'rectangle',
                        device_type: device.type, ip: device.ip || '',
                        mac: device.mac || '', os: device.os || '', notes: device.notes || ''
                    },
                    position: { x: d.x, y: d.y }
                });
            });
        });

        // Node delete → remove device via API and from canvas
        document.addEventListener('ht:node-delete', function(evt) {
            var d = evt.detail;
            var token = sessionStorage.getItem('access_token');
            if (!token || !window._cy) return;
            fetch('/api/devices/' + d.id, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token }
            }).then(function(r) {
                if (r.ok || r.status === 404) {
                    window._cy.getElementById(d.id).remove();
                }
            });
        });

        // Node duplicate → clone device via API and add offset node
        document.addEventListener('ht:node-duplicate', function(evt) {
            var d = evt.detail;
            var token = sessionStorage.getItem('access_token');
            if (!token || !window._cy) return;
            var srcData = d.data || {};
            fetch('/api/devices/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({
                    name: (srcData.label || 'Device') + ' (copy)',
                    type: srcData.device_type || 'Server'
                })
            }).then(function(r) { return r.ok ? r.json() : null; })
              .then(function(device) {
                if (!device) return;
                var srcNode = window._cy.getElementById(d.id);
                var pos = srcNode.length ? srcNode.position() : { x: 200, y: 200 };
                window._cy.add({
                    data: {
                        id: String(device.id), label: device.name,
                        shape: deviceShapes[device.type] || 'rectangle',
                        device_type: device.type, ip: device.ip || '',
                        mac: device.mac || '', os: device.os || '', notes: device.notes || ''
                    },
                    position: { x: pos.x + 50, y: pos.y + 50 }
                });
            });
        });

        // Node edit → select node and open detail panel
        document.addEventListener('ht:node-edit', function(evt) {
            var d = evt.detail;
            if (window._cy) { window._cy.getElementById(d.id).select(); }
            document.dispatchEvent(
                new CustomEvent('ht:node-selected', { detail: d.data || d })
            );
        });

        // Edge drawing: shift+tap first node = source, shift+tap second = target → POST connection
        window._htEdgeSource = null;
        cy.on('tap', 'node', function(evt) {
            if (!evt.originalEvent || !evt.originalEvent.shiftKey) return;
            var node = evt.target;
            if (!window._htEdgeSource) {
                window._htEdgeSource = node.id();
                node.style('border-color', '#f59e0b');
                return;
            }
            var sourceId = window._htEdgeSource;
            var targetId = node.id();
            window._htEdgeSource = null;
            cy.nodes().style('border-color', '#a6adc8');
            if (sourceId === targetId) return;
            var token = sessionStorage.getItem('access_token');
            if (!token) return;
            fetch('/api/connections/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                body: JSON.stringify({ source_id: sourceId, target_id: targetId, type: 'Ethernet' })
            }).then(function(r) { return r.ok ? r.json() : null; })
              .then(function(conn) {
                if (!conn) return;
                window.addEdgeToCanvas({
                    id: conn.id, source: conn.source_id, target: conn.target_id,
                    label: conn.label || '', connection_type: conn.type
                });
            });
        });

        // Edge right-click → delete connection
        cy.on('cxttap', 'edge', function(evt) {
            var edge = evt.target;
            var token = sessionStorage.getItem('access_token');
            if (!token) return;
            fetch('/api/connections/' + edge.id(), {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token }
            }).then(function(r) { if (r.ok || r.status === 404) { edge.remove(); } });
        });
    };
})();
"""


def inject_canvas_events() -> None:
    """Inject canvas event-handler JavaScript into the page body."""
    ui.add_body_html(f"<script>{_CANVAS_EVENTS_JS}</script>")
