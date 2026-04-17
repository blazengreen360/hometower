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

    function _updateToolbarState() {
        var state = window._htUndoState;
        var undoTop = state.undoStack.length ? state.undoStack[state.undoStack.length - 1] : null;
        var redoTop = state.redoStack.length ? state.redoStack[state.redoStack.length - 1] : null;
        var readonly = !!window.HT_READONLY;

        var undoButton = document.getElementById('ht-undo-button');
        if (undoButton) {
            undoButton.disabled = readonly || state.busy || state.undoStack.length === 0;
            undoButton.title = undoTop ? ('Undo: ' + String(undoTop.label || 'action')) : 'Undo unavailable';
        }

        var redoButton = document.getElementById('ht-redo-button');
        if (redoButton) {
            redoButton.disabled = readonly || state.busy || state.redoStack.length === 0;
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

    function _snapshotNodeIds(snapshot) {
        var ids = {};
        if (!snapshot || !Array.isArray(snapshot.nodes)) return ids;
        snapshot.nodes.forEach(function(node) {
            var data = node && node.data;
            if (!data || !data.id) return;
            ids[String(data.id)] = true;
        });
        return ids;
    }

    function _applySnapshotRemoval(snapshot) {
        if (!window._cy || !snapshot) return;
        if (Array.isArray(snapshot.edges)) {
            snapshot.edges.forEach(function(edge) {
                var data = edge && edge.data;
                if (!data || !data.id) return;
                var found = window._cy.getElementById(String(data.id));
                if (found && found.length) found.remove();
            });
        }
        if (Array.isArray(snapshot.nodes)) {
            snapshot.nodes.forEach(function(node) {
                var data = node && node.data;
                if (!data || !data.id) return;
                var found = window._cy.getElementById(String(data.id));
                if (found && found.length) found.remove();
            });
        }
    }

    function _applySnapshotRestore(snapshot) {
        if (!window._cy || !snapshot) return;
        var nodeIds = _snapshotNodeIds(snapshot);
        if (Array.isArray(snapshot.nodes)) {
            snapshot.nodes.forEach(function(node) {
                var data = node && node.data;
                if (!data || !data.id) return;
                if (window._cy.getElementById(String(data.id)).length) return;
                window._cy.add(node);
            });
        }
        if (Array.isArray(snapshot.edges)) {
            snapshot.edges.forEach(function(edge) {
                var data = edge && edge.data;
                if (!data || !data.id) return;
                var sourceId = String(data.source || '');
                var targetId = String(data.target || '');
                if (!sourceId || !targetId) return;
                if (!window._cy.getElementById(sourceId).length) return;
                if (!window._cy.getElementById(targetId).length) return;
                if (window._cy.getElementById(String(data.id)).length) return;
                window._cy.add(edge);
            });
        }
    }

    function _addEdge(payload) {
        if (!window._cy || !payload) return;
        var connectionId = _edgeId(payload);
        if (!connectionId) return;
        if (window._cy.getElementById(connectionId).length) return;

        var sourceId = String(payload.source_id || payload.source || '');
        var targetId = String(payload.target_id || payload.target || '');
        if (!sourceId || !targetId) return;

        var rawLabel = String(payload.label || '');
        var escape = window._htEscapeHtml || function(s) { return String(s); };
        var edgePayload = {
            id: connectionId,
            source: sourceId,
            target: targetId,
            label: escape(rawLabel),
            raw_label: rawLabel,
            connection_type: String(payload.connection_type || payload.type || 'Ethernet')
        };

        if (window.addEdgeToCanvas) {
            window.addEdgeToCanvas(edgePayload);
            return;
        }

        window._cy.add({ group: 'edges', data: edgePayload });
    }

    function _removeEdge(payload) {
        if (!window._cy || !payload) return;
        var connectionId = _edgeId(payload);
        if (!connectionId) return;
        var edge = window._cy.getElementById(connectionId);
        if (edge && edge.length) edge.remove();
    }

    function _applyMove(payload, isUndo) {
        if (!window._cy || !payload || !Array.isArray(payload.nodes)) return;
        payload.nodes.forEach(function(item) {
            if (!item || !item.id) return;
            var node = window._cy.getElementById(String(item.id));
            if (!node || !node.length) return;
            var position = isUndo ? item.from : item.to;
            if (!position) return;
            node.position(position);
        });
    }

    function _patchNode(payload) {
        if (!window._cy || !payload || !payload.node_id || !payload.patch) return;
        var node = window._cy.getElementById(String(payload.node_id));
        if (!node || !node.length) return;
        var patch = payload.patch;
        var escape = window._htEscapeHtml || function(s) { return String(s); };

        if (Object.prototype.hasOwnProperty.call(patch, 'name')) {
            var name = patch.name == null ? '' : String(patch.name);
            node.data('raw_name', name);
            node.data('label', escape(name));
        }
        if (Object.prototype.hasOwnProperty.call(patch, 'status')) {
            var status = patch.status == null ? '' : String(patch.status);
            node.data('status', escape(status));
        }
        if (Object.prototype.hasOwnProperty.call(patch, 'version')) {
            node.data('version', Number(patch.version));
        }
    }

    window._htApplyUndoNodePatch = function(nodeId, patch) {
        _patchNode({ node_id: nodeId, patch: patch || {} });
    };

    function _applyGraphPatch(patch) {
        if (!patch || typeof patch !== 'object') return;
        var op = String(patch.op || '');
        if (op === 'add_edge') {
            _addEdge(patch.edge || patch.payload || {});
            return;
        }
        if (op === 'remove_edge') {
            _removeEdge({ connection_id: patch.connection_id || patch.edge_id });
            return;
        }
        if (op === 'remove_node_set') {
            _applySnapshotRemoval(patch.snapshot || {});
            return;
        }
        if (op === 'restore_node_set') {
            _applySnapshotRestore(patch.snapshot || {});
            return;
        }
        if (op === 'patch_node') {
            _patchNode({ node_id: patch.node_id, patch: patch.patch || {} });
        }
    }

"""
