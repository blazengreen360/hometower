"""Unit tests for canvas_shortcuts module (HT-016).

inject_canvas_shortcuts() calls NiceGUI ui.add_body_html() which requires
a running NiceGUI context. These tests focus on the generated JS string so
regressions in the shortcut branches and focus guards are caught without a
browser harness.
"""
from unittest.mock import patch

from src.ui.components.canvas_shortcuts import _CANVAS_SHORTCUTS_JS, inject_canvas_shortcuts


def _shortcut_section(start: str, end: str | None = None) -> str:
    start_index = _CANVAS_SHORTCUTS_JS.index(start)
    if end is None:
        return _CANVAS_SHORTCUTS_JS[start_index:]
    end_index = _CANVAS_SHORTCUTS_JS.index(end, start_index)
    return _CANVAS_SHORTCUTS_JS[start_index:end_index]


class TestCanvasShortcutsJs:
    def test_js_string_is_non_empty(self) -> None:
        assert len(_CANVAS_SHORTCUTS_JS) > 100

    def test_js_registers_keydown_listener(self) -> None:
        assert "document.addEventListener('keydown'" in _CANVAS_SHORTCUTS_JS

    def test_js_active_element_guard_ignores_form_fields_and_contenteditable(self) -> None:
        assert "document.activeElement ? document.activeElement.tagName : ''" in _CANVAS_SHORTCUTS_JS
        assert "INPUT" in _CANVAS_SHORTCUTS_JS
        assert "TEXTAREA" in _CANVAS_SHORTCUTS_JS
        assert "SELECT" in _CANVAS_SHORTCUTS_JS
        assert "isContentEditable" in _CANVAS_SHORTCUTS_JS

    def test_delete_shortcut_dispatches_node_and_edge_events(self) -> None:
        delete_section = _shortcut_section(
            "if ((key === 'Delete' || key === 'Backspace') && !ctrl)",
            "if (ctrl && key === 'd')",
        )
        assert "if (window.HT_READONLY) return;" in delete_section
        assert "if (window._htIsDraft && !window._htIsDraft(eleId)) return;" in delete_section
        assert "document.dispatchEvent(new CustomEvent('ht:node-delete'" in delete_section
        assert "document.dispatchEvent(new CustomEvent('ht:edge-delete'" in delete_section

    def test_ctrl_d_shortcut_requires_selected_node_and_readonly_guard(self) -> None:
        ctrl_d_section = _shortcut_section("if (ctrl && key === 'd')", "if (ctrl && key === 'a')")
        assert "if (window.HT_READONLY) return;" in ctrl_d_section
        assert "e.preventDefault();" in ctrl_d_section
        assert "var sel = window._cy.$('node:selected');" in ctrl_d_section
        assert "document.dispatchEvent(new CustomEvent('ht:node-duplicate'" in ctrl_d_section

    def test_ctrl_a_shortcut_remains_read_safe(self) -> None:
        ctrl_a_section = _shortcut_section("if (ctrl && key === 'a')", "if (key === 'Escape')")
        assert "e.preventDefault();" in ctrl_a_section
        assert "window._cy.nodes().select();" in ctrl_a_section
        assert "HT_READONLY" not in ctrl_a_section

    def test_escape_shortcut_clears_selection_and_closes_panel(self) -> None:
        escape_section = _shortcut_section("if (key === 'Escape')", "if (ctrl && key === 'z')")
        assert "window._cy.elements().unselect();" in escape_section
        assert "document.dispatchEvent(new CustomEvent('ht:close-panel'));" in escape_section
        assert "HT_READONLY" not in escape_section

    def test_ctrl_z_shortcut_routes_to_stack_undo_request(self) -> None:
        ctrl_z_section = _shortcut_section("if (ctrl && key === 'z')", "if (ctrl && key === 's')")
        assert "if (window.HT_READONLY) return;" in ctrl_z_section
        assert "e.preventDefault();" in ctrl_z_section
        assert "if (e.shiftKey) {" in ctrl_z_section
        assert "window._htRequestUndo" in ctrl_z_section
        assert "window._htRequestRedo" in ctrl_z_section
        assert "_htUndoStack" not in ctrl_z_section

    def test_ctrl_y_shortcut_routes_to_stack_redo_request(self) -> None:
        ctrl_y_section = _shortcut_section("if (ctrl && (key === 'y' || key === 'Y'))", "})();")
        assert "if (window.HT_READONLY) return;" in ctrl_y_section
        assert "e.preventDefault();" in ctrl_y_section
        assert "window._htRequestRedo" in ctrl_y_section

    def test_ctrl_s_shortcut_prevents_default_and_dispatches_save_event(self) -> None:
        ctrl_s_section = _shortcut_section("if (ctrl && key === 's')", "if (key === 'f' || key === 'F')")
        assert "if (window.HT_READONLY) return;" in ctrl_s_section
        assert "e.preventDefault();" in ctrl_s_section
        assert "document.dispatchEvent(new CustomEvent('ht:save-version'));" in ctrl_s_section

    def test_fit_shortcut_remains_read_safe(self) -> None:
        fit_section = _shortcut_section("if (key === 'f' || key === 'F')")
        assert "window._cy.fit();" in fit_section
        assert "HT_READONLY" not in fit_section


class TestInjectCanvasShortcuts:
    def test_calls_add_body_html_once(self) -> None:
        with patch("src.ui.components.canvas_shortcuts.ui") as mock_ui:
            inject_canvas_shortcuts()
            mock_ui.add_body_html.assert_called_once()

    def test_injects_script_tag(self) -> None:
        with patch("src.ui.components.canvas_shortcuts.ui") as mock_ui:
            inject_canvas_shortcuts()
            call_args = mock_ui.add_body_html.call_args[0][0]
            assert "<script>" in call_args
