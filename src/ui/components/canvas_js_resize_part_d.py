"""Supplemental fragment of the HT-077 canvas resize bridge script."""

CANVAS_RESIZE_JS_PART_D = """
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

        return {
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