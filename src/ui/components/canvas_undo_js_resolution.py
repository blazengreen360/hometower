"""Resolution/finalization JS segment for canvas undo/redo stack behavior (HT-032)."""

CANVAS_UNDO_JS_RESOLUTION = """
    window._htResolveUndoApiSuccess = function(direction, entryId, result) {
        var pending = window._htUndoState.pending;
        if (!pending || pending.direction !== direction || String(pending.entry_id) !== String(entryId)) {
            return;
        }

        if (result && result.graph_patch) {
            _applyGraphPatch(result.graph_patch);
        }
        if (result && result.stencil_patch) {
            _applyStencilPatch(result.stencil_patch);
        }
        _syncDiagramVersion(result || {});

        if (direction === 'forward') {
            if (result && result.entry) {
                window._htPushCommittedUndoEntry(result.entry);
            }
        } else {
            var source = direction === 'undo' ? window._htUndoState.undoStack : window._htUndoState.redoStack;
            var target = direction === 'undo' ? window._htUndoState.redoStack : window._htUndoState.undoStack;
            if (!source.length) {
                window._htUndoState.busy = false;
                window._htUndoState.pending = null;
                _updateToolbarState();
                return;
            }
            var top = source[source.length - 1];
            if (String(top.entry_id || '') !== String(entryId)) {
                window._htUndoState.busy = false;
                window._htUndoState.pending = null;
                _updateToolbarState();
                return;
            }
            if (result && result.entry_patch && typeof result.entry_patch === 'object') {
                top = Object.assign({}, top, result.entry_patch);
                source[source.length - 1] = top;
            }
            source.pop();
            target.push(top);
            if (direction === 'redo') _trimUndoStack();
        }

        window._htUndoState.busy = false;
        window._htUndoState.pending = null;
        _updateToolbarState();
    };

    window._htResolveUndoApiFailure = function(direction, entryId, message) {
        var pending = window._htUndoState.pending;
        if (!pending || pending.direction !== direction || String(pending.entry_id) !== String(entryId)) {
            return;
        }

        var prefix = direction === 'undo' ? 'Undo failed: ' : (direction === 'redo' ? 'Redo failed: ' : 'Action failed: ');
        _notify(prefix + String(message || 'Unknown error'), 'negative');
        window._htUndoState.busy = false;
        window._htUndoState.pending = null;
        _updateToolbarState();
    };

    window._htResetUndoState = function() {
        window._htUndoState.undoStack = [];
        window._htUndoState.redoStack = [];
        window._htUndoState.busy = false;
        window._htUndoState.pending = null;
        _updateToolbarState();
    };

    _updateToolbarState();
})();
"""
