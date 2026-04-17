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
        var targetBounds = _htResizeCompoundAnchoredBounds(calc, compoundState);
        var targetContentBounds = {
            x1: targetBounds.x1 + compoundState.startPadding.left,
            x2: targetBounds.x2 - compoundState.startPadding.right,
            y1: targetBounds.y1 + compoundState.startPadding.top,
            y2: targetBounds.y2 - compoundState.startPadding.bottom
        };

        compoundState.childStarts.forEach(function(childStart) {
            var child = node.cy().getElementById(childStart.id);
            if (!child || !child.length) return;

            var nextX = direction.indexOf('w') !== -1 && direction.indexOf('e') === -1
                ? targetContentBounds.x2 - childStart.offsetRight
                : targetContentBounds.x1 + childStart.offsetLeft;
            var nextY = direction.indexOf('n') !== -1 && direction.indexOf('s') === -1
                ? targetContentBounds.y2 - childStart.offsetBottom
                : targetContentBounds.y1 + childStart.offsetTop;

            child.position({
                x: nextX,
                y: nextY
            });
            child.data('_positioned', true);
        });

        var children = node.children();
        if (!children || children.length === 0) {
            _htResizeApplyLeaf(node, calc);
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
        node.style('padding', Math.max(0, compoundState.uniformPadding || 0) + 'px');

        node.style('min-width', calc.width + 'px');
        node.style('min-height', calc.height + 'px');
        node.style('min-width-bias-left', leftBias);
        node.style('min-width-bias-right', rightBias);
        node.style('min-height-bias-top', topBias);
        node.style('min-height-bias-bottom', bottomBias);

        var finalBox = node.boundingBox({ includeLabels: false, includeOverlays: false });
        var finalWidth = _htResizeParsePx(finalBox ? (finalBox.w || (finalBox.x2 - finalBox.x1)) : calc.width, calc.width);
        var finalHeight = _htResizeParsePx(finalBox ? (finalBox.h || (finalBox.y2 - finalBox.y1)) : calc.height, calc.height);

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

    function _htResizeStop(commit) {
        var pointer = state.pointer;
        if (!pointer) return;

        document.removeEventListener('pointermove', _htResizePointerMove);
        document.removeEventListener('pointerup', _htResizePointerUp);
        document.removeEventListener('pointercancel', _htResizePointerCancel);

        if (!commit) {
            _htResizeApply(pointer.node, {
                width: pointer.startSize.width,
                height: pointer.startSize.height,
                position: {
                    x: pointer.startPosition.x,
                    y: pointer.startPosition.y
                }
            }, pointer);
        } else if (pointer.last && pointer.last.changed) {
            _htResizeApply(pointer.node, pointer.last, pointer);
            if (window.scheduleAutosave) window.scheduleAutosave(800);
        }

        state.pointer = null;
        _htResizeScheduleSync();
    }

    function _htResizePointerMove(event) {
        if (!state.pointer || event.pointerId !== state.pointer.pointerId) return;
        if (!_htResizeIsActive()) {
            _htResizeStop(false);
            return;
        }
        event.preventDefault();
        var calc = _htResizeCompute(state.pointer, event.clientX, event.clientY);
        state.pointer.last = calc;
        _htResizeApply(state.pointer.node, calc, state.pointer);
        _htResizeShow(state.pointer.node);
    }

    function _htResizePointerUp(event) {
        if (!state.pointer || event.pointerId !== state.pointer.pointerId) return;
        event.preventDefault();
        _htResizeStop(true);
    }

    function _htResizePointerCancel(event) {
        if (!state.pointer || event.pointerId !== state.pointer.pointerId) return;
        event.preventDefault();
        _htResizeStop(false);
    }

    function _htResizePointerDown(event) {
        var direction = event.target && event.target.getAttribute
            ? event.target.getAttribute('data-ht-resize-handle')
            : '';
        if (!direction || !state.cy || !_htResizeIsActive()) return;

        var node = _htResizeSelectedNode();
        if (!node) return;

        event.preventDefault();
        event.stopPropagation();
        var startBox = node.boundingBox({ includeLabels: false, includeOverlays: false });
        var startWidth = _htResizeParsePx(startBox ? (startBox.w || (startBox.x2 - startBox.x1)) : 0, _htResizeParsePx(node.width(), HT_NODE_MIN_SIZE));
        var startHeight = _htResizeParsePx(startBox ? (startBox.h || (startBox.y2 - startBox.y1)) : 0, _htResizeParsePx(node.height(), HT_NODE_MIN_SIZE));
        var startPosition = { x: node.position('x'), y: node.position('y') };
        var compound = _htResizeCaptureCompoundState(node, {
            width: startWidth,
            height: startHeight
        }, startPosition);
        if (compound) {
            compound.direction = direction;
        }
        var minSize = _htResizeCompoundMin(node, compound ? compound.minPadding : null);

        var aspectRatio = startWidth / Math.max(startHeight, 1);
        if (!Number.isFinite(aspectRatio) || aspectRatio <= 0) {
            aspectRatio = 1;
        }

        state.pointer = {
            pointerId: event.pointerId,
            direction: direction,
            node: node,
            startClient: { x: event.clientX, y: event.clientY },
            startPosition: startPosition,
            startSize: { width: startWidth, height: startHeight },
            minSize: minSize,
            zoom: state.cy.zoom(),
            aspectRatio: aspectRatio,
            compound: compound,
            last: null
        };

        document.addEventListener('pointermove', _htResizePointerMove);
        document.addEventListener('pointerup', _htResizePointerUp);
        document.addEventListener('pointercancel', _htResizePointerCancel);
    }

    function _htResizeBindSyncListener() {
        if (state.syncListenerBound) return;
        state.syncListenerBound = true;
        document.addEventListener('ht:canvas-bg-click', function() {
            _htResizeScheduleSync();
        });
    }

    function _htResizeHydrateCompoundsFromPersistedStyles() {
        if (!state.cy) return;

        state.cy.nodes().forEach(function(node) {
            if (!(node.isParent && node.isParent())) return;

            var children = node.children();
            if (!children || children.length === 0) return;

            var savedWidth = _htResizeParsePx(node.style('width'), 0);
            var savedHeight = _htResizeParsePx(node.style('height'), 0);
            if (savedWidth <= 0 || savedHeight <= 0) return;

            var box = node.boundingBox({ includeLabels: false, includeOverlays: false });
            var currentWidth = _htResizeParsePx(box ? (box.w || (box.x2 - box.x1)) : 0, 0);
            var currentHeight = _htResizeParsePx(box ? (box.h || (box.y2 - box.y1)) : 0, 0);

            if (Math.abs(savedWidth - currentWidth) < 0.5 && Math.abs(savedHeight - currentHeight) < 0.5) {
                return;
            }

            var padding = _htResizeCompoundPadding(node);
            var savedContentWidth = Math.max(1, savedWidth - padding.left - padding.right);
            var savedContentHeight = Math.max(1, savedHeight - padding.top - padding.bottom);

            node.style('min-width', savedContentWidth + 'px');
            node.style('min-height', savedContentHeight + 'px');
        });
    }

    window._htResizeSyncFromSelection = function() {
        _htResizeEnsureHandles();
        if (!_htResizeIsActive()) {
            _htResizeHide();
            return;
        }
        var node = _htResizeSelectedNode();
        if (!node) {
            _htResizeHide();
            return;
        }
        _htResizeShow(node);
    };

    window._htResizeSetEnabled = function(enabled) {
        state.enabled = !!enabled;
        if (!state.enabled) _htResizeStop(false);
        if (window._htResizeSyncFromSelection) {
            window._htResizeSyncFromSelection();
        }
    };

    window._htBindCanvasResize = function(cy, container) {
        if (!cy || !container) return;

        state.cy = cy;
        state.container = container;
        _htResizeEnsureHandles();
        _htResizeBindSyncListener();
        _htResizeHydrateCompoundsFromPersistedStyles();

        if (!state.bound) {
            state.bound = true;
            cy.on('select unselect add remove position style', 'node', function() {
                _htResizeScheduleSync();
            });
            cy.on('pan zoom resize', function() {
                _htResizeScheduleSync();
            });
        }

        if (window._htResizeSyncFromSelection) {
            window._htResizeSyncFromSelection();
        }
    };
})();

"""
