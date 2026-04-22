"""Container growth helpers for dragged child interactions."""

CANVAS_CONTAINER_ACTIONS_GROWTH_JS = """
        function _htGrowContainerForDraggedChild(node) {
            if (!node || !node.length || window.HT_READONLY) return;
            var parent = node.parent ? node.parent() : null;
            if (!parent || !parent.length) return;
            var origin = window._htContainerDragOrigin && window._htContainerDragOrigin[String(node.id())];
            var padding = 20;
            var parentBox = _htCloneBounds(origin && origin.dragParentBox)
                || _htCloneBounds(origin && origin.parentBox)
                || parent.boundingBox({ includeLabels: false, includeOverlays: false });
            var childBox = node.boundingBox({ includeLabels: false, includeOverlays: false });
            if (!parentBox || !childBox) return;

            var overflowLeft = Math.max(0, parentBox.x1 - childBox.x1 + padding);
            var overflowRight = Math.max(0, childBox.x2 - parentBox.x2 + padding);
            var overflowTop = Math.max(0, parentBox.y1 - childBox.y1 + padding);
            var overflowBottom = Math.max(0, childBox.y2 - parentBox.y2 + padding);
            if (childBox.x1 >= parentBox.x1 && childBox.x2 <= parentBox.x2
                    && childBox.y1 >= parentBox.y1 && childBox.y2 <= parentBox.y2) {
                return;
            }
            if (!overflowLeft && !overflowRight && !overflowTop && !overflowBottom) return;

            var currentWidth = Math.max(0, parentBox.x2 - parentBox.x1);
            var currentHeight = Math.max(0, parentBox.y2 - parentBox.y1);
            var nextWidth = currentWidth + overflowLeft + overflowRight;
            var nextHeight = currentHeight + overflowTop + overflowBottom;
            parent.style('width', nextWidth + 'px');
            parent.style('height', nextHeight + 'px');
            parent.style('min-width', nextWidth + 'px');
            parent.style('min-height', nextHeight + 'px');
            var nextCenterX = (parentBox.x1 + parentBox.x2) / 2 + (overflowRight - overflowLeft) / 2;
            var nextCenterY = (parentBox.y1 + parentBox.y2) / 2 + (overflowBottom - overflowTop) / 2;
            if (origin) {
                origin.dragParentBox = { x1: nextCenterX - (nextWidth / 2), y1: nextCenterY - (nextHeight / 2), x2: nextCenterX + (nextWidth / 2), y2: nextCenterY + (nextHeight / 2) };
            }
        }

        window._htMaybeGrowContainerForDraggedChild = function(node) {
            if (!node || !node.length || window.HT_READONLY) return;
            window._htContainerGrowthRaf = window._htContainerGrowthRaf || {};
            var nodeId = String(node.id());
            if (window._htContainerGrowthRaf[nodeId]) return;
            window._htContainerGrowthRaf[nodeId] = window.requestAnimationFrame(function() {
                delete window._htContainerGrowthRaf[nodeId];
                _htGrowContainerForDraggedChild(node);
            });
        };
"""