"""Pending published reparent helpers for topology canvas container actions."""

CANVAS_CONTAINER_ACTIONS_PENDING_JS = """
        function _htPendingPublishedReparentSelectionLocked(node) {
            var pending = window._htPendingPublishedReparent || {};
            var candidateIds = {};
            if (node && node.length) {
                candidateIds[String(node.id())] = true;
            }
            _htSelectedNodeIds().forEach(function(selectedId) {
                candidateIds[String(selectedId)] = true;
            });
            if (!Object.keys(candidateIds).length) return false;

            return Object.keys(pending).some(function(entryId) {
                var rollback = pending[String(entryId)] || {};
                var selectionIds = (rollback.selection_ids || []).map(function(selectionId) {
                    return String(selectionId);
                });
                if (rollback.node_id != null) {
                    selectionIds.push(String(rollback.node_id));
                }
                return selectionIds.some(function(selectionId) {
                    return !!candidateIds[String(selectionId)];
                });
            });
        }

        window._htPendingPublishedReparentSelectionLocked = _htPendingPublishedReparentSelectionLocked;

        function _htLockPendingPublishedReparent(node, entryId, payload) {
            var pendingNodeId = String(node.id());
            window._htPendingPublishedReparent = window._htPendingPublishedReparent || {};
            window._htPendingPublishedReparentByNode = window._htPendingPublishedReparentByNode || {};
            if (window._htPendingPublishedReparentByNode[pendingNodeId]) {
                return false;
            }
            window._htPendingPublishedReparentByNode[pendingNodeId] = String(entryId);
            window._htPendingPublishedReparent[String(entryId)] = {
                node_id: node.id(),
                parent_id: payload.from_parent_id,
                rendered_position: payload.from_rendered_position,
                version: payload.version_cursor,
                selection_ids: _htSelectedNodeIds()
            };
            return true;
        }

        function _htTakePendingPublishedReparent(entryId) {
            var pending = window._htPendingPublishedReparent || {};
            var rollback = pending[String(entryId)] || null;
            delete pending[String(entryId)];
            if (rollback) {
                var byNode = window._htPendingPublishedReparentByNode || {};
                delete byNode[String(rollback.node_id || '')];
            }
            return rollback;
        }

        function _htRollbackPublishedReparent(rollback) {
            if (!rollback || !window._cy) return false;
            var node = window._cy.getElementById(String(rollback.node_id || ''));
            if (!node || !node.length) return false;
            _htMoveReparentedNode(
                node,
                _htNormalizeParentId(rollback.parent_id),
                rollback.rendered_position,
                rollback.version
            );
            _htRestoreSelection(rollback.selection_ids || []);
            return true;
        }

        function _htPersistPublishedReparentDraft() {
            var queuedAutosave = false;
            if (window.scheduleAutosave) {
                window.scheduleAutosave(0);
                queuedAutosave = true;
            }
            if (window._htFlushAutosave) {
                window._htFlushAutosave();
                return;
            }
            if (!queuedAutosave && window.scheduleAutosave) {
                window.scheduleAutosave(800);
            }
        }

        function _htShouldPersistPublishedReparent(direction, hadPendingReparent, result) {
            if (hadPendingReparent) return true;
            var entry = result && typeof result.entry === 'object' ? result.entry : null;
            if (entry && String(entry.type || '') === 'reparent_device') {
                return true;
            }

            var entryPatch = result && typeof result.entry_patch === 'object' ? result.entry_patch : null;
            var forward = entryPatch && typeof entryPatch.forward === 'object' ? entryPatch.forward : null;
            var reverse = entryPatch && typeof entryPatch.reverse === 'object' ? entryPatch.reverse : null;
            var graphPatch = result && typeof result.graph_patch === 'object' ? result.graph_patch : null;
            return String((forward && forward.op) || '') === 'reparent_device'
                || String((reverse && reverse.op) || '') === 'reparent_device'
                || String((graphPatch && graphPatch.op) || '') === 'reparent_node';
        }

        function _htWrapPublishedReparentResolvers() {
            if (window._htPublishedReparentWrapped) return;
            window._htPublishedReparentWrapped = true;
            var baseSuccess = window._htResolveUndoApiSuccess;
            window._htResolveUndoApiSuccess = function(direction, entryId, result) {
                var hadPendingReparent = false;
                if (direction === 'forward') {
                    hadPendingReparent = !!_htTakePendingPublishedReparent(entryId);
                }
                if (typeof baseSuccess === 'function') {
                    baseSuccess(direction, entryId, result);
                }
                if (_htShouldPersistPublishedReparent(direction, hadPendingReparent, result)) {
                    if (direction === 'forward') {
                        _htPersistPublishedReparentDraft();
                    } else if (window.requestAnimationFrame) {
                        window.requestAnimationFrame(function() {
                            _htPersistPublishedReparentDraft();
                        });
                    } else {
                        window.setTimeout(function() {
                            _htPersistPublishedReparentDraft();
                        }, 0);
                    }
                }
            };

            var baseFailure = window._htResolveUndoApiFailure;
            window._htResolveUndoApiFailure = function(direction, entryId, message) {
                if (direction === 'forward') {
                    var rollback = _htTakePendingPublishedReparent(entryId);
                    if (rollback && !_htRollbackPublishedReparent(rollback)) {
                        _notify('Move failed and could not be restored. Reload topology.', 'negative');
                    }
                }
                if (typeof baseFailure === 'function') {
                    baseFailure(direction, entryId, message);
                }
            };
        }
"""