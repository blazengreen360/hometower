"""Cytoscape.js interaction bindings used by the canvas init script."""

CANVAS_INTERACTIONS_JS = """
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

        function emitNodeSelected(node) {
            document.dispatchEvent(new CustomEvent('ht:node-selected', {
                detail: buildNodeSelectedDetail(node)
            }));
        }

        function dispatchContextMenuRequest(detail) {
            if (window._htCtxMenuBridgeHandled) return;
            window._htCtxMenuBridgeHandled = true;
            window.setTimeout(function() { window._htCtxMenuBridgeHandled = false; }, 50);
            document.dispatchEvent(new CustomEvent('ht:context-menu-request', { detail: detail }));
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
            if (window._htBeginMoveGesture) window._htBeginMoveGesture(evt.target);
        });

        cy.on('dragend', 'node', function(evt) {
            if (window.HT_READONLY) return;
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
            dispatchContextMenuRequest({ id: node.id(), data: node.data() });
        });

        container.addEventListener('contextmenu', function(e) {
            if (window.HT_READONLY) return;
            e.preventDefault();
            if (window._htCtxMenuBridgeHandled) return;

            window._htLastCtxX = e.clientX;
            window._htLastCtxY = e.clientY;

            var rect = container.getBoundingClientRect();
            var rx = e.clientX - rect.left;
            var ry = e.clientY - rect.top;
            var nearest = null;
            var best = Infinity;

            cy.nodes().forEach(function(node) {
                var pos = node.renderedPosition();
                var dx = pos.x - rx;
                var dy = pos.y - ry;
                var dist = dx * dx + dy * dy;
                if (dist < best) {
                    best = dist;
                    nearest = node;
                }
            });

            if (!nearest || Math.sqrt(best) > 30) return;
            if (_htNodeIsLocked(nearest)) return;
            dispatchContextMenuRequest({ id: nearest.id(), data: nearest.data() });
        });

        container.addEventListener('dragover', function(e) { e.preventDefault(); });
        container.addEventListener('drop', function(e) {
            e.preventDefault();
            var rect = container.getBoundingClientRect();
            var zoom = cy.zoom();
            var pan = cy.pan();
            var renderedX = e.clientX - rect.left;
            var renderedY = e.clientY - rect.top;
            var pos = { x: (renderedX - pan.x) / zoom, y: (renderedY - pan.y) / zoom };

            var inventoryId = e.dataTransfer.getData('inventoryDeviceId');
            if (inventoryId) {
                document.dispatchEvent(new CustomEvent('ht:stencil-drop', {
                    detail: {
                        deviceId: inventoryId,
                        deviceName: e.dataTransfer.getData('inventoryDeviceName'),
                        deviceType: e.dataTransfer.getData('inventoryDeviceType'),
                        deviceIp: e.dataTransfer.getData('inventoryDeviceIp'),
                        deviceVersion: e.dataTransfer.getData('inventoryDeviceVersion'),
                        x: pos.x,
                        y: pos.y
                    }
                }));
                return;
            }

            var deviceType = e.dataTransfer.getData('deviceType');
            if (!deviceType) return;
            document.dispatchEvent(new CustomEvent('ht:palette-drop', {
                detail: {
                    deviceType: deviceType,
                    x: pos.x,
                    y: pos.y,
                    screenX: e.clientX,
                    screenY: e.clientY
                }
            }));
        });

        window._htInitTooltipHandlers();
        window._htApplyNodeEditability(cy);
    };
})();
"""