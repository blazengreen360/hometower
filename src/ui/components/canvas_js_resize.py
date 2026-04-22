"""Node/container resize overlay bridge for Cytoscape.js canvas."""

from src.ui.components.canvas_js_resize_part_a import CANVAS_RESIZE_JS_PART_A
from src.ui.components.canvas_js_resize_part_d import CANVAS_RESIZE_JS_PART_D
from src.ui.components.canvas_js_resize_part_b import CANVAS_RESIZE_JS_PART_B
from src.ui.components.canvas_js_resize_part_c import CANVAS_RESIZE_JS_PART_C

CANVAS_RESIZE_JS = (
	CANVAS_RESIZE_JS_PART_A
	+ CANVAS_RESIZE_JS_PART_D
	+ CANVAS_RESIZE_JS_PART_B
	+ CANVAS_RESIZE_JS_PART_C
)
