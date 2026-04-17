"""First fragment of the HT-050 canvas resize bridge script."""

CANVAS_RESIZE_JS_PART_A = """
(function() {
    if (window._htCanvasResizeBridgeLoaded) return;
    window._htCanvasResizeBridgeLoaded = true;

    var HT_NODE_MIN_SIZE = 40;
    var HT_COMPOUND_MIN_PADDING = 24;
    var HT_HANDLE_SIZE = 12;
    var HT_HANDLE_OFF = HT_HANDLE_SIZE / 2;
    var HT_CORNER_HANDLES = { nw: true, ne: true, se: true, sw: true };
    var HT_DIRECTIONS = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
    var HT_CURSOR_BY_DIRECTION = {
        n: 'ns-resize',
        s: 'ns-resize',
        e: 'ew-resize',
        w: 'ew-resize',
        ne: 'nesw-resize',
        sw: 'nesw-resize',
        nw: 'nwse-resize',
        se: 'nwse-resize'
    };

    var state = {
        cy: null,
        container: null,
        overlay: null,
        handles: {},
        bound: false,
        enabled: false,
        raf: 0,
        pointer: null,
        syncListenerBound: false
    };

    function _htResizeParsePx(rawValue, fallback) {
        var parsed = parseFloat(String(rawValue || ''));
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function _htResizeCompoundPadding(node) {
        var fallback = _htResizeParsePx(node && node.style ? node.style('padding') : 0, 0);
        return {
            left: _htResizeParsePx(node && node.style ? node.style('padding-left') : 0, fallback),
            right: _htResizeParsePx(node && node.style ? node.style('padding-right') : 0, fallback),
            top: _htResizeParsePx(node && node.style ? node.style('padding-top') : 0, fallback),
            bottom: _htResizeParsePx(node && node.style ? node.style('padding-bottom') : 0, fallback)
        };
    }

    function _htResizeCompoundMinPadding(node) {
        var padding = _htResizeCompoundPadding(node);
        return {
            left: Math.min(padding.left, HT_COMPOUND_MIN_PADDING),
            right: Math.min(padding.right, HT_COMPOUND_MIN_PADDING),
            top: Math.min(padding.top, HT_COMPOUND_MIN_PADDING),
            bottom: Math.min(padding.bottom, HT_COMPOUND_MIN_PADDING)
        };
    }

    function _htResizeGetOverlay() {
        if (state.overlay && document.body.contains(state.overlay)) return state.overlay;
        var overlay = document.getElementById('ht-node-resize-overlay');
        if (!overlay) {
            if (!state.container || !state.container.parentElement) return null;
            overlay = document.createElement('div');
            overlay.id = 'ht-node-resize-overlay';
            state.container.parentElement.appendChild(overlay);
        }
        overlay.style.position = 'absolute';
        overlay.style.inset = '0';
        overlay.style.pointerEvents = 'none';
        overlay.style.zIndex = '8';
        overlay.style.display = 'none';
        state.overlay = overlay;
        return overlay;
    }

    function _htResizeEnsureHandles() {
        var overlay = _htResizeGetOverlay();
        if (!overlay) return;
        if (Object.keys(state.handles).length > 0) return;

        HT_DIRECTIONS.forEach(function(direction) {
            var handle = document.createElement('div');
            handle.setAttribute('data-ht-resize-handle', direction);
            handle.style.position = 'absolute';
            handle.style.width = HT_HANDLE_SIZE + 'px';
            handle.style.height = HT_HANDLE_SIZE + 'px';
            handle.style.border = '1px solid var(--ht-accent)';
            handle.style.background = 'var(--ht-bg-surface-raised)';
            handle.style.borderRadius = '3px';
            handle.style.pointerEvents = 'auto';
            handle.style.cursor = HT_CURSOR_BY_DIRECTION[direction] || 'move';
            handle.style.boxSizing = 'border-box';
            handle.addEventListener('pointerdown', _htResizePointerDown);
            state.handles[direction] = handle;
            overlay.appendChild(handle);
        });
    }

    function _htResizeIsLocked(node) {
        if (!node || !node.length) return true;
        var data = node.data ? (node.data() || {}) : {};
        return data.ghost === true || data.editable === false || node.hasClass('ghost');
    }

    function _htResizeIsEligible(node) {
        if (!node || !node.length || !node.isNode || !node.isNode()) return false;
        return !_htResizeIsLocked(node);
    }

    function _htResizeIsActive() {
        return !!(
            state.enabled
            && state.cy
            && !window.HT_READONLY
            && window._htHistoryPreviewActive !== true
        );
    }

    function _htResizeHide() {
        var overlay = _htResizeGetOverlay();
        if (!overlay) return;
        overlay.style.display = 'none';
    }

    function _htResizeSelectedNode() {
        if (!state.cy) return null;
        var selected = state.cy.$('node:selected');
        if (selected.length !== 1) return null;
        var node = selected.first();
        if (!_htResizeIsEligible(node)) return null;
        return node;
    }

    function _htResizePlaceHandle(direction, x, y) {
        var handle = state.handles[direction];
        if (!handle) return;
        handle.style.left = (x - HT_HANDLE_OFF) + 'px';
        handle.style.top = (y - HT_HANDLE_OFF) + 'px';
    }

    function _htResizeShow(node) {
        var overlay = _htResizeGetOverlay();
        if (!overlay) return;

        var box = node.renderedBoundingBox({ includeLabels: false, includeOverlays: false });
        _htResizePlaceHandle('nw', box.x1, box.y1);
        _htResizePlaceHandle('n', (box.x1 + box.x2) / 2, box.y1);
        _htResizePlaceHandle('ne', box.x2, box.y1);
        _htResizePlaceHandle('e', box.x2, (box.y1 + box.y2) / 2);
        _htResizePlaceHandle('se', box.x2, box.y2);
        _htResizePlaceHandle('s', (box.x1 + box.x2) / 2, box.y2);
        _htResizePlaceHandle('sw', box.x1, box.y2);
        _htResizePlaceHandle('w', box.x1, (box.y1 + box.y2) / 2);
        overlay.style.display = 'block';
    }

    function _htResizeScheduleSync() {
        if (state.raf) return;
        state.raf = window.requestAnimationFrame(function() {
            state.raf = 0;
            if (window._htResizeSyncFromSelection) {
                window._htResizeSyncFromSelection();
            }
        });
    }

    function _htResizeCompoundMin(node, minPadding) {
        var minWidth = HT_NODE_MIN_SIZE;
        var minHeight = HT_NODE_MIN_SIZE;
        if (!node || !node.length) {
            return { width: minWidth, height: minHeight };
        }

        var isCompound = node.isParent && node.isParent();
        if (!isCompound && !node.hasClass('container')) {
            return { width: minWidth, height: minHeight };
        }

        var children = node.children();
        if (!children || children.length === 0) {
            return { width: minWidth, height: minHeight };
        }

        var childBox = children.boundingBox({ includeLabels: false, includeOverlays: false });
        var childWidth = Math.max(0, childBox.w || (childBox.x2 - childBox.x1));
        var childHeight = Math.max(0, childBox.h || (childBox.y2 - childBox.y1));
        var padding = minPadding || _htResizeCompoundPadding(node);

        minWidth = Math.max(minWidth, childWidth + padding.left + padding.right);
        minHeight = Math.max(minHeight, childHeight + padding.top + padding.bottom);
        return {
            width: minWidth,
            height: minHeight
        };
    }

    function _htResizeCaptureCompoundState(node, startSize, startPosition) {
        if (!node || !node.length || !(node.isParent && node.isParent())) return null;

        var children = node.children();
        if (!children || children.length === 0) return null;

        var startPadding = _htResizeCompoundPadding(node);
        var minPadding = _htResizeCompoundMinPadding(node);
        var uniformPadding = _htResizeParsePx(node && node.style ? node.style('padding') : 0, Math.max(
            startPadding.left,
            startPadding.right,
            startPadding.top,
            startPadding.bottom,
            0
        ));
        var startBounds = {
            x1: startPosition.x - (startSize.width / 2),
            y1: startPosition.y - (startSize.height / 2),
            x2: startPosition.x + (startSize.width / 2),
            y2: startPosition.y + (startSize.height / 2)
        };
        var startContentBounds = {
            x1: startBounds.x1 + startPadding.left,
            x2: startBounds.x2 - startPadding.right,
            y1: startBounds.y1 + startPadding.top,
            y2: startBounds.y2 - startPadding.bottom
        };
        var childStarts = [];

        children.forEach(function(child) {
            var childX = child.position('x');
            var childY = child.position('y');
            childStarts.push({
                id: child.id(),
                x: childX,
                y: childY,
                offsetLeft: childX - startContentBounds.x1,
                offsetRight: startContentBounds.x2 - childX,
                offsetTop: childY - startContentBounds.y1,
                offsetBottom: startContentBounds.y2 - childY
            });
        });

        return {
            childStarts: childStarts,
            startPadding: startPadding,
            minPadding: minPadding,
            uniformPadding: uniformPadding,
            startBounds: startBounds,
            startContentBounds: startContentBounds
        };
    }

    function _htResizeCompute(pointer, clientX, clientY) {
        var zoom = pointer.zoom || 1;
        var dx = (clientX - pointer.startClient.x) / zoom;
        var dy = (clientY - pointer.startClient.y) / zoom;
        var direction = pointer.direction;

        var affectX = direction.indexOf('e') !== -1 || direction.indexOf('w') !== -1;
        var affectY = direction.indexOf('n') !== -1 || direction.indexOf('s') !== -1;
        var signX = direction.indexOf('w') !== -1 ? -1 : 1;
        var signY = direction.indexOf('n') !== -1 ? -1 : 1;

        var width = pointer.startSize.width;
        var height = pointer.startSize.height;

        if (HT_CORNER_HANDLES[direction]) {
            var widthDeltaFromX = signX * dx;
            var widthDeltaFromY = signY * dy * pointer.aspectRatio;
            var dominantDelta = Math.abs(widthDeltaFromX) >= Math.abs(widthDeltaFromY)
                ? widthDeltaFromX
                : widthDeltaFromY;
            width = pointer.startSize.width + dominantDelta;
            height = width / pointer.aspectRatio;
        } else {
            if (affectX) width = pointer.startSize.width + (signX * dx);
            if (affectY) height = pointer.startSize.height + (signY * dy);
        }

        width = Math.max(pointer.minSize.width, width);
        height = Math.max(pointer.minSize.height, height);

        if (HT_CORNER_HANDLES[direction]) {
            var widthFromHeight = height * pointer.aspectRatio;
            if (widthFromHeight > width) width = widthFromHeight;
            height = width / pointer.aspectRatio;

            if (height < pointer.minSize.height) {
                height = pointer.minSize.height;
                width = Math.max(pointer.minSize.width, height * pointer.aspectRatio);
            }
            if (width < pointer.minSize.width) {
                width = pointer.minSize.width;
                height = Math.max(pointer.minSize.height, width / pointer.aspectRatio);
            }
        }

        var deltaW = width - pointer.startSize.width;
        var deltaH = height - pointer.startSize.height;
        var x = pointer.startPosition.x;
        var y = pointer.startPosition.y;

        if (affectX) x += (signX * deltaW) / 2;
        if (affectY) y += (signY * deltaH) / 2;

        return {
            width: width,
            height: height,
            position: { x: x, y: y },
            changed: Math.abs(deltaW) > 0.2 || Math.abs(deltaH) > 0.2
        };
    }

    function _htResizeApplyLeaf(node, calc) {
        if (!node || !node.length || !calc) return;
        node.style('width', calc.width);
        node.style('height', calc.height);
        node.position(calc.position);
        node.data('_positioned', true);
    }

    function _htResizeSyncCompoundChain(node) {
        var cursor = node;
        while (cursor && cursor.length) {
            if (cursor.isParent && cursor.isParent()) {
                var box = cursor.boundingBox({ includeLabels: false, includeOverlays: false });
                var width = _htResizeParsePx(box ? (box.w || (box.x2 - box.x1)) : 0, 0);
                var height = _htResizeParsePx(box ? (box.h || (box.y2 - box.y1)) : 0, 0);
                if (width > 0 && height > 0) {
                    cursor.style('width', width);
                    cursor.style('height', height);
                }
            }

            var parent = cursor.parent ? cursor.parent() : null;
            if (!parent || !parent.length) break;
            cursor = parent;
        }
    }


"""
