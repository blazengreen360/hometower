"""Local-entry JS helpers for canvas undo/redo stack behavior (HT-032)."""

CANVAS_UNDO_JS_LOCAL = """
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
"""