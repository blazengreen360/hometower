"""Core JS helpers for canvas undo/redo stack operations (HT-032)."""

CANVAS_UNDO_JS_CORE = """
(function() {
    if (window._htUndoLoaded) return;
    window._htUndoLoaded = true;

    var HT_UNDO_MAX_ENTRIES = 50;
    window._htUndoState = {
        undoStack: [],
        redoStack: [],
        busy: false,
        pending: null,
    };

    function _notify(message, color) {
        if (window._htNotify) {
            window._htNotify(message, color || 'warning');
            return;
        }
        console.warn(message);
    }

    function _edgeId(payload) {
        return String(
            payload.connection_id
            || payload.id
            || ''
        );
    }

    function _syncDiagramVersion(result) {
        if (!result || !Array.isArray(result.modified_diagrams)) return;
        var activeDiagramId = window._htDiagramId;
        if (!activeDiagramId) return;
        result.modified_diagrams.forEach(function(row) {
            if (!row) return;
            if (String(row.diagram_id) !== String(activeDiagramId)) return;
            if (typeof row.version === 'number') {
                window._htDiagramVersion = row.version;
            }
        });
    }

    function _dispatchStencilEvent(name, detail) {
        if (typeof document === 'undefined' || !document.dispatchEvent || typeof CustomEvent !== 'function') {
            return;
        }
        document.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    }

    function _applyStencilPatch(patch) {
        if (!patch || typeof patch !== 'object') return;
        var op = String(patch.op || '');
        if (op === 'remove_published_device') {
            var deviceId = patch.device_id == null ? '' : String(patch.device_id);
            if (!deviceId) return;
            _dispatchStencilEvent('ht:stencil-device-removed', { deviceId: deviceId });
            return;
        }
        if (op === 'upsert_published_device' && patch.device && typeof patch.device === 'object') {
            _dispatchStencilEvent('ht:stencil-device-published', { device: patch.device });
        }
    }

    function _htEntryCanRunWhileBusy(entry) {
        return !!entry && entry.execution === 'local';
    }

    function _setToolbarButtonState(button, disabled) {
        if (!button) return;
        var isDisabled = !!disabled;
        button.disabled = isDisabled;
        if (isDisabled) {
            button.setAttribute('disabled', '');
        } else {
            button.removeAttribute('disabled');
        }
        button.setAttribute('aria-disabled', isDisabled ? 'true' : 'false');
        button.setAttribute('tabindex', isDisabled ? '-1' : '0');
        button.classList.toggle('disabled', isDisabled);
    }

    function _updateToolbarState() {
        var state = window._htUndoState;
        var undoTop = state.undoStack.length ? state.undoStack[state.undoStack.length - 1] : null;
        var redoTop = state.redoStack.length ? state.redoStack[state.redoStack.length - 1] : null;
        var readonly = !!window.HT_READONLY;

        var undoButton = document.getElementById('ht-undo-button');
        if (undoButton) {
            _setToolbarButtonState(
                undoButton,
                readonly || (state.busy && !_htEntryCanRunWhileBusy(undoTop)) || state.undoStack.length === 0
            );
            undoButton.title = undoTop ? ('Undo: ' + String(undoTop.label || 'action')) : 'Undo unavailable';
        }

        var redoButton = document.getElementById('ht-redo-button');
        if (redoButton) {
            _setToolbarButtonState(
                redoButton,
                readonly || (state.busy && !_htEntryCanRunWhileBusy(redoTop)) || state.redoStack.length === 0
            );
            redoButton.title = redoTop ? ('Redo: ' + String(redoTop.label || 'action')) : 'Redo unavailable';
        }

        document.dispatchEvent(new CustomEvent('ht:undo-state-changed', {
            detail: {
                undo_count: state.undoStack.length,
                redo_count: state.redoStack.length,
                busy: state.busy,
                undo_label: undoTop ? String(undoTop.label || '') : '',
                redo_label: redoTop ? String(redoTop.label || '') : ''
            }
        }));
    }

    function _trimUndoStack() {
        while (window._htUndoState.undoStack.length > HT_UNDO_MAX_ENTRIES) {
            window._htUndoState.undoStack.shift();
        }
    }

"""
