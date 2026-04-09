"""Unit tests for Cytoscape canvas initialization safeguards."""
import inspect
import re

from src.ui.components.canvas import _CANVAS_INIT_JS, render_canvas
from src.ui.pages.topology import topology_page


class TestCanvasInitializationGuards:
    def test_init_canvas_retries_are_bounded(self) -> None:
        assert "HT_CANVAS_INIT_MAX_ATTEMPTS = 50" in _CANVAS_INIT_JS
        assert "HT_CANVAS_RETRY_DELAY_MS = 100" in _CANVAS_INIT_JS
        assert _CANVAS_INIT_JS.count("currentAttempt >= HT_CANVAS_INIT_MAX_ATTEMPTS") == 2
        assert _CANVAS_INIT_JS.count("currentAttempt + 1") == 2
        assert re.search(
            r"window\.initCanvas = function\(\s*elements,\s*savedPositions,\s*deviceShapes,\s*attempt\s*\)",
            _CANVAS_INIT_JS,
        )

    def test_init_canvas_emits_console_error_when_retries_exhausted(self) -> None:
        assert (
            "console.error('Hometower canvas init failed: Cytoscape did not load within 5 seconds.');"
            in _CANVAS_INIT_JS
        )
        assert (
            "console.error('Hometower canvas init failed: #cy container not ready within 5 seconds.');"
            in _CANVAS_INIT_JS
        )

    def test_palette_drop_converts_rendered_to_model_with_zoom_and_pan(self) -> None:
        assert "var zoom = cy.zoom();" in _CANVAS_INIT_JS
        assert "var pan = cy.pan();" in _CANVAS_INIT_JS
        assert "var renderedX = e.clientX - rect.left;" in _CANVAS_INIT_JS
        assert "var renderedY = e.clientY - rect.top;" in _CANVAS_INIT_JS
        assert "var pos = { x: (renderedX - pan.x) / zoom, y: (renderedY - pan.y) / zoom };" in _CANVAS_INIT_JS
        assert "renderedToModel" not in _CANVAS_INIT_JS

    def test_canvas_container_uses_absolute_fill_layout(self) -> None:
        source = inspect.getsource(render_canvas)
        assert "position: absolute; top: 0; right: 0; bottom: 0; left: 0;" in source
        assert "width: 100%; height: 100%; background-color:" in source

    def test_topology_row_stretches_canvas_column(self) -> None:
        source = inspect.getsource(topology_page)
        assert "flex-wrap: nowrap;" in source
        assert "align-items: stretch;" in source

    def test_canvas_globals_are_defined(self) -> None:
        expected_globals = [
            "initCanvas",
            "getCanvasJson",
            "addNodeToCanvas",
            "addEdgeToCanvas",
        ]
        for function_name in expected_globals:
            assert f"window.{function_name} = function" in _CANVAS_INIT_JS
