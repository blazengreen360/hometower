"""Draft publish helpers for the Cytoscape canvas."""

CANVAS_DRAFT_PUBLISH_JS: str = """
(function() {
    function _htRestoreDraftEdge(cy, edgeData) {
        if (cy.getElementById(edgeData.id).length !== 0) return true;
        var restoredEdge = cy.add({ group: 'edges', data: edgeData });
        return restoredEdge.length === 1;
    }

    function _htRollbackPublishedDraft(cy, draftId, newId, draftClasses, oldData, pos, connectedEdges, replacementEdgeIds) {
        replacementEdgeIds.forEach(function(edgeId) {
            var edge = cy.getElementById(edgeId);
            if (edge.length) edge.remove();
        });
        var newNode = cy.getElementById(newId);
        if (newNode.length) newNode.remove();

        if (cy.getElementById(draftId).length === 0) {
            var restoredNode = cy.add({
                group: 'nodes',
                data: oldData,
                position: { x: pos.x, y: pos.y },
                classes: draftClasses
            });
            if (restoredNode.length !== 1) {
                window._htShowGraphCorruption();
                return false;
            }
        }

        var restoredEdges = connectedEdges.every(function(edgeData) {
            if (_htRestoreDraftEdge(cy, edgeData)) return true;
            window._htShowGraphCorruption();
            return false;
        });
        return restoredEdges && cy.getElementById(draftId).length === 1;
    }

    function _htBuildReplacementEdge(edgeData, draftId, newId) {
        var replacementEdge = Object.assign({}, edgeData);
        if (replacementEdge.source === draftId) replacementEdge.source = newId;
        if (replacementEdge.target === draftId) replacementEdge.target = newId;
        return replacementEdge;
    }

    function _htPrunePromotedDraftEdges(cy, node) {
        node.connectedEdges().forEach(function(edge) {
            if (!(window._htIsDraftEdge && window._htIsDraftEdge(edge.data()))) return;
            var src = edge.data('source');
            var tgt = edge.data('target');
            if (!window._htIsDraft(src) && !window._htIsDraft(tgt) && window._htHasPersistedConnection(cy, src, tgt)) edge.remove();
        });
    }

    window._htPublishDraft = function(draftId) {
        var cy = window._cy;
        if (!cy) return Promise.resolve(false);
        var node = cy.getElementById(draftId);
        if (!node.length) return Promise.resolve(false);
        var d = node.data();

        var payload = {
            name:   d.draft_name || d.raw_name,
            type:   d.draft_type || d.raw_device_type,
            ip:     d.draft_ip   || null,
            mac:    d.draft_mac  || null,
            os:     d.draft_os   || null,
            notes:  d.draft_notes || null
        };
        ['ip','mac','os','notes'].forEach(function(k) {
            if (payload[k] === '') payload[k] = null;
        });

        return fetch('/api/devices/', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function(r) {
            if (!r.ok) return r.json().catch(function() {
                return {};
            }).then(function(b) {
                throw new Error(b.detail || 'Publish failed');
            });
            return r.json();
        })
        .then(function(device) {
            var newId = String(device.id);
            var pos = node.position();
            var oldData = Object.assign({}, node.data());
            var draftClasses = node.classes();
            var oldClasses = node.classes().filter(function(c) {
                return c !== 'draft' && c !== 'draft-error';
            }).join(' ');
            var connectedEdges = [];
            node.connectedEdges().forEach(function(edge) {
                connectedEdges.push(Object.assign({}, edge.data()));
            });
            node.remove();
            var newData = {
                id: newId,
                label: window._htEscapeHtml(device.name || ''),
                raw_name: device.name || '',
                version: Number(device.version || 1),
                shape: oldData.shape || 'rectangle',
                device_type: window._htEscapeHtml(device.type || oldData.raw_device_type || ''),
                raw_device_type: device.type || oldData.raw_device_type || '',
                status: window._htEscapeHtml(device.status || 'Active'),
                ip: window._htEscapeHtml(device.ip || ''),
                mac: window._htEscapeHtml(device.mac || ''),
                os: window._htEscapeHtml(device.os || ''),
                notes: window._htEscapeHtml(device.notes || '')
            };
            if (oldData.parent) newData.parent = oldData.parent;
            var addedNode = cy.add({
                group: 'nodes',
                data: newData,
                position: { x: pos.x, y: pos.y },
                classes: oldClasses
            });
            if (addedNode.length !== 1 || cy.getElementById(newId).length !== 1) {
                var nodeError = new Error('Node replacement verification failed');
                if (!_htRollbackPublishedDraft(cy, draftId, newId, draftClasses, oldData, pos, connectedEdges, [])) {
                    nodeError.htCorruptGraph = true;
                }
                throw nodeError;
            }
            var replacementEdgeIds = [];
            var edgesRestored = connectedEdges.every(function(edgeData) {
                var replacementEdge = _htBuildReplacementEdge(edgeData, draftId, newId);
                var addedEdge = cy.add({ group: 'edges', data: replacementEdge });
                if (addedEdge.length !== 1 || cy.getElementById(replacementEdge.id).length !== 1) {
                    return false;
                }
                replacementEdgeIds.push(replacementEdge.id);
                return true;
            });

            if (!edgesRestored || cy.getElementById(newId).length !== 1) {
                var edgeError = new Error('Edge replacement verification failed');
                if (!_htRollbackPublishedDraft(
                    cy,
                    draftId,
                    newId,
                    draftClasses,
                    oldData,
                    pos,
                    connectedEdges,
                    replacementEdgeIds
                )) {
                    edgeError.htCorruptGraph = true;
                }
                throw edgeError;
            }
            return _htPromoteConnections(newId).then(function() {
                var stencilDevice = {
                    id: newId,
                    name: device.name || '',
                    type: device.type || oldData.raw_device_type || '',
                    ip: device.ip || '',
                    version: Number(device.version || 1)
                };
                document.dispatchEvent(new CustomEvent('ht:stencil-device-published', { detail: { device: stencilDevice } }));
                if (window._htFlushAutosave) window._htFlushAutosave();
                if (window._htUpdateDraftBadge) window._htUpdateDraftBadge();
                window._htNotify('Device published to inventory.', 'positive');
                return true;
            });
        })
        .catch(function(err) {
            if (err && err.htCorruptGraph) return false;
            var draftNode = cy.getElementById(draftId);
            if (draftNode.length) draftNode.addClass('draft-error');
            window._htNotify(
                'Publish failed \u2014 your draft has been kept. Try again or reload.',
                'negative',
                {
                    position: 'top-center',
                    timeout: 0,
                    closeBtn: true,
                    group: 'ht-draft-publish-failed'
                }
            );
            return false;
        });
    };

    function _htPromoteConnections(publishedId) {
        var cy = window._cy;
        if (!cy) return Promise.resolve();
        var node = cy.getElementById(publishedId);
        if (!node.length) return Promise.resolve();
        var promotions = [];

        node.connectedEdges().forEach(function(edge) {
            if (!(window._htIsDraftEdge && window._htIsDraftEdge(edge.data()))) return;
            var src = edge.data('source');
            var tgt = edge.data('target');
            if (window._htIsDraft(src) || window._htIsDraft(tgt)) return;
            if (window._htHasPersistedConnection(cy, src, tgt)) {
                edge.remove();
                return;
            }

            var connType = edge.data('connection_type') || 'Ethernet';
            var connLabel = edge.data('raw_label') || '';

            promotions.push(fetch('/api/connections/', {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_id: src,
                    target_id: tgt,
                    type: connType,
                    label: connLabel || null
                })
            })
            .then(function(r) {
                if (!r.ok) return null;
                return r.json();
            })
            .then(function(conn) {
                if (!conn) return;
                if (window._htHasPersistedConnection(cy, conn.source_id, conn.target_id)) {
                    edge.remove();
                    return;
                }
                var addedConnection = cy.add({ group: 'edges', data: {
                    id: conn.id,
                    source: conn.source_id,
                    target: conn.target_id,
                    label: window._htEscapeHtml(conn.label || ''),
                    raw_label: conn.label || '',
                    connection_type: conn.type
                }});
                if (addedConnection.length !== 1) return;
                edge.remove();
            })
            .catch(function() { return null; }));
        });
        return Promise.all(promotions).then(function() { _htPrunePromotedDraftEdges(cy, node); });
    }
})();
"""
