"""Container drag event JS fragment C (runtime event bindings)."""

CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_C = """
        function _htClearDragIndicators() {
            if (!window._cy) return;
            window._cy.$('.ht-drop-target').removeClass('ht-drop-target');
            window._cy.$('.ht-will-detach').removeClass('ht-will-detach');
        }

        window._htClearDragIndicators = _htClearDragIndicators;

        cy.on('grab', 'node', function(evt) {
            var node = evt.target;
            if (window._htNormalizeSelectionForContainerDrag) {
                window._htNormalizeSelectionForContainerDrag(node);
            }
            var parent = node.parent ? node.parent() : null;
            var parentBox = parent && parent.length
                ? parent.boundingBox({ includeLabels: false, includeOverlays: false })
                : null;
            window._htContainerDragOrigin = window._htContainerDragOrigin || {};
            window._htContainerDragOrigin[node.id()] = {
                parentId: _htNormalizeParentId(node.data('parent')),
                wasSelected: !!(node.selected && node.selected()),
                isContainerNode: !!((node.hasClass && node.hasClass('container')) || (node.isParent && node.isParent())),
                position: { x: node.position().x, y: node.position().y },
                renderedPosition: _htCurrentRenderedPosition(node),
                parentBox: _htCloneBounds(parentBox),
                parentRenderedBounds: parent && parent.length ? _htRenderedBounds(parent) : null,
                dragParentBox: _htCloneBounds(parentBox),
            };

            var existingOwnership = _htGetPointerOwnership(node.id());
            var originalEvent = evt.originalEvent || {};
            var pointerX = Number(
                existingOwnership && Number.isFinite(Number(existingOwnership.pointerX))
                    ? Number(existingOwnership.pointerX)
                    : Number(originalEvent.clientX || 0)
            );
            var pointerY = Number(
                existingOwnership && Number.isFinite(Number(existingOwnership.pointerY))
                    ? Number(existingOwnership.pointerY)
                    : Number(originalEvent.clientY || 0)
            );
            var pointerId = existingOwnership
                ? (existingOwnership.pointerId || null)
                : (originalEvent.pointerId || null);
            var selectedAtPointerdown = !!(
                (existingOwnership && existingOwnership.selectedAtPointerdown)
                || (node.selected && node.selected())
            );

            window._htContainerPointerOwnership = window._htContainerPointerOwnership || {};
            window._htContainerPointerOwnership[node.id()] = {
                pointerX: pointerX,
                pointerY: pointerY,
                pointerId: pointerId,
                armed: true,
                ownershipFrozen: true,
                selectedAtPointerdown: selectedAtPointerdown
            };

            cy.$('node:selected').forEach(function(selectedNode) {
                if (String(selectedNode.id()) === String(node.id())) return;
                window._htContainerPointerOwnership[selectedNode.id()] = {
                    pointerX: pointerX,
                    pointerY: pointerY,
                    pointerId: pointerId,
                    armed: true,
                    ownershipFrozen: true,
                    selectedAtPointerdown: true
                };
                if (!window._htContainerDragOrigin[selectedNode.id()]) {
                    var selParent = selectedNode.parent ? selectedNode.parent() : null;
                    var selParentBox = selParent && selParent.length
                        ? selParent.boundingBox({ includeLabels: false, includeOverlays: false })
                        : null;
                    window._htContainerDragOrigin[selectedNode.id()] = {
                        parentId: _htNormalizeParentId(selectedNode.data('parent')),
                        wasSelected: true,
                        isContainerNode: !!((selectedNode.hasClass && selectedNode.hasClass('container')) || (selectedNode.isParent && selectedNode.isParent())),
                        position: { x: selectedNode.position().x, y: selectedNode.position().y },
                        renderedPosition: _htCurrentRenderedPosition(selectedNode),
                        parentBox: _htCloneBounds(selParentBox),
                        parentRenderedBounds: selParent && selParent.length ? _htRenderedBounds(selParent) : null,
                        dragParentBox: _htCloneBounds(selParentBox),
                    };
                }
            });

            window._htContainerGestureOwner = {
                nodeId: String(node.id()),
                isContainerNode: !!((node.hasClass && node.hasClass('container')) || (node.isParent && node.isParent()))
            };
            window._htContainerDragInProgress = true;
        });

        cy.on('pointerdown', 'node', function(evt) {
            if (window.HT_READONLY) {
                _htCancelContainerDrag('readonly-cancel');
                return;
            }
            var node = evt.target;
            var selectedAtPointerdown = !!(node.selected && node.selected());
            var originalEvent = evt.originalEvent || {};
            window._htContainerPointerOwnership = window._htContainerPointerOwnership || {};
            window._htContainerPointerOwnership[node.id()] = {
                pointerX: Number(originalEvent.clientX || 0),
                pointerY: Number(originalEvent.clientY || 0),
                pointerId: originalEvent.pointerId || null,
                armed: true,
                ownershipFrozen: true,
                selectedAtPointerdown: selectedAtPointerdown
            };
            window._htContainerGestureOwner = {
                nodeId: String(node.id()),
                isContainerNode: !!((node.hasClass && node.hasClass('container')) || (node.isParent && node.isParent()))
            };
        });

        cy.on('drag', 'node', function(evt) {
            if (window.HT_READONLY) {
                _htCancelContainerDrag('readonly-cancel');
                return;
            }
            var node = evt.target;
            if (node.isParent && node.isParent()) return;

            var origin = window._htContainerDragOrigin && window._htContainerDragOrigin[node.id()];
            var originParentId = origin ? origin.parentId : _htNormalizeParentId(node.data('parent'));
            if (window._htMaybeGrowContainerForDraggedChild) {
                window._htMaybeGrowContainerForDraggedChild(node);
            }
            var prospective = _htResolveDetachAwareDropParent(node, origin);

            window._cy.$('.ht-drop-target').removeClass('ht-drop-target');
            window._cy.$('.ht-will-detach').removeClass('ht-will-detach');

            if (prospective && prospective !== originParentId) {
                var dropTarget = window._cy.getElementById(String(prospective));
                if (dropTarget && dropTarget.length) dropTarget.addClass('ht-drop-target');
            } else if (!prospective && originParentId) {
                var originParent = window._cy.getElementById(String(originParentId));
                if (originParent && originParent.length) originParent.addClass('ht-will-detach');
            }
        });

        document.addEventListener('ht:node-remove-from-container', function(evt) {
            if (window.HT_READONLY) return;
            var d = evt.detail || {};
            if (!d.id) return;
            window._htRequestDetachToTopLevel(d.id);
        });

        cy.on('dragfree', 'node', function(evt) {
            _htClearDragIndicators();
            if (window.HT_READONLY) {
                _htCancelContainerDrag('readonly-cancel');
                return;
            }
            var node = evt.target;
            var nodeId = node.id();
            var owner = window._htContainerGestureOwner || null;
            if (owner && String(owner.nodeId) !== String(nodeId)) {
                var ownerIsAncestor = !!(
                    node.ancestors
                    && node.ancestors().filter(function(ancestorNode) {
                        return String(ancestorNode.id()) === String(owner.nodeId);
                    }).length > 0
                );
                if (owner.isContainerNode && ownerIsAncestor) {
                    _htFinalizeDragNode(nodeId, true);
                    return;
                }
            }
            if (window._htContainerDragCancelled) {
                window._htContainerDragCancelled = false;
                _htFinalizeDragNode(nodeId, true);
                return;
            }
            var ownership = _htGetPointerOwnership(nodeId);
            var releaseEvent = evt.originalEvent || {};
            var dragDistance = ownership
                ? Math.hypot(
                    Number(releaseEvent.clientX || ownership.pointerX) - Number(ownership.pointerX || 0),
                    Number(releaseEvent.clientY || ownership.pointerY) - Number(ownership.pointerY || 0)
                )
                : 5;
            if (dragDistance < 5) {
                _htFinalizeDragNode(nodeId, true);
                return;
            }
            var origin = window._htContainerDragOrigin && window._htContainerDragOrigin[nodeId];
            _htNormalizeSelectionForContainerDrag(node);
            var isSelectedForReparent = !!(
                (ownership && ownership.ownershipFrozen && ownership.selectedAtPointerdown)
                || (!ownership && origin && origin.wasSelected && dragDistance >= 5)
            );
            if (!isSelectedForReparent) {
                if (origin) {
                    _htSnapBackNode(node);
                    window._htContainerDragCancelled = true;
                }
                _htFinalizeDragNode(nodeId, true);
                return;
            }
            var currentParent = origin ? origin.parentId : _htNormalizeParentId(node.data('parent'));
            var targetParent = _htResolveDetachAwareDropParent(node, origin);
            var renderedPosition = _htCurrentRenderedPosition(node);

            if (targetParent === currentParent) {
                if (targetParent) {
                    var stayParentNode = cy.getElementById(targetParent);
                    if (stayParentNode && stayParentNode.length) {
                        stayParentNode.removeStyle('min-width min-height width height');
                    }
                }
                _htFinalizeDragNode(nodeId, true);
                return;
            }

            if (_htRequestNodeReparent(node, {
                fromParentId: currentParent,
                toParentId: targetParent,
                fromRenderedPosition: origin && origin.renderedPosition ? origin.renderedPosition : renderedPosition,
                toRenderedPosition: renderedPosition,
                label: targetParent ? 'Move into container' : 'Remove from container'
            })) {
                window._htStructuralDragMoveSuppression = window._htStructuralDragMoveSuppression || {};
                window._htStructuralDragMoveSuppression[String(nodeId)] = true;
                window._htContainerDragCancelled = true;
                window._htMoveGesture = null;
                if (currentParent) {
                    var sourceParentNode = cy.getElementById(currentParent);
                    if (sourceParentNode && sourceParentNode.length) {
                        sourceParentNode.removeStyle('min-width min-height width height');
                    }
                }
                _htFinalizeDragNode(nodeId, true);
                return;
            }

            _htSnapBackNode(node);
            _htFinalizeDragNode(nodeId, true);
        });
"""