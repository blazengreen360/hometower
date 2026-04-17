"""Unit tests for HT-050 canvas resize bridge script."""

from src.ui.components.canvas_js_resize import CANVAS_RESIZE_JS


class TestCanvasResizeBridgeJs:
    def test_resize_bridge_is_singleton_guarded(self) -> None:
        assert "window._htCanvasResizeBridgeLoaded" in CANVAS_RESIZE_JS
        assert "if (window._htCanvasResizeBridgeLoaded) return;" in CANVAS_RESIZE_JS

    def test_resize_bridge_exports_window_scoped_helpers(self) -> None:
        assert "window._htResizeSyncFromSelection = function()" in CANVAS_RESIZE_JS
        assert "window._htResizeSetEnabled = function(enabled)" in CANVAS_RESIZE_JS
        assert "window._htBindCanvasResize = function(cy, container)" in CANVAS_RESIZE_JS

    def test_resize_bridge_defines_eight_resize_handles(self) -> None:
        for direction in ["nw", "n", "ne", "e", "se", "s", "sw", "w"]:
            assert f"'{direction}'" in CANVAS_RESIZE_JS
        assert "data-ht-resize-handle" in CANVAS_RESIZE_JS

    def test_resize_bridge_corner_path_locks_aspect_ratio_from_pointerdown(self) -> None:
        assert "aspectRatio = startWidth / Math.max(startHeight, 1);" in CANVAS_RESIZE_JS
        assert "if (HT_CORNER_HANDLES[direction]) {" in CANVAS_RESIZE_JS
        assert "var widthDeltaFromX = signX * dx;" in CANVAS_RESIZE_JS
        assert "var widthDeltaFromY = signY * dy * pointer.aspectRatio;" in CANVAS_RESIZE_JS
        assert "var dominantDelta = Math.abs(widthDeltaFromX) >= Math.abs(widthDeltaFromY)" in CANVAS_RESIZE_JS

    def test_resize_bridge_edge_handles_resize_single_dimension(self) -> None:
        assert "if (affectX) width = pointer.startSize.width + (signX * dx);" in CANVAS_RESIZE_JS
        assert "if (affectY) height = pointer.startSize.height + (signY * dy);" in CANVAS_RESIZE_JS

    def test_resize_bridge_applies_node_and_compound_minimums(self) -> None:
        assert "var HT_NODE_MIN_SIZE = 40;" in CANVAS_RESIZE_JS
        assert "var children = node.children();" in CANVAS_RESIZE_JS
        assert "var childBox = children.boundingBox({ includeLabels: false, includeOverlays: false });" in CANVAS_RESIZE_JS
        assert "var padding = _htResizeParsePx(node.style('padding'), 0);" in CANVAS_RESIZE_JS
        assert "minWidth = Math.max(minWidth, childWidth + (padding * 2));" in CANVAS_RESIZE_JS
        assert "minHeight = Math.max(minHeight, childHeight + (padding * 2));" in CANVAS_RESIZE_JS

    def test_resize_bridge_persists_inline_dimensions_and_autosaves_once_on_commit(self) -> None:
        assert "node.style('width', calc.width);" in CANVAS_RESIZE_JS
        assert "node.style('height', calc.height);" in CANVAS_RESIZE_JS
        assert "node.position(calc.position);" in CANVAS_RESIZE_JS
        pointer_move_section = CANVAS_RESIZE_JS.split("function _htResizePointerMove(event) {", 1)[1].split(
            "function _htResizePointerUp(event) {",
            1,
        )[0]
        assert "scheduleAutosave" not in pointer_move_section
        stop_section = CANVAS_RESIZE_JS.split("function _htResizeStop(commit) {", 1)[1].split(
            "function _htResizePointerMove(event) {",
            1,
        )[0]
        assert "if (window.scheduleAutosave) window.scheduleAutosave(800);" in stop_section

    def test_resize_bridge_is_inactive_in_readonly_or_history_preview(self) -> None:
        assert "&& !window.HT_READONLY" in CANVAS_RESIZE_JS
        assert "&& window._htHistoryPreviewActive !== true" in CANVAS_RESIZE_JS

    def test_resize_bridge_requires_exactly_one_selected_eligible_node(self) -> None:
        assert "var selected = state.cy.$('node:selected');" in CANVAS_RESIZE_JS
        assert "if (selected.length !== 1) return null;" in CANVAS_RESIZE_JS
        assert "return !_htResizeIsLocked(node);" in CANVAS_RESIZE_JS
