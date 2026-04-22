"""Cytoscape interaction bindings fragment B."""

CANVAS_INTERACTIONS_JS_PART_B = """
        container.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            if (window.HT_READONLY) return;

            window._htLastCtxX = e.clientX;
            window._htLastCtxY = e.clientY;

            var rect = container.getBoundingClientRect();
            var rx = e.clientX - rect.left;
            var ry = e.clientY - rect.top;
            var hitNode = null;
            var hitArea = Number.POSITIVE_INFINITY;

            cy.nodes().forEach(function(node) {
                if (!node.renderedBoundingBox) return;
                var box = node.renderedBoundingBox({ includeLabels: false, includeOverlays: false });
                if (!box) return;
                var contains = rx >= box.x1 && rx <= box.x2 && ry >= box.y1 && ry <= box.y2;
                if (!contains) return;
                var depth = Number(node.ancestors ? (node.ancestors().length || 0) : 0);
                var width = Math.max(0, box.x2 - box.x1);
                var height = Math.max(0, box.y2 - box.y1);
                var area = width * height;
                var isDeeper = !hitNode || depth > Number(hitNode.ancestors ? (hitNode.ancestors().length || 0) : 0);
                var isSmallerAtSameDepth = !isDeeper && area < hitArea;
                if (isDeeper || isSmallerAtSameDepth) {
                    hitArea = area;
                    hitNode = node;
                }
            });

            if (hitNode) {
                emitNodeSelected(hitNode);
                if (_htNodeIsLocked(hitNode)) return;
                dispatchContextMenuRequest({
                    id: hitNode.id(),
                    data: hitNode.data(),
                    source: 'contextmenu',
                    eventId: e.timeStamp,
                    clientX: e.clientX,
                    clientY: e.clientY,
                    renderedX: rx,
                    renderedY: ry
                });
            }
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