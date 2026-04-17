"""Action/request JS segment for canvas undo/redo stack behavior (HT-032)."""

CANVAS_UNDO_JS_ACTIONS = """
    function _emit(eventName, payload) {
        if (typeof emitEvent !== 'function') {
            _notify('Undo bridge unavailable', 'negative');
            return false;
        }
        emitEvent(eventName, payload);
        return true;
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
        if (op === 'remove_snapshot') {
            _applySnapshotRemoval(payload);
            return;
        }
        if (op === 'restore_snapshot') {
            _applySnapshotRestore(payload);
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
        if (window._htUndoState.busy) return;
        var source = direction === 'undo' ? window._htUndoState.undoStack : window._htUndoState.redoStack;
        if (!source.length) return;
        var entry = source[source.length - 1];

        if (entry.execution === 'local') {
            var action = direction === 'undo' ? entry.reverse : entry.forward;
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
        if (!_emit('ht_canvas_undo_request', { direction: direction, entry: entry })) {
            window._htUndoState.busy = false;
            window._htUndoState.pending = null;
        }
        _updateToolbarState();
    }

    window._htSnapshotNodeSet = function(nodeLike) {
        if (!window._cy || !nodeLike) return { nodes: [], edges: [] };
        var node = nodeLike;
        if (nodeLike.length && typeof nodeLike.first === 'function') {
            node = nodeLike.first();
        }
        if (!node || !node.isNode || !node.isNode()) {
            return { nodes: [], edges: [] };
        }

        var scope = node;
        if (node.union && node.descendants) {
            scope = node.union(node.descendants());
        }

        var snapshotNodes = [];
        scope.forEach(function(n) { snapshotNodes.push(n.json()); });

        var nodeIds = _snapshotNodeIds({ nodes: snapshotNodes });
        var snapshotEdges = [];
        scope.connectedEdges().forEach(function(edge) {
            var data = edge.data() || {};
            var sourceId = String(data.source || '');
            var targetId = String(data.target || '');
            if (nodeIds[sourceId] || nodeIds[targetId]) {
                snapshotEdges.push(edge.json());
            }
        });

        return { nodes: snapshotNodes, edges: snapshotEdges };
    };

    window._htPushCommittedUndoEntry = function(entry) {
        if (!entry || typeof entry !== 'object') return;
        window._htUndoState.undoStack.push(entry);
        _trimUndoStack();
        window._htUndoState.redoStack = [];
        _updateToolbarState();
    };

    window._htCommitLocalRemoveFromView = function(el) {
        if (!window._cy || window.HT_READONLY) return;
        var snapshot = window._htSnapshotNodeSet(el);
        if (!snapshot.nodes.length) return;
        _applySnapshotRemoval(snapshot);
        if (window.scheduleAutosave) window.scheduleAutosave(800);
        document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
        _notify('Device removed from View.', 'info');
        window._htPushCommittedUndoEntry({
            entry_id: crypto.randomUUID(),
            type: 'remove_from_view',
            label: 'Remove from View',
            execution: 'local',
            forward: { op: 'remove_snapshot', payload: snapshot },
            reverse: { op: 'restore_snapshot', payload: snapshot }
        });
    };

    window._htCommitLocalDraftDelete = function(el) {
        if (!window._cy || window.HT_READONLY) return;
        var snapshot = window._htSnapshotNodeSet(el);
        if (!snapshot.nodes.length) return;
        _applySnapshotRemoval(snapshot);
        if (window._htUpdateDraftBadge) window._htUpdateDraftBadge();
        if (window.scheduleAutosave) window.scheduleAutosave(800);
        var firstNode = snapshot.nodes[0] || {};
        var data = firstNode.data || {};
        var label = String(data.raw_name || data.label || 'draft');
        window._htPushCommittedUndoEntry({
            entry_id: crypto.randomUUID(),
            type: 'delete_draft_node',
            label: 'Delete ' + label,
            execution: 'local',
            forward: { op: 'remove_snapshot', payload: snapshot },
            reverse: { op: 'restore_snapshot', payload: snapshot }
        });
    };

    window._htBeginMoveGesture = function(node) {
        if (!node || !node.id) return;
        var moving = node;
        if (node.union && node.descendants) {
            moving = node.union(node.descendants());
        }
        var start = [];
        moving.forEach(function(n) {
            var pos = n.position();
            start.push({ id: String(n.id()), from: { x: pos.x, y: pos.y } });
        });
        window._htMoveGesture = { nodes: start };
    };

    window._htCommitMoveGesture = function(node) {
        if (!window._cy || !window._htMoveGesture || !Array.isArray(window._htMoveGesture.nodes)) return;
        var updates = [];
        window._htMoveGesture.nodes.forEach(function(item) {
            var found = window._cy.getElementById(String(item.id));
            if (!found || !found.length) return;
            var toPos = found.position();
            if (item.from.x === toPos.x && item.from.y === toPos.y) return;
            updates.push({ id: String(item.id), from: item.from, to: { x: toPos.x, y: toPos.y } });
        });
        window._htMoveGesture = null;
        if (!updates.length) return;

        var data = node && node.data ? node.data() : {};
        var label = String(data.raw_name || data.label || node.id() || 'node');
        window._htPushCommittedUndoEntry({
            entry_id: crypto.randomUUID(),
            type: 'move_node',
            label: 'Move ' + label,
            execution: 'local',
            forward: { op: 'move_node', payload: { nodes: updates } },
            reverse: { op: 'move_node', payload: { nodes: updates } }
        });
    };

    window._htRequestCanvasAction = function(action) {
        if (window.HT_READONLY || !action || typeof action !== 'object') return;
        if (window._htUndoState.busy) return;

        var entryId = String(action.entry_id || crypto.randomUUID());
        window._htUndoState.busy = true;
        window._htUndoState.pending = { direction: 'forward', entry_id: entryId };
        _updateToolbarState();

        var emitActionRequest = function() {
            if (!_emit('ht_canvas_action_request', { entry_id: entryId, action: action })) {
                window._htUndoState.busy = false;
                window._htUndoState.pending = null;
                _updateToolbarState();
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
