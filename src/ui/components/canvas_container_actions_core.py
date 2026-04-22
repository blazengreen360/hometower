"""Core reparent helpers for the topology canvas container actions."""

CANVAS_CONTAINER_ACTIONS_CORE_JS = """
        function _htNormalizeParentId(value) {
            return value == null || value === '' ? null : String(value);
        }

        function _htCloneRenderedPosition(position) {
            return { x: Number(position && position.x ? position.x : 0), y: Number(position && position.y ? position.y : 0) };
        }

        function _htCloneBounds(bounds) {
            if (!bounds) return null;
            return { x1: Number(bounds.x1 || 0), y1: Number(bounds.y1 || 0), x2: Number(bounds.x2 || 0), y2: Number(bounds.y2 || 0) };
        }

        function _htCurrentRenderedPosition(node) {
            if (!node || !node.length) return { x: 0, y: 0 };
            if (node.renderedPosition) {
                var rendered = node.renderedPosition();
                if (rendered && Number.isFinite(rendered.x) && Number.isFinite(rendered.y)) {
                    return { x: rendered.x, y: rendered.y };
                }
            }
            var box = node.renderedBoundingBox
                ? node.renderedBoundingBox({ includeLabels: false, includeOverlays: false })
                : null;
            if (box) return { x: (box.x1 + box.x2) / 2, y: (box.y1 + box.y2) / 2 };
            var position = node.position ? node.position() : { x: 0, y: 0 };
            return { x: position.x, y: position.y };
        }

        function _htApplyRenderedPosition(node, renderedPosition) {
            if (!node || !node.length || !renderedPosition) return;
            var next = _htCloneRenderedPosition(renderedPosition);
            if (node.renderedPosition) {
                node.renderedPosition(next);
                return;
            }
            var cyRef = node.cy ? node.cy() : null;
            if (!cyRef) return;
            var zoom = cyRef.zoom() || 1;
            var pan = cyRef.pan() || { x: 0, y: 0 };
            node.position({
                x: (next.x - pan.x) / zoom,
                y: (next.y - pan.y) / zoom
            });
        }

        function _htMoveReparentedNode(node, parentId, renderedPosition, version) {
            if (!node || !node.length) return;
            node = node.move({ parent: parentId });
            _htApplyRenderedPosition(node, renderedPosition);
            node.data('parent', parentId);
            if (version != null) {
                node.data('version', Number(version || node.data('version') || 1));
            }
        }

        function _htReparentUndoPayload(node, spec, version) {
            return {
                node_id: node.id(),
                device_id: node.id(),
                from_parent_id: _htNormalizeParentId(spec.fromParentId),
                to_parent_id: _htNormalizeParentId(spec.toParentId),
                from_rendered_position: _htCloneRenderedPosition(spec.fromRenderedPosition),
                to_rendered_position: _htCloneRenderedPosition(spec.toRenderedPosition),
                version_cursor: Number(version || node.data('version') || 1),
                label: String(spec.label || '')
            };
        }

        function _htReparentNotice(spec) {
            return spec.toParentId ? 'Device moved into container.' : 'Device removed from container.';
        }

        function _htSelectedNodeIds() {
            if (!window._cy) return [];
            return window._cy.$('node:selected').map(function(selectedNode) {
                return String(selectedNode.id());
            });
        }

        function _htRestoreSelection(nodeIds) {
            if (!window._cy) return;
            window._cy.nodes().unselect();
            (nodeIds || []).forEach(function(nodeId) {
                var selectedNode = window._cy.getElementById(String(nodeId));
                if (selectedNode && selectedNode.length && selectedNode.select) {
                    selectedNode.select();
                }
            });
        }

        window._htApplyCanvasReparent = function(node, parentId, renderedPosition, version) {
            _htMoveReparentedNode(node, _htNormalizeParentId(parentId), renderedPosition, version);
        };

        function _htCommitLocalReparent(node, spec) {
            var payload = _htReparentUndoPayload(node, spec, node.data('version'));
            _htMoveReparentedNode(node, payload.to_parent_id, payload.to_rendered_position, payload.version_cursor);
            if (window.scheduleAutosave) window.scheduleAutosave(800);
            if (window._htPushCommittedUndoEntry) {
                window._htPushCommittedUndoEntry({
                    entry_id: crypto.randomUUID(),
                    type: 'reparent_node',
                    label: String(spec.label || 'Move device'),
                    execution: 'local',
                    forward: { op: 'reparent_node', payload: payload },
                    reverse: { op: 'reparent_node', payload: payload }
                });
            }
            _notify(_htReparentNotice(spec), 'positive');
        }

        function _htRequestPublishedReparent(node, spec) {
            if (!window._htRequestCanvasAction || window.HT_READONLY || (window._htUndoState && window._htUndoState.busy)) {
                return false;
            }

            _htWrapPublishedReparentResolvers();
            var entryId = crypto.randomUUID();
            var payload = _htReparentUndoPayload(node, spec, node.data('version'));
            if (!_htLockPendingPublishedReparent(node, entryId, payload)) {
                _notify('Move blocked: node is busy with another change.', 'warning');
                return false;
            }

            _htMoveReparentedNode(node, payload.to_parent_id, payload.to_rendered_position, payload.version_cursor);
            _notify('Saving container move...', 'info');
            window._htRequestCanvasAction({
                entry_id: entryId,
                type: 'reparent_device',
                payload: {
                    device_id: payload.device_id,
                    from_parent_id: payload.from_parent_id,
                    to_parent_id: payload.to_parent_id,
                    from_rendered_position: payload.from_rendered_position,
                    to_rendered_position: payload.to_rendered_position,
                    version_cursor: payload.version_cursor,
                    label: payload.label
                }
            });
            return true;
        }

        function _htRequestNodeReparent(node, spec) {
            if (!node || !node.length || !spec) return false;
            if (_htPendingPublishedReparentSelectionLocked(node)) {
                _notify('Move blocked: node is busy with another change.', 'warning');
                return false;
            }
            var isDraftNode = !!(
                (window._htIsDraft && window._htIsDraft(node.id()))
                || (node.data && node.data('draft'))
                || (node.hasClass && node.hasClass('draft'))
            );
            if (isDraftNode) {
                _htCommitLocalReparent(node, spec);
                return true;
            }
            return _htRequestPublishedReparent(node, spec);
        }

        window._htRequestDetachToTopLevel = function(nodeId) {
            if (!window._cy || window.HT_READONLY) return;
            var node = window._cy.getElementById(String(nodeId || ''));
            if (!node || !node.length) return;
            var currentParent = _htNormalizeParentId(node.data('parent'));
            if (!currentParent) return;

            var rendered = _htCurrentRenderedPosition(node);
            _htRequestNodeReparent(node, {
                fromParentId: currentParent,
                toParentId: null,
                fromRenderedPosition: rendered,
                toRenderedPosition: rendered,
                label: 'Remove from container'
            });
        };
"""