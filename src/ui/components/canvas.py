"""Cytoscape.js canvas component — embeds and manages the topology canvas.

Loads Cytoscape.js from CDN, initializes the canvas with device elements,
and wires event handlers for drag, tap, and context-menu interactions.
"""
import json

from nicegui import ui

from src.ui.components.canvas_events import inject_canvas_events
from src.ui.design.tokens import COLOR_PRIMARY, COLOR_SURFACE, COLOR_SURFACE_ALT, COLOR_TEXT, DEVICE_SHAPES

_CYTOSCAPE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"

_CANVAS_INIT_JS = """
(function() {
    if (typeof initCanvas !== 'undefined') return;

    window._htSelectedCallback = null;

    window.initCanvas = function(elements, savedPositions, deviceShapes) {
        var cy = cytoscape({
            container: document.getElementById('cy'),
            elements: elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'label': 'data(label)',
                        'shape': 'data(shape)',
                        'background-color': '#4f46e5',
                        'color': '#cdd6f4',
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'font-size': '12px',
                        'width': 48,
                        'height': 48,
                        'border-width': 2,
                        'border-color': '#a6adc8',
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-color': '#4f46e5',
                        'border-width': 4,
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'curve-style': 'bezier',
                        'target-arrow-shape': 'triangle',
                        'line-color': '#a6adc8',
                        'target-arrow-color': '#a6adc8',
                        'width': 2,
                    }
                }
            ],
            layout: savedPositions && savedPositions.pan
                ? { name: 'preset' }
                : { name: 'cose', animate: false },
        });

        if (savedPositions && savedPositions.pan) {
            cy.zoom(savedPositions.zoom || 1);
            cy.pan(savedPositions.pan || {x: 0, y: 0});
        }

        window._cy = cy;

        // Wire event handlers for palette-drop and node actions
        window._htInitEventHandlers(deviceShapes || {});

        // Node tap — dispatch custom event for detail panel
        cy.on('tap', 'node', function(evt) {
            var node = evt.target;
            var detail = node.data();
            document.dispatchEvent(new CustomEvent('ht:node-selected', { detail: detail }));
        });

        // Drag end — update position in memory only (batch-saved on Save Layout)
        cy.on('dragfree', 'node', function(evt) {
            var node = evt.target;
            window._htNodePositions = window._htNodePositions || {};
            window._htNodePositions[node.id()] = node.position();
        });

        // Right-click context menu
        cy.on('cxttap', 'node', function(evt) {
            var node = evt.target;
            document.dispatchEvent(new CustomEvent('ht:node-context', {
                detail: { id: node.id(), data: node.data() }
            }));
        });

        // Drop handler for device palette
        var container = document.getElementById('cy');
        container.addEventListener('dragover', function(e) { e.preventDefault(); });
        container.addEventListener('drop', function(e) {
            e.preventDefault();
            var deviceType = e.dataTransfer.getData('deviceType');
            if (!deviceType) return;
            var rect = container.getBoundingClientRect();
            var pos = cy.renderedToModel({ x: e.clientX - rect.left, y: e.clientY - rect.top });
            document.dispatchEvent(new CustomEvent('ht:palette-drop', {
                detail: { deviceType: deviceType, x: pos.x, y: pos.y }
            }));
        });
    };

    window.getCanvasJson = function() {
        if (!window._cy) return null;
        var json = window._cy.json();
        return { elements: json.elements, zoom: window._cy.zoom(), pan: window._cy.pan() };
    };

    window.addNodeToCanvas = function(nodeData) {
        if (!window._cy) return;
        window._cy.add({ data: nodeData, position: { x: nodeData.x || 200, y: nodeData.y || 200 } });
    };

    window.addEdgeToCanvas = function(edgeData) {
        if (!window._cy) return;
        if (window._cy.getElementById(edgeData.id).length > 0) return;
        window._cy.add({ group: 'edges', data: edgeData });
    };
})();
"""


def render_canvas(elements: list[dict[str, object]], saved_layout: dict[str, object] | None) -> None:
    """Render the Cytoscape.js canvas inside NiceGUI.

    :param elements: Cytoscape element dicts (nodes/edges).
    :param saved_layout: Persisted layout JSON with zoom/pan, or None for auto-layout.
    """
    # Inject CDN script
    ui.add_head_html(
        f'<script src="{_CYTOSCAPE_CDN}" crossorigin="anonymous"></script>'
    )

    # Event handlers (extracted to canvas_events.py)
    inject_canvas_events()

    # Canvas init logic (only once per page load)
    ui.add_body_html(f"<script>{_CANVAS_INIT_JS}</script>")

    # Canvas container
    with ui.element("div").props('id="cy"').style(
        f"width: 100%; height: 100%; background-color: {COLOR_SURFACE};"
    ):
        pass

    # Initialize canvas with data
    device_shapes_dict = {dt.value: shape for dt, shape in DEVICE_SHAPES.items()}
    elements_js = json.dumps(elements)
    saved_js = json.dumps(saved_layout) if saved_layout else "null"
    shapes_js = json.dumps(device_shapes_dict)
    ui.run_javascript(f"initCanvas({elements_js}, {saved_js}, {shapes_js})")
