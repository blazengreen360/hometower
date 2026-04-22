"""Second fragment of the HT-050 canvas resize bridge script."""

CANVAS_RESIZE_JS_PART_B = """
    function _htResizeCompoundAnchoredBounds(calc, compoundState) {
        var direction = compoundState.direction || '';
        var startBounds = compoundState.startBounds || {
            x1: calc.position.x - (calc.width / 2),
            y1: calc.position.y - (calc.height / 2),
            x2: calc.position.x + (calc.width / 2),
            y2: calc.position.y + (calc.height / 2)
        };
        var x1 = startBounds.x1;
        var y1 = startBounds.y1;
        var x2 = startBounds.x2;
        var y2 = startBounds.y2;

        if (direction.indexOf('e') !== -1 && direction.indexOf('w') === -1) {
            x2 = x1 + calc.width;
        } else if (direction.indexOf('w') !== -1 && direction.indexOf('e') === -1) {
            x1 = x2 - calc.width;
        } else {
            x1 = calc.position.x - (calc.width / 2);
            x2 = calc.position.x + (calc.width / 2);
        }

        if (direction.indexOf('s') !== -1 && direction.indexOf('n') === -1) {
            y2 = y1 + calc.height;
        } else if (direction.indexOf('n') !== -1 && direction.indexOf('s') === -1) {
            y1 = y2 - calc.height;
        } else {
            y1 = calc.position.y - (calc.height / 2);
            y2 = calc.position.y + (calc.height / 2);
        }

        return {
            x1: x1,
            y1: y1,
            x2: x2,
            y2: y2
        };
    }

    function _htResizeApplyCompound(node, calc, compoundState) {
        if (!node || !node.length || !calc || !compoundState) {
            _htResizeApplyLeaf(node, calc);
            return;
        }

        var direction = compoundState.direction || '';
        var liveMin = _htResizeCompoundMin(node, compoundState.minPadding);
        var nextCalc = {
            width: Math.max(calc.width, liveMin.width),
            height: Math.max(calc.height, liveMin.height),
            position: calc.position,
            changed: calc.changed
        };
        var targetBounds = _htResizeCompoundAnchoredBounds(nextCalc, compoundState);
        nextCalc.width = targetBounds.x2 - targetBounds.x1;
        nextCalc.height = targetBounds.y2 - targetBounds.y1;
        nextCalc.position = {
            x: (targetBounds.x1 + targetBounds.x2) / 2,
            y: (targetBounds.y1 + targetBounds.y2) / 2
        };

        var children = node.children();
        if (!children || children.length === 0) {
            _htResizeApplyLeaf(node, nextCalc);
            return;
        }

        // Prefer compound-native minimum sizing properties because they persist cleanly.
        var leftBias = '50%';
        var rightBias = '50%';
        var topBias = '50%';
        var bottomBias = '50%';

        if (direction.indexOf('e') !== -1 && direction.indexOf('w') === -1) {
            leftBias = '0%';
            rightBias = '100%';
        } else if (direction.indexOf('w') !== -1 && direction.indexOf('e') === -1) {
            leftBias = '100%';
            rightBias = '0%';
        }

        if (direction.indexOf('s') !== -1 && direction.indexOf('n') === -1) {
            topBias = '0%';
            bottomBias = '100%';
        } else if (direction.indexOf('n') !== -1 && direction.indexOf('s') === -1) {
            topBias = '100%';
            bottomBias = '0%';
        }

        node.removeStyle('padding-left');
        node.removeStyle('padding-right');
        node.removeStyle('padding-top');
        node.removeStyle('padding-bottom');
        node.style('min-width', nextCalc.width + 'px');
        node.style('min-height', nextCalc.height + 'px');
        node.style('min-width-bias-left', leftBias);
        node.style('min-width-bias-right', rightBias);
        node.style('min-height-bias-top', topBias);
        node.style('min-height-bias-bottom', bottomBias);

        var finalBox = node.boundingBox({ includeLabels: false, includeOverlays: false });
        var finalWidth = _htResizeParsePx(finalBox ? (finalBox.w || (finalBox.x2 - finalBox.x1)) : nextCalc.width, nextCalc.width);
        var finalHeight = _htResizeParsePx(finalBox ? (finalBox.h || (finalBox.y2 - finalBox.y1)) : nextCalc.height, nextCalc.height);

        // Keep style dimensions synchronized to rendered BB for persistence sanity.
        node.style('width', finalWidth);
        node.style('height', finalHeight);
        _htResizeSyncCompoundChain(node);
        node.data('_positioned', true);
    }

    function _htResizeApply(node, calc, pointer) {
        if (!node || !node.length || !calc) return;
        if (pointer && pointer.compound) {
            _htResizeApplyCompound(node, calc, pointer.compound);
            return;
        }
        _htResizeApplyLeaf(node, calc);
    }

"""
