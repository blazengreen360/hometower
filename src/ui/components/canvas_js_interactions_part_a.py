"""Cytoscape interaction bindings fragment A."""

CANVAS_INTERACTIONS_JS_PART_A = """
(function() {
    function _htNodeIsLocked(node) {
        if (!node) return false;
        var data = node.data ? (node.data() || {}) : {};
        return data.ghost === true || data.editable === false || node.hasClass('ghost');
    }

    window._htApplyNodeEditability = function(cy) {
        if (!cy) return;
        cy.nodes().forEach(function(node) {
            if (_htNodeIsLocked(node)) {
                node.ungrabify();
            } else {
                node.grabify();
            }
        });
    };

    window._htBindCanvasInteractions = function(cy, container) {
        function buildNodeSelectedDetail(node) {
            var detail = node.data();
            return {
                id: node.id(),
                name: String(detail.raw_name || detail.label || ''),
                data: detail
            };
        }

        function _htSelectSingleNode(node) {
            if (!cy || !node || !node.length || !node.select) return;
            if (cy.elements && cy.elements().unselect) {
                cy.elements().unselect();
            }
            node.select();
        }

        function emitNodeSelected(node) {
            _htSelectSingleNode(node);
            document.dispatchEvent(new CustomEvent('ht:node-selected', {
                detail: buildNodeSelectedDetail(node)
            }));
        }

        function _htDedupContextMenuRequest(id, eventId) {
            var key = String(id) + ':' + String(eventId);
            window._htCtxMenuRequestKeys = window._htCtxMenuRequestKeys || {};
            if (window._htCtxMenuRequestKeys[key]) return true;
            window._htCtxMenuRequestKeys[key] = true;
            setTimeout(function() {
                delete window._htCtxMenuRequestKeys[key];
            }, 10);
            return false;
        }

        function dispatchContextMenuRequest(detail) {
            var id = String(detail && detail.id || '');
            var eventId = String(detail && detail.eventId || '');
            if (_htDedupContextMenuRequest(id, eventId)) return;
            document.dispatchEvent(new CustomEvent('ht:context-menu-request', { detail: detail }));
        }

        function _htConsumeStructuralDragMoveSuppression(nodeId) {
            var suppression = window._htStructuralDragMoveSuppression;
            if (!suppression || typeof suppression !== 'object') return false;
            var key = String(nodeId || '');
            if (!suppression[key]) return false;
            delete suppression[key];
            return true;
        }

        cy.on('tap', 'node', function(evt) {
            var node = evt.target;
            var isShiftTap = !!(evt.originalEvent && evt.originalEvent.shiftKey);

            if (window.HT_READONLY) {
                if (isShiftTap) return;
                emitNodeSelected(node);
                return;
            }

            if (_htNodeIsLocked(node)) {
                emitNodeSelected(node);
                return;
            }

            if (!window._htEdgeSource && isShiftTap) {
                document.dispatchEvent(new CustomEvent('ht:association-source', {
                    detail: buildNodeSelectedDetail(node)
                }));
                return;
            }

            if (window._htEdgeSource) {
                document.dispatchEvent(new CustomEvent('ht:association-target', {
                    detail: buildNodeSelectedDetail(node)
                }));
                return;
            }

            emitNodeSelected(node);
        });

        cy.on('tap', 'edge', function(evt) {
            var edge = evt.target;
            var srcNode = cy.getElementById(edge.data('source'));
            var tgtNode = cy.getElementById(edge.data('target'));
            document.dispatchEvent(new CustomEvent('ht:edge-selected', { detail: {
                id: edge.id(),
                source: edge.data('source'),
                target: edge.data('target'),
                source_label: srcNode.length ? (srcNode.data('raw_name') || srcNode.data('label')) : edge.data('source'),
                target_label: tgtNode.length ? (tgtNode.data('raw_name') || tgtNode.data('label')) : edge.data('target'),
                type: edge.data('connection_type'),
                label: edge.data('raw_label') || edge.data('label') || ''
            }}));
        });

        cy.on('tap', function(evt) {
            if (evt.target === cy) {
                document.dispatchEvent(new CustomEvent('ht:canvas-bg-click'));
            }
        });

        cy.on('dragstart', 'node', function(evt) {
            if (window.HT_READONLY) return;
            window._htContainerDragCancelled = false;
            if (window._htStructuralDragMoveSuppression && typeof window._htStructuralDragMoveSuppression === 'object') {
                delete window._htStructuralDragMoveSuppression[String(evt.target.id())];
            }
            if (window._htBeginMoveGesture) window._htBeginMoveGesture(evt.target);
        });

        cy.on('dragend', 'node', function(evt) {
            if (window.HT_READONLY) return;
            if (_htConsumeStructuralDragMoveSuppression(evt.target.id())) {
                window._htContainerDragCancelled = false;
                window._htMoveGesture = null;
                return;
            }
            if (window._htContainerDragCancelled) {
                window._htContainerDragCancelled = false;
                return;
            }
            if (window._htCommitMoveGesture) window._htCommitMoveGesture(evt.target);
            if (window.scheduleAutosave) window.scheduleAutosave(800);
        });

        cy.on('dragfree', 'node', function(evt) {
            window._htNodePositions = window._htNodePositions || {};
            window._htNodePositions[evt.target.id()] = evt.target.position();
        });

        cy.on('cxttap', 'node', function(evt) {
            var node = evt.target;
            if (_htNodeIsLocked(node)) {
                emitNodeSelected(node);
                return;
            }
            emitNodeSelected(node);
            if (window.HT_READONLY) return;
            var originalEvent = evt.originalEvent || {};
            var clientX = Number(originalEvent.clientX);
            var clientY = Number(originalEvent.clientY);
            var rendered = evt.renderedPosition || (node.renderedPosition ? node.renderedPosition() : null) || { x: 0, y: 0 };
            if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) {
                var ctxRect = container.getBoundingClientRect();
                clientX = Number(ctxRect.left) + Number(rendered.x || 0);
                clientY = Number(ctxRect.top) + Number(rendered.y || 0);
            }
            dispatchContextMenuRequest({
                id: node.id(),
                data: node.data(),
                source: 'cxttap',
                eventId: originalEvent.timeStamp,
                clientX: clientX,
                clientY: clientY,
                renderedX: Number(rendered.x || 0),
                renderedY: Number(rendered.y || 0)
            });
        });
"""