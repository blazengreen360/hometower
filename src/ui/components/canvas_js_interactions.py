"""Cytoscape.js interaction bindings used by the canvas init script."""

from src.ui.components.canvas_js_interactions_part_a import (
    CANVAS_INTERACTIONS_JS_PART_A,
)
from src.ui.components.canvas_js_interactions_part_b import (
    CANVAS_INTERACTIONS_JS_PART_B,
)


CANVAS_INTERACTIONS_JS = (
    CANVAS_INTERACTIONS_JS_PART_A
    + CANVAS_INTERACTIONS_JS_PART_B
)