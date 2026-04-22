"""Cytoscape.js canvas event handlers for palette, node CRUD, and edge actions."""
from nicegui import ui

from src.ui.components.canvas_container_events import CANVAS_CONTAINER_EVENTS_JS
from src.ui.components.canvas_draft import CANVAS_DRAFT_JS
from src.ui.components.canvas_draft_events import CANVAS_DRAFT_EVENTS_JS
from src.ui.components.canvas_draft_form import CANVAS_DRAFT_FORM_JS
from src.ui.components.canvas_draft_publish import CANVAS_DRAFT_PUBLISH_JS
from src.ui.components.canvas_js_helpers import CANVAS_HELPERS_JS
from src.ui.components.device_detail_panel_shell import (
    RIGHT_RAIL_PANEL_IDS,
    build_panel_visibility_batch_js,
)
from src.ui.components.stencils_panel_js import STENCIL_DROP_HANDLER_JS

_CLOSE_RIGHT_RAIL_JS = build_panel_visibility_batch_js(RIGHT_RAIL_PANEL_IDS, False)

_CANVAS_EVENTS_JS = """
(function() {
    if (typeof window._htInitEventHandlers !== 'undefined') return;

    window._htInitEventHandlers = function(deviceShapes) {
        var cy = window._cy;
""" + CANVAS_HELPERS_JS + """
        document.addEventListener('ht:palette-drop', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail;
            if (!window._cy) return;

            var zoom = window._cy.zoom();
            var pan  = window._cy.pan();
            var container = document.getElementById('cy');
            var rect = container ? container.getBoundingClientRect() : {left:0,top:0};
            var screenX = d.screenX || (d.x * zoom + pan.x + rect.left);
            var screenY = d.screenY || (d.y * zoom + pan.y + rect.top);

            window._htShowDraftForm({
                deviceType: d.deviceType,
                x: d.x,
                y: d.y,
                screenX: screenX,
                screenY: screenY,
                deviceShapes: deviceShapes
            }, function onSubmit(fields) {
                window._htDraftId = window._htDraftId || function() { return 'draft-' + crypto.randomUUID(); };
                var draftId = window._htDraftId();
                var shape = deviceShapes[fields.type] || 'rectangle';
                var nodeDefn = window._htBuildDraftNode({
                    id: draftId,
                    name: fields.name,
                    type: fields.type,
                    ip: fields.ip,
                    mac: fields.mac,
                    os: fields.os,
                    notes: fields.notes,
                    shape: shape,
                    x: d.x,
                    y: d.y
                });
                window._cy.add(nodeDefn);
                if (window._htUpdateDraftBadge) window._htUpdateDraftBadge();
                if (window.scheduleAutosave) window.scheduleAutosave(800);
            }, function onCancel() {
            });
        });

        document.addEventListener('ht:node-delete', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail;
            if (!window._cy) return;

            if (window._htIsDraft && window._htIsDraft(d.id)) {
                var draftName = (d && (d.name || (d.data && (d.data.raw_name || d.data.label)) || d.id)) || 'this draft';
                _confirmDelete("Delete draft '" + _escapeHtml(draftName) + "'? This cannot be undone.", function() {
                    var el = window._cy.getElementById(d.id);
                    if (el.length > 0 && window._htCommitLocalDraftDelete) {
                        window._htCommitLocalDraftDelete(el);
                    }
                    if (window._htUpdateDraftBadge) window._htUpdateDraftBadge();
                });
                return;
            }

            var deviceName = (d && (d.name || (d.data && (d.data.raw_name || d.data.label)) || d.id)) || 'this device';
            _confirmDelete("Delete device '" + _escapeHtml(deviceName) + "'? This cannot be undone.", function() {
                if (!window._htRequestCanvasAction) return;
                window._htRequestCanvasAction({
                    type: 'delete_published_node',
                    payload: {
                        device_id: d.id,
                        active_diagram_id: window._htDiagramId || null,
                        active_node: window._htSnapshotNodeSet
                            ? window._htSnapshotNodeSet(window._cy.getElementById(d.id))
                            : null
                    }
                });
            });
        });

        document.addEventListener('ht:edge-delete', function(evt) {
            if (window.HT_READONLY) return;
            _deleteAssociation(evt.detail || {});
        });

        document.addEventListener('ht:node-duplicate', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail;
            if (!window._cy) return;
            if (window._htIsDraft && window._htIsDraft(d.id)) {
                _notify('Publish the draft first before duplicating.', 'warning');
                return;
            }
            var srcData = d.data || {};
            var baseName = srcData.raw_name || srcData.label || 'Device';
            fetch('/api/devices/', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: baseName + ' (copy)',
                    type: srcData.raw_device_type || srcData.device_type || 'Server'
                })
            }).then(function(r) { return r.ok ? r.json() : null; })
              .then(function(device) {
                if (!device) return;
                var rawName = device.name || '';
                var escapedName = _escapeHtml(rawName);
                var rawType = device.type || '';
                var escapedType = _escapeHtml(rawType);
                var srcNode = window._cy.getElementById(d.id);
                var pos = srcNode.length ? srcNode.position() : { x: 200, y: 200 };
                window._cy.add({
                    data: {
                        id: String(device.id),
                        label: escapedName,
                        raw_name: rawName,
                        version: Number(device.version || 1),
                        shape: deviceShapes[device.type] || 'rectangle',
                        device_type: escapedType,
                        raw_device_type: rawType,
                        status: _escapeHtml(device.status || 'Active'),
                        ip: _escapeHtml(device.ip || ''),
                        mac: _escapeHtml(device.mac || ''),
                        os: _escapeHtml(device.os || ''),
                        notes: _escapeHtml(device.notes || '')
                    },
                    position: { x: pos.x + 50, y: pos.y + 50 }
                });
            });
        });

        document.addEventListener('ht:node-edit', function(evt) {
            var d = evt.detail;
            if (window._cy) { window._cy.getElementById(d.id).select(); }
            document.dispatchEvent(
                new CustomEvent('ht:node-selected', { detail: {
                    id: d.id,
                    data: d.data || d
                }})
            );
        });

        document.addEventListener('ht:association-source', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail || {};
            if (!d.id) return;
            _startAssociation(String(d.id));
        });

        document.addEventListener('ht:association-target', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail || {};
            var targetId = d.id;
            var sourceId = window._htEdgeSource;
            if (!sourceId || !targetId) return;
            _clearAssociationSelection();
            if (sourceId === targetId) {
                _notify('Pick a different target device for the association.', 'warning');
                return;
            }
            _createAssociation(sourceId, targetId);
        });

        document.addEventListener('ht:canvas-bg-click', function() {
            _clearAssociationSelection();
        });

        window._htEdgeSource = null;

        cy.on('cxttap', 'edge', function(evt) {
            if (window.HT_READONLY) return;
            var edge = evt.target;
            _deleteAssociation({
                id: edge.id(),
                label: edge.data('label'),
                raw_label: edge.data('raw_label')
            });
        });

        document.addEventListener('ht:save-version', function() {
            var btn = Array.from(document.querySelectorAll('button')).find(function(b) {
                return b.innerText && b.innerText.trim() === 'Save Version';
            });
            if (btn) btn.click();
        });

        document.addEventListener('ht:close-panel', function() {
            """ + _CLOSE_RIGHT_RAIL_JS + """
            _clearAssociationSelection();
        });
""" + CANVAS_DRAFT_EVENTS_JS + CANVAS_CONTAINER_EVENTS_JS + STENCIL_DROP_HANDLER_JS + """
    };
})();
"""

def inject_canvas_events() -> None:
    """Inject canvas event-handler JavaScript into the page body."""
    ui.add_body_html(f"<script>{CANVAS_DRAFT_JS}</script>")
    ui.add_body_html(f"<script>{CANVAS_DRAFT_FORM_JS}</script>")
    ui.add_body_html(f"<script>{CANVAS_DRAFT_PUBLISH_JS}</script>")
    ui.add_body_html(f"<script>{_CANVAS_EVENTS_JS}</script>")
