"""Unit tests for canvas undo/redo client stack contract (HT-032)."""

from src.ui.components.canvas_undo import CANVAS_UNDO_JS
from src.ui.components.canvas_undo_js_actions import CANVAS_UNDO_JS_ACTIONS


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
        assert "if (window._htUndoState.busy && !_htEntryCanRunWhileBusy(entry)) return;" in CANVAS_UNDO_JS
        assert "Undo failed:" in CANVAS_UNDO_JS
        assert "Redo failed:" in CANVAS_UNDO_JS

    def test_local_top_entries_remain_enabled_while_busy(self) -> None:
        assert "function _htEntryCanRunWhileBusy(entry) {" in CANVAS_UNDO_JS
        assert "function _setToolbarButtonState(button, disabled) {" in CANVAS_UNDO_JS
        assert "readonly || (state.busy && !_htEntryCanRunWhileBusy(undoTop)) || state.undoStack.length === 0" in CANVAS_UNDO_JS
        assert "readonly || (state.busy && !_htEntryCanRunWhileBusy(redoTop)) || state.redoStack.length === 0" in CANVAS_UNDO_JS
        assert "button.setAttribute('aria-disabled', isDisabled ? 'true' : 'false');" in CANVAS_UNDO_JS
        assert "button.classList.toggle('disabled', isDisabled);" in CANVAS_UNDO_JS

    def test_local_snapshot_replay_resyncs_stencil_panel_state(self) -> None:
        refresh_helper = CANVAS_UNDO_JS_ACTIONS.split(
            "function _dispatchStencilRefreshAfterSettle() {",
            1,
        )[1].split("async function _waitForAutosaveSettled() {", 1)[0]
        remove_branch = CANVAS_UNDO_JS_ACTIONS.split("if (op === 'remove_snapshot') {", 1)[1].split(
            "if (op === 'restore_snapshot') {",
            1,
        )[0]
        restore_branch = CANVAS_UNDO_JS_ACTIONS.split("if (op === 'restore_snapshot') {", 1)[1].split(
            "if (op === 'add_edge_local') {",
            1,
        )[0]

        assert "ht:stencil-refresh" in remove_branch
        assert "ht:stencil-refresh" in refresh_helper
        assert "_dispatchStencilRefreshAfterSettle();" in restore_branch

    def test_page_session_reset_clears_both_stacks(self) -> None:
        assert "window._htUndoState.undoStack = [];" in CANVAS_UNDO_JS
        assert "window._htUndoState.redoStack = [];" in CANVAS_UNDO_JS
