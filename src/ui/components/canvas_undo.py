"""Canvas undo/redo stack manager injected as client-side JavaScript (HT-032)."""

from nicegui import ui
from src.ui.components.canvas_undo_js_actions import CANVAS_UNDO_JS_ACTIONS
from src.ui.components.canvas_undo_js_core import CANVAS_UNDO_JS_CORE
from src.ui.components.canvas_undo_js_graph import CANVAS_UNDO_JS_GRAPH
from src.ui.components.canvas_undo_js_local import CANVAS_UNDO_JS_LOCAL
from src.ui.components.canvas_undo_js_resolution import CANVAS_UNDO_JS_RESOLUTION


CANVAS_UNDO_JS = (
    CANVAS_UNDO_JS_CORE
    + CANVAS_UNDO_JS_GRAPH
    + CANVAS_UNDO_JS_LOCAL
    + CANVAS_UNDO_JS_ACTIONS
    + CANVAS_UNDO_JS_RESOLUTION
)


def inject_canvas_undo() -> None:
    """Inject the canvas undo stack JavaScript bundle."""
    ui.add_body_html(f"<script>{CANVAS_UNDO_JS}</script>")
