"""Unit tests for canvas_mode module (HT-048).

Tests the JS string constants that transition Cytoscape between
view-only and edit interaction states.
"""
from src.ui.components.canvas_mode import EDIT_MODE_JS, VIEW_MODE_JS


class TestViewModeJs:
    def test_view_mode_js_is_non_empty(self) -> None:
        assert len(VIEW_MODE_JS) > 50

    def test_view_mode_defines_htSetViewMode(self) -> None:
        assert "htSetViewMode" in VIEW_MODE_JS

    def test_view_mode_sets_readonly_true(self) -> None:
        assert "HT_READONLY = true" in VIEW_MODE_JS

    def test_view_mode_autoungrabify_true(self) -> None:
        assert "autoungrabify(true)" in VIEW_MODE_JS

    def test_view_mode_autounselectify_not_set(self) -> None:
        # autounselectify(true) must NOT be present: it globally locks
        # selectable:false, preventing Ctrl+A / Escape from working (BUG-001).
        assert "autounselectify(true)" not in VIEW_MODE_JS

    def test_view_mode_box_selection_disabled(self) -> None:
        assert "boxSelectionEnabled(false)" in VIEW_MODE_JS

    def test_view_mode_guards_missing_cy(self) -> None:
        assert "if (!window._cy) return" in VIEW_MODE_JS


class TestEditModeJs:
    def test_edit_mode_js_is_non_empty(self) -> None:
        assert len(EDIT_MODE_JS) > 50

    def test_edit_mode_defines_htSetEditMode(self) -> None:
        assert "htSetEditMode" in EDIT_MODE_JS

    def test_edit_mode_sets_readonly_false(self) -> None:
        assert "HT_READONLY = false" in EDIT_MODE_JS

    def test_edit_mode_autoungrabify_false(self) -> None:
        assert "autoungrabify(false)" in EDIT_MODE_JS

    def test_edit_mode_autounselectify_false(self) -> None:
        assert "autounselectify(false)" in EDIT_MODE_JS

    def test_edit_mode_box_selection_enabled(self) -> None:
        assert "boxSelectionEnabled(true)" in EDIT_MODE_JS

    def test_edit_mode_guards_missing_cy(self) -> None:
        assert "if (!window._cy) return" in EDIT_MODE_JS
