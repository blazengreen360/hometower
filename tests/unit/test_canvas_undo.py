"""Unit tests for canvas undo/redo client stack contract (HT-032)."""

from src.ui.components.canvas_undo import CANVAS_UNDO_JS


class TestCanvasUndoJs:
    def test_exports_required_window_functions(self) -> None:
        required = [
            "window._htRequestCanvasAction = function(action)",
            "window._htPushCommittedUndoEntry = function(entry)",
            "window._htRequestUndo = function()",
            "window._htRequestRedo = function()",
            "window._htResolveUndoApiSuccess = function(direction, entryId, result)",
            "window._htResolveUndoApiFailure = function(direction, entryId, message)",
            "window._htResetUndoState = function()",
        ]
        for marker in required:
            assert marker in CANVAS_UNDO_JS

    def test_stack_limit_is_capped_to_fifty_entries(self) -> None:
        assert "HT_UNDO_MAX_ENTRIES = 50" in CANVAS_UNDO_JS
        assert "window._htUndoState.undoStack.length > HT_UNDO_MAX_ENTRIES" in CANVAS_UNDO_JS
        assert "window._htUndoState.undoStack.shift();" in CANVAS_UNDO_JS

    def test_new_forward_actions_clear_redo_stack(self) -> None:
        assert "window._htUndoState.redoStack = [];" in CANVAS_UNDO_JS

    def test_busy_lock_and_failure_retain_source_entry(self) -> None:
        assert "window._htUndoState.busy" in CANVAS_UNDO_JS
        assert "if (window._htUndoState.busy) return;" in CANVAS_UNDO_JS
        assert "Undo failed:" in CANVAS_UNDO_JS
        assert "Redo failed:" in CANVAS_UNDO_JS

    def test_page_session_reset_clears_both_stacks(self) -> None:
        assert "window._htUndoState.undoStack = [];" in CANVAS_UNDO_JS
        assert "window._htUndoState.redoStack = [];" in CANVAS_UNDO_JS
