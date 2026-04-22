"""Drag and detach helpers for container node interactions on the canvas."""

from src.ui.components.canvas_container_drag_events_part_a import (
    CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_A,
)
from src.ui.components.canvas_container_drag_events_part_b import (
    CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_B,
)
from src.ui.components.canvas_container_drag_events_part_c import (
    CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_C,
)
from src.ui.components.canvas_container_drag_events_part_d import (
    CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_D,
)

CANVAS_CONTAINER_DRAG_EVENTS_JS = (
    CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_A
    + CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_B
    + CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_C
    + CANVAS_CONTAINER_DRAG_EVENTS_JS_PART_D
)
