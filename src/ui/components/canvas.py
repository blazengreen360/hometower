"""Cytoscape.js canvas component — embeds and manages the topology canvas.

Loads Cytoscape.js from CDN, initializes the canvas with device elements,
and wires event handlers for drag, tap, and context-menu interactions.
"""
import json

from nicegui import ui

from src.ui.components.canvas_events import inject_canvas_events
from src.ui.components.canvas_undo import inject_canvas_undo
from src.ui.components.canvas_js import CANVAS_INIT_JS_TEMPLATE
from src.ui.components.canvas_styles import build_theme_style_json
from src.ui.components.canvas_tooltip import inject_canvas_tooltip
from src.ui.design.tokens import DEVICE_SHAPES

_CYTOSCAPE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"
_CYTOSCAPE_SRI = "sha384-J7Q85oZE4GJ/e7+n2aOQsLXfDwwfnA8S2nZAL5BpFsfpCF84zQD7LroZ/dMnLgex"


def render_canvas(elements: list[dict[str, object]], saved_layout: dict[str, object] | None) -> None:
    """Render the Cytoscape.js canvas inside NiceGUI.

    :param elements: Cytoscape element dicts (nodes/edges).
    :param saved_layout: Persisted layout JSON with zoom/pan, or None for auto-layout.
    """
    from nicegui import app as nicegui_app

    theme = nicegui_app.storage.user.get("theme", "dark")

    # Inject CDN script
    ui.add_head_html(
        f'<script src="{_CYTOSCAPE_CDN}" integrity="{_CYTOSCAPE_SRI}" crossorigin="anonymous"></script>'
    )

    # Event handlers (extracted to canvas_events.py)
    inject_canvas_events()

    # Undo/redo stack helpers and API bridge wiring
    inject_canvas_undo()

    # Service tooltip handlers (extracted to canvas_tooltip.py)
    inject_canvas_tooltip()

    # Canvas init logic with theme-specific styles (only once per page load)
    canvas_js = CANVAS_INIT_JS_TEMPLATE.replace(
        "__HT_CANVAS_STYLE__", build_theme_style_json(theme)
    )
    ui.add_body_html(f"<script>{canvas_js}</script>")

    # Canvas container — background uses CSS var so it follows theme without JS
    with ui.element("div").style(
        "position: absolute; top: 0; right: 0; bottom: 0; left: 0;"
    ):
        with ui.element("div").props('id="cy"').style(
            "width: 100%; height: 100%; background-color: var(--ht-bg-base);"
        ):
            pass
        with ui.element("div").props('id="ht-network-badges"').style(
            "position: absolute; inset: 0; pointer-events: none; z-index: 6;"
        ):
            pass
        with ui.element("div").props('id="ht-node-resize-overlay"').style(
            "position: absolute; inset: 0; pointer-events: none; z-index: 8;"
        ):
            pass

    # Initialize canvas with data
    device_shapes_dict = {dt.value: shape for dt, shape in DEVICE_SHAPES.items()}
    elements_js = json.dumps(elements)
    saved_js = json.dumps(saved_layout) if saved_layout else "null"
    shapes_js = json.dumps(device_shapes_dict)
    ui.run_javascript(f"initCanvas({elements_js}, {saved_js}, {shapes_js})")
