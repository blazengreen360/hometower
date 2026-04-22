"""Container drag event JS fragment A (selection normalization and state helpers)."""

CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_A = """
        function _htSelectionDepth(node) {
            if (!node || !node.length || !node.ancestors) return 0;
            return Number(node.ancestors().length || 0);
        }

        function _htSelectedNodesForNormalization() {
            if (!window._cy) return [];
            var selected = [];
            window._cy.$('node:selected').forEach(function(selectedNode) {
                selected.push({
                    id: String(selectedNode.id()),
                    node: selectedNode,
                    depth: _htSelectionDepth(selectedNode)
                });
            });
            return selected;
        }

        function _htNormalizeSelectionMutualExclusion(candidates) {
            var sorted = (candidates || []).slice();
            sorted.sort(function(a, b) {
                if (a.depth !== b.depth) return a.depth - b.depth;
                return String(a.id).localeCompare(String(b.id));
            });

            var keep = [];
            var keepIds = {};
            sorted.forEach(function(candidate) {
                var hasSelectedAncestor = candidate.node.ancestors().filter(function(ancestorNode) {
                    return !!keepIds[String(ancestorNode.id())];
                }).length > 0;
                if (hasSelectedAncestor) return;

                keep = keep.filter(function(kept) {
                    var isDescendant = candidate.node.descendants().filter(function(descendantNode) {
                        return String(descendantNode.id()) === kept.id;
                    }).length > 0;
                    if (isDescendant) {
                        delete keepIds[kept.id];
                    }
                    return !isDescendant;
                });

                keep.push(candidate);
                keepIds[candidate.id] = true;
            });
            return keep;
        }

        function _htApplyNormalizedSelection(normalized) {
            if (!window._cy || window._htSelectionNormalizationInProgress) return;
            var keepIds = {};
            (normalized || []).forEach(function(item) {
                keepIds[String(item.id)] = true;
            });

            window._htSelectionNormalizationInProgress = true;
            window._cy.nodes().forEach(function(node) {
                var nodeId = String(node.id());
                var shouldBeSelected = !!keepIds[nodeId];
                var isSelected = !!(node.selected && node.selected());
                if (shouldBeSelected && !isSelected && node.select) node.select();
                if (!shouldBeSelected && isSelected && node.unselect) node.unselect();
            });
            window._htSelectionNormalizationInProgress = false;
        }

        function _htNormalizeSelectionForContainerDrag() {
            _htApplyNormalizedSelection(
                _htNormalizeSelectionMutualExclusion(_htSelectedNodesForNormalization())
            );
        }

        window._htNormalizeSelectionForContainerDrag = _htNormalizeSelectionForContainerDrag;

        function _htCancelContainerDrag(reason) {
            if (window._htClearDragIndicators) window._htClearDragIndicators();
            var nodeIds = window._htContainerDragOrigin ? Object.keys(window._htContainerDragOrigin) : [];
            var hadActiveDrag = !!(
                nodeIds.length
                || window._htContainerDragInProgress
                || window._htMoveGesture
                || window._htContainerGestureOwner
            );
            if (window._cy && nodeIds.length) {
                nodeIds.forEach(function(nodeId) {
                    var draggedNode = window._cy.getElementById(String(nodeId));
                    if (draggedNode && draggedNode.length) {
                        _htSnapBackNode(draggedNode);
                    }
                });
            }
            window._htContainerDragCancelled = true;
            if (window._htMoveGesture) {
                window._htMoveGesture = null;
            }
            window._htContainerDragOrigin = {};
            window._htContainerPointerOwnership = {};
            window._htContainerGestureOwner = null;
            window._htContainerDragInProgress = false;
            window._htDeferredContainerDragCancelReason = null;
            if (reason === 'readonly-cancel' && hadActiveDrag) {
                _notify('Container move canceled: canvas is read-only.', 'warning');
            }
        }

        function _htClearDragOrigin(nodeId) {
            if (!window._htContainerDragOrigin) return;
            delete window._htContainerDragOrigin[nodeId];
        }

        function _htGetPointerOwnership(nodeId) {
            var ownershipMap = window._htContainerPointerOwnership;
            if (!ownershipMap || typeof ownershipMap !== 'object') return null;
            return ownershipMap[String(nodeId)] || null;
        }

        function _htClearPointerOwnership(nodeId) {
            var ownershipMap = window._htContainerPointerOwnership;
            if (!ownershipMap || typeof ownershipMap !== 'object') {
                window._htContainerPointerOwnership = {};
            } else {
                delete ownershipMap[String(nodeId)];
            }
        }

        function _htFinalizeDragNode(nodeId, clearOrigin) {
            if (clearOrigin !== false) {
                _htClearDragOrigin(nodeId);
            }
            _htClearPointerOwnership(nodeId);
            var originMap = window._htContainerDragOrigin;
            var hasActiveOrigins = !!(originMap && Object.keys(originMap).length > 0);
            window._htContainerDragInProgress = hasActiveOrigins;
            if (!hasActiveOrigins) {
                window._htContainerGestureOwner = null;
            }
            if (!hasActiveOrigins && window._htDeferredContainerDragCancelReason) {
                var deferredReason = window._htDeferredContainerDragCancelReason;
                window._htDeferredContainerDragCancelReason = null;
                _htCancelContainerDrag(deferredReason);
            }
        }
"""
