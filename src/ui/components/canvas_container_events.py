"""Container-specific Cytoscape.js event handlers (HT-021)."""

from src.ui.components.canvas_container_actions import CANVAS_CONTAINER_ACTIONS_JS
from src.ui.components.canvas_container_drag_events import CANVAS_CONTAINER_DRAG_EVENTS_JS
from src.ui.components.canvas_container_unconvert import CANVAS_CONTAINER_UNCONVERT_JS


CANVAS_CONTAINER_EVENTS_JS = CANVAS_CONTAINER_ACTIONS_JS + """
        document.addEventListener('ht:node-convert-container', function(evt) {
            var d = evt.detail;
            if (!window._cy) return;
            var node = window._cy.getElementById(d.id);
            if (node.length) {
                node.addClass('container');
                if (window._htFlushAutosave) {
                    window._htFlushAutosave();
                } else if (window.scheduleAutosave) window.scheduleAutosave(800);
                _notify('Device converted to container.', 'positive');
            }
        });

        function _htStripClasses(classes) {
            if (typeof classes !== 'string') return classes;
            return classes.split(/\\s+/).filter(function(value) {
                return value && value !== 'container' && value !== 'collapsed';
            }).join(' ');
        }

        document.addEventListener('ht:node-collapse-toggle', function(evt) {
            var d = evt.detail;
            if (!window._cy) return;
            var node = window._cy.getElementById(d.id);
            if (!node.length) { return; }

            var isCollapsed = node.data('_collapsed');
            if (isCollapsed) {
                node.children().forEach(function(child) {
                    child.style('display', 'element');
                    child.connectedEdges().style('display', 'element');
                });
                node.data('_collapsed', false);
                node.removeClass('collapsed');
            } else {
                node.children().forEach(function(child) {
                    child.style('display', 'none');
                    child.connectedEdges().forEach(function(edge) {
                        var srcParent = edge.source().data('parent');
                        var tgtParent = edge.target().data('parent');
                        // Only hide internal edges; edges crossing the boundary stay visible
                        if (srcParent === d.id && tgtParent === d.id) {
                            edge.style('display', 'none');
                        }
                    });
                });
                node.data('_collapsed', true);
                node.addClass('collapsed');
            }
            // Persist collapse state via debounced autosave (both collapse and expand)
            if (window.scheduleAutosave) window.scheduleAutosave(800);
        });
""" + CANVAS_CONTAINER_DRAG_EVENTS_JS + CANVAS_CONTAINER_UNCONVERT_JS
