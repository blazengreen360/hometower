"""Action/request JS segment for canvas undo/redo stack behavior (HT-032)."""

CANVAS_UNDO_JS_ACTIONS = """
    function _emit(eventName, payload) {
        if (typeof emitEvent !== 'function') {
            return false;
        }
        emitEvent(eventName, payload);
        return true;
    }

    function _dispatchStencilRefreshAfterSettle() {
        var dispatch = function() {
            document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
        };
        if (window.requestAnimationFrame) {
            window.requestAnimationFrame(dispatch);
            return;
        }
        window.setTimeout(dispatch, 0);
    }

    async function _waitForAutosaveSettled() {
        if (window._htFlushAutosave) {
            window._htFlushAutosave();
        }
        var attempts = 0;
        while (attempts < 60) {
            if (!window._htAutosaveInFlight && !window._htAutosaveRequestInFlight && !window._htAutosavePending) {
                return true;
            }
            await new Promise(function(resolve) { window.setTimeout(resolve, 50); });
            attempts += 1;
        }
        return false;
    }

    function _applyLocalOp(op, payload, isUndo) {
        if (op === 'move_node') {
            _applyMove(payload, isUndo);
            return;
        }
        if (op === 'reparent_node') {
            _reparentNode({
                node_id: payload.node_id || payload.device_id,
                parent_id: isUndo ? payload.from_parent_id : payload.to_parent_id,
                rendered_position: isUndo ? payload.from_rendered_position : payload.to_rendered_position,
                version: payload.version_cursor
            });
            return;
        }
        if (op === 'remove_snapshot') {
            _applySnapshotRemoval(payload);
            document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
            return;
        }
        if (op === 'restore_snapshot') {
            _applySnapshotRestore(payload);
            _dispatchStencilRefreshAfterSettle();
            return;
        }
        if (op === 'add_edge_local') {
            _addEdge(payload);
            return;
        }
        if (op === 'remove_edge_local') {
            _removeEdge(payload);
        }
    }

    function _requestApiDirection(direction) {
        var source = direction === 'undo' ? window._htUndoState.undoStack : window._htUndoState.redoStack;
        if (!source.length) return;
        var entry = source[source.length - 1];
        var action = direction === 'undo' ? entry.reverse : entry.forward;
        var op = String(action && action.op || '');
        if (window._htUndoState.busy && !_htEntryCanRunWhileBusy(entry)) return;

        if (entry.execution === 'local') {
            _applyLocalOp(String(action.op || ''), action.payload || {}, direction === 'undo');
            source.pop();
            if (direction === 'undo') {
                window._htUndoState.redoStack.push(entry);
            } else {
                window._htUndoState.undoStack.push(entry);
                _trimUndoStack();
            }
            if (window.scheduleAutosave) window.scheduleAutosave(800);
            _updateToolbarState();
            return;
        }

        window._htUndoState.busy = true;
        window._htUndoState.pending = { direction: direction, entry_id: String(entry.entry_id || '') };

        var emitUndoRequest = function() {
            if (!_emit('ht_canvas_undo_request', { direction: direction, entry: entry })) {
                window._htResolveUndoApiFailure(direction, String(entry.entry_id || ''), 'Undo bridge unavailable');
            }
        };

        if (op === 'reparent_device') {
            _waitForAutosaveSettled().then(function(autosaveSettled) {
                if (!autosaveSettled) {
                    window._htResolveUndoApiFailure(direction, String(entry.entry_id || ''), 'Autosave not settled');
                    return;
                }
                emitUndoRequest();
            });
            _updateToolbarState();
            return;
        }

        emitUndoRequest();
        _updateToolbarState();
    }

    window._htRequestCanvasAction = function(action) {
        if (window.HT_READONLY || !action || typeof action !== 'object') return;
        if (window._htUndoState.busy) return;

        var entryId = String(action.entry_id || crypto.randomUUID());
        window._htUndoState.busy = true;
        window._htUndoState.pending = { direction: 'forward', entry_id: entryId };
        _updateToolbarState();

        var emitActionRequest = function() {
            if (!_emit('ht_canvas_action_request', { entry_id: entryId, action: action })) {
                window._htResolveUndoApiFailure('forward', entryId, 'Undo bridge unavailable');
            }
        };

        if (action.type === 'delete_published_node') {
            _waitForAutosaveSettled().then(function(autosaveSettled) {
                if (!autosaveSettled) {
                    window._htResolveUndoApiFailure('forward', entryId, 'Autosave not settled');
                    return;
                }
                emitActionRequest();
            });
            return;
        }

        emitActionRequest();
    };

    window._htRequestUndo = function() {
        if (window.HT_READONLY) return;
        _requestApiDirection('undo');
    };

    window._htRequestRedo = function() {
        if (window.HT_READONLY) return;
        _requestApiDirection('redo');
    };
"""
