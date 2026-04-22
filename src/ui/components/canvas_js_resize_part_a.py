"""First fragment of the HT-050 canvas resize bridge script."""

CANVAS_RESIZE_JS_PART_A = """
(function() {
    if (window._htCanvasResizeBridgeLoaded) return;
    window._htCanvasResizeBridgeLoaded = true;

    var HT_NODE_MIN_SIZE = 40;
    var HT_COMPOUND_MIN_PADDING = 20;
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
        var selectedNodes = state.cy ? state.cy.$('node:selected') : null;
        var lockSubject = selectedNodes && selectedNodes.length ? selectedNodes.first() : node;
        var selectionLocked = !!(
            window._htPendingPublishedReparentSelectionLocked
            && window._htPendingPublishedReparentSelectionLocked(lockSubject)
        );
        return selectionLocked || data.ghost === true || data.editable === false || node.hasClass('ghost');
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
"""
