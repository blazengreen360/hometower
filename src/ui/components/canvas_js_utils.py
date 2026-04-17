"""Cytoscape.js canvas utilities shared by the init template."""

from src.ui.components.canvas_js_autosave import CANVAS_AUTOSAVE_JS

CANVAS_UTILS_JS_TEMPLATE = CANVAS_AUTOSAVE_JS + """
(function() {
    function _htNodeEntries(rawElements) {
        if (Array.isArray(rawElements)) {
            rawElements.forEach(function(elem) {
                if (!elem || typeof elem !== 'object') return;
                if (!elem.group) elem.group = 'nodes';
            });
            return rawElements;
        }
        if (rawElements && typeof rawElements === 'object') {
            var nodes = Array.isArray(rawElements.nodes) ? rawElements.nodes : [];
            var edges = Array.isArray(rawElements.edges) ? rawElements.edges : [];
            nodes.forEach(function(node) { if (!node.group) node.group = 'nodes'; });
            edges.forEach(function(edge) { if (!edge.group) edge.group = 'edges'; });
            return nodes.concat(edges);
        }
        return [];
    }

    function _htStripLayoutMetadata(cytoscapeJson) {
        if (!cytoscapeJson) return null;
        var payload = JSON.parse(JSON.stringify(cytoscapeJson));
        delete payload._draft_cleanup_required;
        delete payload._draft_pruned_count;
        return payload;
    }

    function _htMarkSerializedNodesPositioned(rawElements) {
        _htNodeEntries(rawElements).forEach(function(elem) {
            if (!elem.group) elem.group = 'nodes';
            if (elem.group !== 'nodes') return;
            if (!elem.position) return;
            elem.data = elem.data || {};
            elem.data._positioned = true;
        });
    }

    function _htNodeElementsById(rawElements) {
        return _htNodeEntries(rawElements).reduce(function(byId, elem) {
            if (!elem || typeof elem !== 'object') return byId;
            var data = elem.data || {};
            if (elem.group === 'edges' || (data.source != null && data.target != null)) return byId;
            if (data.id != null) byId[String(data.id)] = elem;
            return byId;
        }, {});
    }

    function _htNodeBypassStylePx(node, propertyName) {
        var styleState = node && node.pstyle ? node.pstyle(propertyName) : null;
        if (!styleState || styleState.bypass !== true) return null;
        if (typeof styleState.strValue === 'string' && styleState.strValue.trim() !== '') return styleState.strValue;
        if (typeof styleState.pfValue === 'number' && Number.isFinite(styleState.pfValue)) return String(styleState.pfValue) + 'px';
        var fallback = node && node.style ? node.style(propertyName) : '';
        return (typeof fallback === 'string' && fallback.trim() !== '') ? fallback : null;
    }

    function _htSerializeNodeSizeStyles(cy, rawElements) {
        if (!cy) return;
        var nodesById = _htNodeElementsById(rawElements);
        cy.nodes().forEach(function(node) {
            var entry = nodesById[node.id()];
            if (!entry) return;
            var style = (entry.style && typeof entry.style === 'object') ? entry.style : {};
            var width = _htNodeBypassStylePx(node, 'width');
            var height = _htNodeBypassStylePx(node, 'height');
            if (width !== null) style.width = width; else delete style.width;
            if (height !== null) style.height = height; else delete style.height;
            if (Object.keys(style).length > 0) entry.style = style; else delete entry.style;
        });
    }

    function _htReapplyNodeSizeStyles(cy, rawElements) {
        if (!cy) return;
        var nodesById = _htNodeElementsById(rawElements);
        Object.keys(nodesById).forEach(function(nodeId) {
            var style = nodesById[nodeId] && nodesById[nodeId].style;
            if (!style || typeof style !== 'object') return;
            var node = cy.getElementById(nodeId);
            if (!node || !node.length) return;
            if (style.width != null && String(style.width).trim() !== '') node.style('width', String(style.width));
            if (style.height != null && String(style.height).trim() !== '') node.style('height', String(style.height));
        });
    }

    window._htHasSavedNodePositions = function(cytoscapeJson) {
        return _htNodeEntries(cytoscapeJson && cytoscapeJson.elements).some(function(elem) {
            return elem.group === 'nodes'
                && !!elem.position
                && typeof elem.position.x === 'number'
                && typeof elem.position.y === 'number';
        });
    };

    window._htHasSavedViewport = function(cytoscapeJson) {
        return !!(cytoscapeJson && typeof cytoscapeJson.zoom === 'number' && cytoscapeJson.pan && typeof cytoscapeJson.pan.x === 'number' && typeof cytoscapeJson.pan.y === 'number');
    };

    window._htRestoreViewport = function(cy, cytoscapeJson) {
        if (!cy || !window._htHasSavedViewport(cytoscapeJson)) return;
        cy.zoom(cytoscapeJson.zoom);
        cy.pan(cytoscapeJson.pan);
    };

    window._htPersistPrunedLayoutCleanup = function(cytoscapeJson) {
        if (!cytoscapeJson || !cytoscapeJson._draft_cleanup_required) return;
        if (window.HT_CAN_PATCH_DIAGRAMS !== true || !window._htTopologyId) return;
        if (window._htDraftCleanupInFlight) return;
        var prunedCount = Number(cytoscapeJson._draft_pruned_count || 0);
        var payload = _htStripLayoutMetadata(cytoscapeJson);
        if (!payload) return;
        cytoscapeJson._draft_cleanup_required = false;
        window._htDraftCleanupInFlight = true;
        console.info('[Hometower] Pruned ' + prunedCount + ' orphaned draft nodes from saved layout.');
        fetch('/api/topologies/' + window._htTopologyId + '/personal-draft', {
            method: 'PUT',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cytoscape_json: payload,
                base_version: window._htDraftVersion != null ? window._htDraftVersion : null
            })
        }).then(function(r) {
            if (!r.ok) return null;
            return r.json();
        }).then(function(data) {
            if (data && data.version != null) window._htDraftVersion = data.version;
        }).finally(function() {
            window._htDraftCleanupInFlight = false;
        });
    };

    window.getCanvasJson = function() {
        if (!window._cy) return null;
        var json = window._cy.json();
        _htMarkSerializedNodesPositioned(json.elements);
        _htSerializeNodeSizeStyles(window._cy, json.elements);
        var collapsedNodes = [];
        window._cy.nodes().forEach(function(n) {
            if (n.data('_collapsed')) collapsedNodes.push(n.id());
        });
        return {
            elements: json.elements,
            zoom: window._cy.zoom(),
            pan: window._cy.pan(),
            collapsedNodes: collapsedNodes
        };
    };

    window.addNodeToCanvas = function(nodeData) {
        if (!window._cy) return;
        nodeData = nodeData || {};
        nodeData._positioned = true;
        window._cy.add({ data: nodeData, position: { x: nodeData.x || 200, y: nodeData.y || 200 } });
    };

    window.addEdgeToCanvas = function(edgeData) {
        if (!window._cy) return;
        if (window._cy.getElementById(edgeData.id).length > 0) return;
        window._cy.add({ group: 'edges', data: edgeData });
    };

    function _htApplyCollapsedSnapshot(cy, cytoscapeJson) {
        var collapsedList = Array.isArray(cytoscapeJson && cytoscapeJson.collapsedNodes)
            ? cytoscapeJson.collapsedNodes
            : [];
        var collapsedSet = {};
        collapsedList.forEach(function(nodeId) {
            collapsedSet[String(nodeId)] = true;
        });

        cy.nodes().forEach(function(node) {
            node.data('_collapsed', false);
            node.removeClass('collapsed');
            node.children().forEach(function(child) {
                child.style('display', 'element');
                child.connectedEdges().style('display', 'element');
            });
        });

        cy.nodes().forEach(function(node) {
            if (!collapsedSet[node.id()]) return;
            node.data('_collapsed', true);
            node.addClass('collapsed');
            node.children().forEach(function(child) {
                child.style('display', 'none');
                child.connectedEdges().forEach(function(edge) {
                    var srcParent = edge.source().data('parent');
                    var tgtParent = edge.target().data('parent');
                    if (srcParent === node.id() && tgtParent === node.id()) {
                        edge.style('display', 'none');
                    }
                });
            });
        });
    }

    function _htDispatchRestoreSummary(cytoscapeJson) {
        var summary = (cytoscapeJson && typeof cytoscapeJson === 'object')
            ? (cytoscapeJson.restore_summary || null)
            : null;
        window._htRestoreSummary = summary;
        document.dispatchEvent(new CustomEvent('ht:restore-summary-updated', {
            detail: { restore_summary: summary }
        }));
    }

    window.applyTopologySnapshot = function(cytoscapeJson) {
        if (!window._cy || !cytoscapeJson) return;
        var payload = JSON.parse(JSON.stringify(cytoscapeJson));
        var entries = _htNodeEntries(payload.elements);
        _htMarkSerializedNodesPositioned(payload.elements);

        window._cy.elements().remove();
        if (entries.length > 0) {
            window._cy.add(entries);
            _htReapplyNodeSizeStyles(window._cy, payload.elements);
        }

        _htApplyCollapsedSnapshot(window._cy, payload);
        if (window._htHasSavedViewport(payload)) {
            window._htRestoreViewport(window._cy, payload);
        } else if (window._cy.elements().length > 0) {
            window._cy.fit(undefined, 40);
        }
        if (window._htApplyNodeEditability) window._htApplyNodeEditability(window._cy);
        if (window._htResizeSyncFromSelection) window._htResizeSyncFromSelection();
        window._htPersistPrunedLayoutCleanup(payload);
        _htDispatchRestoreSummary(payload);
    };

    window.applyLayoutPositions = function(cytoscapeJson) {
        window.applyTopologySnapshot(cytoscapeJson);
    };

    window.updateCyTheme = function(stylesJson) {
        if (!window._cy || window._htThemeUpdating) return;
        window._htThemeUpdating = true;
        try {
            window._cy.style().fromJson(JSON.parse(stylesJson)).update();
        } finally {
            window._htThemeUpdating = false;
        }
    };
})();
"""
