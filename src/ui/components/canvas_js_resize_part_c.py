"""Final fragment of the HT-077 canvas resize bridge script."""

CANVAS_RESIZE_JS_PART_C = """
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
        if (compound) compound.direction = direction;
        var minSize = _htResizeCompoundMin(node, compound ? compound.minPadding : null);

        var aspectRatio = startWidth / Math.max(startHeight, 1);
        if (!Number.isFinite(aspectRatio) || aspectRatio <= 0) aspectRatio = 1;

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