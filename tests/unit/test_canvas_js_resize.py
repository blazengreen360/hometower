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
        assert "var HT_COMPOUND_MIN_PADDING = 24;" in CANVAS_RESIZE_JS
        assert "var children = node.children();" in CANVAS_RESIZE_JS
        assert "var childBox = children.boundingBox({ includeLabels: false, includeOverlays: false });" in CANVAS_RESIZE_JS
        assert "function _htResizeCompoundPadding(node) {" in CANVAS_RESIZE_JS
        assert "function _htResizeCompoundMinPadding(node) {" in CANVAS_RESIZE_JS
        assert "Math.min(padding.left, HT_COMPOUND_MIN_PADDING)" in CANVAS_RESIZE_JS
        assert "padding.left + padding.right" in CANVAS_RESIZE_JS
        assert "padding.top + padding.bottom" in CANVAS_RESIZE_JS

    def test_resize_bridge_has_compound_specific_apply_path(self) -> None:
        assert "function _htResizeCaptureCompoundState(node, startSize, startPosition) {" in CANVAS_RESIZE_JS
        assert "function _htResizeCompoundAnchoredBounds(calc, compoundState) {" in CANVAS_RESIZE_JS
        assert "function _htResizeApplyCompound(node, calc, compoundState) {" in CANVAS_RESIZE_JS
        assert "function _htResizeSyncCompoundChain(node) {" in CANVAS_RESIZE_JS
        assert "offsetLeft: childX - startContentBounds.x1" in CANVAS_RESIZE_JS
        assert "offsetRight: startContentBounds.x2 - childX" in CANVAS_RESIZE_JS
        assert "offsetTop: childY - startContentBounds.y1" in CANVAS_RESIZE_JS
        assert "offsetBottom: startContentBounds.y2 - childY" in CANVAS_RESIZE_JS
        assert "var targetBounds = _htResizeCompoundAnchoredBounds(calc, compoundState);" in CANVAS_RESIZE_JS
        assert "targetContentBounds.x2 - childStart.offsetRight" in CANVAS_RESIZE_JS
        assert "targetContentBounds.x1 + childStart.offsetLeft" in CANVAS_RESIZE_JS
        assert "targetContentBounds.y2 - childStart.offsetBottom" in CANVAS_RESIZE_JS
        assert "targetContentBounds.y1 + childStart.offsetTop" in CANVAS_RESIZE_JS
        assert "calc.position.x + (relX * scaleX)" not in CANVAS_RESIZE_JS
        assert "calc.position.y + (relY * scaleY)" not in CANVAS_RESIZE_JS
        assert "child.position({" in CANVAS_RESIZE_JS
        assert "node.style('min-width', calc.width + 'px');" in CANVAS_RESIZE_JS
        assert "node.style('min-height', calc.height + 'px');" in CANVAS_RESIZE_JS
        assert "node.style('min-width-bias-left', leftBias);" in CANVAS_RESIZE_JS
        assert "node.style('min-width-bias-right', rightBias);" in CANVAS_RESIZE_JS
        assert "node.style('min-height-bias-top', topBias);" in CANVAS_RESIZE_JS
        assert "node.style('min-height-bias-bottom', bottomBias);" in CANVAS_RESIZE_JS
        assert "_htResizeSyncCompoundChain(node);" in CANVAS_RESIZE_JS
        assert "if (pointer && pointer.compound) {" in CANVAS_RESIZE_JS

    def test_resize_bridge_compound_syncs_style_dimensions_to_rendered_box(self) -> None:
        assert "var finalBox = node.boundingBox({ includeLabels: false, includeOverlays: false });" in CANVAS_RESIZE_JS
        assert "var finalWidth = _htResizeParsePx(finalBox ? (finalBox.w || (finalBox.x2 - finalBox.x1)) : calc.width, calc.width);" in CANVAS_RESIZE_JS
        assert "var finalHeight = _htResizeParsePx(finalBox ? (finalBox.h || (finalBox.y2 - finalBox.y1)) : calc.height, calc.height);" in CANVAS_RESIZE_JS
        assert "node.style('width', finalWidth);" in CANVAS_RESIZE_JS
        assert "node.style('height', finalHeight);" in CANVAS_RESIZE_JS

    def test_resize_bridge_hydrates_compounds_from_persisted_styles_on_bind(self) -> None:
        assert "function _htResizeHydrateCompoundsFromPersistedStyles() {" in CANVAS_RESIZE_JS
        assert "var padding = _htResizeCompoundPadding(node);" in CANVAS_RESIZE_JS
        assert "var savedContentWidth = Math.max(1, savedWidth - padding.left - padding.right);" in CANVAS_RESIZE_JS
        assert "var savedContentHeight = Math.max(1, savedHeight - padding.top - padding.bottom);" in CANVAS_RESIZE_JS
        assert "node.style('min-width', savedContentWidth + 'px');" in CANVAS_RESIZE_JS
        assert "node.style('min-height', savedContentHeight + 'px');" in CANVAS_RESIZE_JS
        assert "node.style('min-width-bias-left', '50%');" not in CANVAS_RESIZE_JS
        assert "node.style('min-width-bias-right', '50%');" not in CANVAS_RESIZE_JS
        assert "node.style('min-height-bias-top', '50%');" not in CANVAS_RESIZE_JS
        assert "node.style('min-height-bias-bottom', '50%');" not in CANVAS_RESIZE_JS
        assert "_htResizeHydrateCompoundsFromPersistedStyles();" in CANVAS_RESIZE_JS

    def test_resize_bridge_uses_bounding_box_dimensions_as_resize_baseline(self) -> None:
        assert "var startBox = node.boundingBox({ includeLabels: false, includeOverlays: false });" in CANVAS_RESIZE_JS
        assert "var startWidth = _htResizeParsePx(startBox ? (startBox.w || (startBox.x2 - startBox.x1)) : 0, _htResizeParsePx(node.width(), HT_NODE_MIN_SIZE));" in CANVAS_RESIZE_JS
        assert "var startHeight = _htResizeParsePx(startBox ? (startBox.h || (startBox.y2 - startBox.y1)) : 0, _htResizeParsePx(node.height(), HT_NODE_MIN_SIZE));" in CANVAS_RESIZE_JS
        assert "var startWidth = _htResizeParsePx(node.style('width'), _htResizeParsePx(node.width(), HT_NODE_MIN_SIZE));" not in CANVAS_RESIZE_JS
        assert "var startHeight = _htResizeParsePx(node.style('height'), _htResizeParsePx(node.height(), HT_NODE_MIN_SIZE));" not in CANVAS_RESIZE_JS

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
