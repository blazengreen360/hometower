"""Reusable JavaScript helper functions for the Cytoscape.js canvas.

Extracted from canvas_events.py to keep file sizes within the 250-line limit.
These helpers are injected inside the _htInitEventHandlers IIFE closure and
have access to the ``cy`` variable via closure scope.
"""

CANVAS_HELPERS_JS = """
        var _escapeHtml = window._htEscapeHtml;
        var _notify = window._htNotify;

        function _clearAssociationSelection() {
            window._htEdgeSource = null;
            var rootStyle = getComputedStyle(document.documentElement);
            var borderColor = rootStyle.getPropertyValue('--ht-border').trim() || rootStyle.getPropertyValue('--ht-text-secondary').trim();
            cy.nodes().style('border-color', borderColor);
        }

        function _startAssociation(sourceId) {
            _clearAssociationSelection();
            window._htEdgeSource = sourceId;
            var sourceNode = cy.getElementById(sourceId);
            if (sourceNode && sourceNode.length) {
                var rootStyle = getComputedStyle(document.documentElement);
                var accentColor = rootStyle.getPropertyValue('--ht-warning').trim() || rootStyle.getPropertyValue('--ht-accent').trim();
                sourceNode.style('border-color', accentColor);
            }
            _notify('Association source selected. Click a target device.', 'warning');
        }

        function _createAssociation(sourceId, targetId) {
            if ((window._htIsDraft && window._htIsDraft(sourceId)) ||
                (window._htIsDraft && window._htIsDraft(targetId))) {
                var localEdgeId = 'draft-edge-' + crypto.randomUUID();
                var localEdgePayload = {
                    connection_id: localEdgeId,
                    source_id: sourceId,
                    target_id: targetId,
                    connection_type: 'Ethernet',
                    label: null
                };
                window.addEdgeToCanvas({
                    id: localEdgeId,
                    source: sourceId,
                    target: targetId,
                    label: '',
                    raw_label: '',
                    connection_type: 'Ethernet',
                    draft_edge: true
                });
                if (window._htPushCommittedUndoEntry) {
                    window._htPushCommittedUndoEntry({
                        entry_id: crypto.randomUUID(),
                        type: 'create_edge',
                        label: 'Create edge',
                        execution: 'local',
                        forward: { op: 'add_edge_local', payload: localEdgePayload },
                        reverse: { op: 'remove_edge_local', payload: localEdgePayload }
                    });
                }
                if (window.scheduleAutosave) window.scheduleAutosave(800);
                _notify('Local connection created (will be published when both devices are published).', 'info');
                return;
            }

            if (window._htRequestCanvasAction) {
                window._htRequestCanvasAction({
                    type: 'create_edge',
                    payload: {
                        scope: 'published',
                        source_id: sourceId,
                        target_id: targetId,
                        connection_type: 'Ethernet',
                        label: null
                    }
                });
            }
        }

        function _confirmDelete(message, onOk) {
            if (window.Quasar && window.Quasar.Dialog && window.Quasar.Dialog.create) {
                window.Quasar.Dialog.create({
                    title: 'Confirm delete',
                    message: message,
                    ok: { label: 'Delete', color: 'negative' },
                    cancel: { label: 'Cancel', flat: true, color: 'grey-6' },
                    persistent: true,
                }).onOk(onOk);
                return;
            }
            if (window.confirm(message)) onOk();
        }

        function _deleteAssociation(d) {
            if (!d || !d.id) return;

            if (window._htIsDraftEdge && window._htIsDraftEdge(d)) {
                var draftEdgePayload = {
                    connection_id: d.id,
                    source_id: d.source || (d.data && d.data.source),
                    target_id: d.target || (d.data && d.data.target),
                    connection_type: d.type || (d.data && d.data.connection_type) || 'Ethernet',
                    label: d.raw_label || d.label || (d.data && d.data.raw_label) || null
                };
                window._cy.getElementById(d.id).remove();
                if (window._htPushCommittedUndoEntry) {
                    window._htPushCommittedUndoEntry({
                        entry_id: crypto.randomUUID(),
                        type: 'delete_edge',
                        label: 'Delete edge',
                        execution: 'local',
                        forward: { op: 'remove_edge_local', payload: draftEdgePayload },
                        reverse: { op: 'add_edge_local', payload: draftEdgePayload }
                    });
                }
                if (window.scheduleAutosave) window.scheduleAutosave(800);
                return;
            }
            if (typeof d.id === 'string' && d.id.indexOf('draft-edge-') === 0) {
                var localEdgePayload = {
                    connection_id: d.id,
                    source_id: d.source || (d.data && d.data.source),
                    target_id: d.target || (d.data && d.data.target),
                    connection_type: d.type || (d.data && d.data.connection_type) || 'Ethernet',
                    label: d.raw_label || d.label || (d.data && d.data.raw_label) || null
                };
                window._cy.getElementById(d.id).remove();
                if (window._htPushCommittedUndoEntry) {
                    window._htPushCommittedUndoEntry({
                        entry_id: crypto.randomUUID(),
                        type: 'delete_edge',
                        label: 'Delete edge',
                        execution: 'local',
                        forward: { op: 'remove_edge_local', payload: localEdgePayload },
                        reverse: { op: 'add_edge_local', payload: localEdgePayload }
                    });
                }
                if (window.scheduleAutosave) window.scheduleAutosave(800);
                return;
            }

            var edgeLabel = d.raw_label || d.label || (d.data && (d.data.raw_label || d.data.label));
            var edgePrompt = edgeLabel
                ? "Delete connection '" + _escapeHtml(edgeLabel) + "'? This cannot be undone."
                : 'Delete this connection? This cannot be undone.';
            _confirmDelete(edgePrompt, function() {
                if (window._htRequestCanvasAction) {
                    window._htRequestCanvasAction({
                        type: 'delete_edge',
                        payload: {
                            scope: 'published',
                            connection_id: d.id,
                            source_id: d.source || (d.data && d.data.source),
                            target_id: d.target || (d.data && d.data.target),
                            connection_type: d.type || (d.data && d.data.connection_type) || 'Ethernet',
                            label: d.raw_label || d.label || (d.data && d.data.raw_label) || null
                        }
                    });
                } else {
                    _notify('Delete unavailable: undo bridge not ready.', 'negative');
                }
            });
        }
"""
