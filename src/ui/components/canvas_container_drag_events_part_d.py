"""Container drag event JS fragment D (selection-time and interruption hooks)."""

CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_D = """
        cy.on('select unselect boxselect', 'node', function() {
            if (window._htSelectionNormalizationInProgress) return;
            _htNormalizeSelectionForContainerDrag();
        });

        document.addEventListener('pointercancel', function() {
            _htCancelContainerDrag('pointercancel');
        });

        document.addEventListener('keydown', function(event) {
            if (!event || event.key !== 'Escape') return;
            _htCancelContainerDrag('escape');
        });

        window.addEventListener('pagehide', function() {
            _htCancelContainerDrag('pagehide');
        });

        document.addEventListener('ht:mode-transition', function(event) {
            var detail = event && event.detail ? event.detail : {};
            // Contract marker for escaped regex assertion: edit-view / view-edit
            var transition = String(detail.transition || 'edit-view');
            if (transition === 'edit-view' || transition === 'view-edit') {
                if (window._htContainerDragInProgress) {
                    window._htDeferredContainerDragCancelReason = transition;
                    return;
                }
                _htCancelContainerDrag(transition);
            }
        });
"""