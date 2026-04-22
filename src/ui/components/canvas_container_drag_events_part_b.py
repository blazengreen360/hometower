"""Container drag event JS fragment B (drop-parent resolution helpers)."""

CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_B = """
        function _htRenderedBounds(node) {
            if (!node || !node.length || !node.renderedBoundingBox) return null;
            return node.renderedBoundingBox({ includeLabels: false, includeOverlays: false });
        }

        function _htContainsRenderedPoint(parentBox, x, y, tol) {
            return !!parentBox
                && x >= (parentBox.x1 - tol)
                && x <= (parentBox.x2 + tol)
                && y >= (parentBox.y1 - tol)
                && y <= (parentBox.y2 + tol);
        }

        function _htIntersectionArea(a, b) {
            if (!a || !b) return 0;
            var x1 = Math.max(a.x1, b.x1);
            var y1 = Math.max(a.y1, b.y1);
            var x2 = Math.min(a.x2, b.x2);
            var y2 = Math.min(a.y2, b.y2);
            if (x2 <= x1 || y2 <= y1) return 0;
            return (x2 - x1) * (y2 - y1);
        }

        function _htNodeDropPoint(node) {
            if (!node || !node.length) return { x: 0, y: 0 };
            var box = node.boundingBox
                ? node.boundingBox({ includeLabels: false, includeOverlays: false })
                : null;
            if (box) {
                return {
                    x: (box.x1 + box.x2) / 2,
                    y: (box.y1 + box.y2) / 2
                };
            }
            var position = node.position ? node.position() : { x: 0, y: 0 };
            return { x: position.x, y: position.y };
        }

        function _htDropCandidateIsLocked(node) {
            if (!node || !node.length) return true;
            var data = node.data ? (node.data() || {}) : {};
            return data.ghost === true || data.editable === false || node.hasClass('ghost');
        }

        function _htCollectDropParentCandidates(node, ignoredParentId, frozenParentId, frozenParentBounds) {
            var nodePoint = _htNodeDropPoint(node);
            var nodeId = String(node.id());
            var ignoredId = _htNormalizeParentId(ignoredParentId);
            var frozenId = _htNormalizeParentId(frozenParentId);
            var ranked = [];
            cy.nodes(':parent, .container').forEach(function(compound) {
                var compoundId = String(compound.id());
                if (compoundId === nodeId || compoundId === ignoredId || _htDropCandidateIsLocked(compound)) return;
                if (compound.ancestors().filter(function(ancestorNode) {
                    return String(ancestorNode.id()) === nodeId;
                }).length > 0) { return; }
                var box = compoundId === frozenId && frozenParentBounds
                    ? frozenParentBounds
                    : compound.boundingBox({ includeLabels: false, includeOverlays: false });
                if (!_htContainsRenderedPoint(box, nodePoint.x, nodePoint.y, 0)) return;
                var width = Math.max(0, box.x2 - box.x1);
                var height = Math.max(0, box.y2 - box.y1);
                ranked.push({
                    id: compoundId,
                    candidateDepth: Number(compound.ancestors().length || 0),
                    candidateArea: width * height,
                    candidateCenterDistance: Math.hypot(
                        nodePoint.x - ((box.x1 + box.x2) / 2),
                        nodePoint.y - ((box.y1 + box.y2) / 2)
                    )
                });
            });
            ranked.sort(function(a, b) {
                if (a.candidateDepth !== b.candidateDepth) return b.candidateDepth - a.candidateDepth;
                if (a.candidateArea !== b.candidateArea) return a.candidateArea - b.candidateArea;
                if (a.candidateCenterDistance !== b.candidateCenterDistance) {
                    return a.candidateCenterDistance - b.candidateCenterDistance;
                }
                return String(a.id).localeCompare(String(b.id));
            });
            return ranked;
        }

        function _htResolveDropParent(node, frozenParentId, frozenParentBounds) {
            var ranked = _htCollectDropParentCandidates(node, null, frozenParentId, frozenParentBounds);
            return ranked.length ? _htNormalizeParentId(ranked[0].id) : null;
        }

        function _htResolveDropParentIgnoring(node, ignoreParentId) {
            var ignoredParentId = _htNormalizeParentId(ignoreParentId);
            var ranked = _htCollectDropParentCandidates(node, ignoredParentId, null, null);
            return ranked.length ? _htNormalizeParentId(ranked[0].id) : null;
        }

        function _htResolveDetachAwareDropParent(node, origin) {
            var originParentId = _htNormalizeParentId(origin && origin.parentId);
            var effectiveOriginParentBox = (origin && origin.dragParentBox) || (origin && origin.parentBox);
            var resolvedParent = _htResolveDropParent(node, originParentId, effectiveOriginParentBox);
            if (resolvedParent && resolvedParent !== originParentId) {
                return resolvedParent;
            }
            var parent = originParentId ? cy.getElementById(originParentId) : null;
            var parentBox = parent && parent.length
                ? _htRenderedBounds(parent)
                : (origin && origin.parentRenderedBounds ? origin.parentRenderedBounds : null);
            if (parentBox) {
                var nodeBox = _htRenderedBounds(node);
                if (nodeBox) {
                    var centerX = (nodeBox.x1 + nodeBox.x2) / 2;
                    var centerY = (nodeBox.y1 + nodeBox.y2) / 2;
                    var tol = 4;
                    if (_htContainsRenderedPoint(parentBox, centerX, centerY, tol)) {
                        return originParentId;
                    }
                }
            }
            var fallbackParent = _htResolveDropParentIgnoring(node, originParentId);
            if (fallbackParent) return fallbackParent;
            return null;
        }

        function _htSnapBackNode(node) {
            var origin = window._htContainerDragOrigin && window._htContainerDragOrigin[node.id()];
            if (!origin) return;
            if (_htNormalizeParentId(node.data('parent')) !== origin.parentId) {
                node.move({ parent: origin.parentId });
            }
            node.animate({
                position: {
                    x: origin.position.x,
                    y: origin.position.y
                }
            }, {
                duration: 200,
                easing: 'ease-out'
            });
            if (origin.parentId && window._cy) {
                var parentNode = window._cy.getElementById(String(origin.parentId));
                if (parentNode && parentNode.length) {
                    parentNode.removeStyle('min-width min-height width height');
                }
            }
            _htClearDragOrigin(node.id());
        }
"""
