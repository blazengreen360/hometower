"""Canvas keyboard shortcuts — injects JS keydown handler (HT-016).

This module hides the keyboard shortcut key-code mapping and the
activeElement guard logic. If we add customisable hotkeys, only this
file changes.
"""
from nicegui import ui

_CANVAS_SHORTCUTS_JS = """
(function() {
    if (window._htShortcutsLoaded) return;
    window._htShortcutsLoaded = true;

    document.addEventListener('keydown', function(e) {
        // activeElement guard — ignore shortcuts when typing in form fields
        var tag = document.activeElement ? document.activeElement.tagName : '';
        if (
            tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
            (document.activeElement && document.activeElement.isContentEditable)
        ) return;

        if (!window._cy) return;

        var ctrl = e.ctrlKey || e.metaKey;
        var key  = e.key;

        // ── Delete / Backspace — delete selected node (write only) ──────────
        if ((key === 'Delete' || key === 'Backspace') && !ctrl) {
            if (window.HT_READONLY) return;
            var sel = window._cy.$(':selected');
            if (sel.length === 0) return;
            sel.forEach(function(ele) {
                if (ele.isNode()) {
                    var eleId = ele.id();
                    // Only allow Delete key for draft nodes — published use right-click
                    if (window._htIsDraft && !window._htIsDraft(eleId)) return;
                    document.dispatchEvent(new CustomEvent('ht:node-delete', {
                        detail: { id: eleId, data: ele.data() }
                    }));
                } else if (ele.isEdge()) {
                    document.dispatchEvent(new CustomEvent('ht:edge-delete', {
                        detail: { id: ele.id(), data: ele.data() }
                    }));
                }
            });
            return;
        }

        // ── Ctrl+D / Cmd+D — duplicate selected node (write only) ───────────
        if (ctrl && key === 'd') {
            if (window.HT_READONLY) return;
            e.preventDefault();
            var sel = window._cy.$('node:selected');
            if (sel.length === 0) return;
            var node = sel[0];
            var data = node.data ? (node.data() || {}) : {};
            if (data.ghost === true || data.editable === false || node.hasClass('ghost')) return;
            document.dispatchEvent(new CustomEvent('ht:node-duplicate', {
                detail: { id: node.id(), data: node.data() }
            }));
            return;
        }

        // ── Ctrl+A / Cmd+A — select all nodes (read-safe) ───────────────────
        if (ctrl && key === 'a') {
            e.preventDefault();
            window._cy.nodes().select();
            return;
        }

        // ── Escape — deselect all + close detail panel (read-safe) ──────────
        if (key === 'Escape') {
            window._cy.elements().unselect();
            document.dispatchEvent(new CustomEvent('ht:close-panel'));
            return;
        }

        // ── Ctrl+Z / Cmd+Z — undo (write only) ──────────────────────────────
        if (ctrl && key === 'z') {
            if (window.HT_READONLY) return;
            e.preventDefault();
            if (e.shiftKey) {
                if (window._htRequestRedo) window._htRequestRedo();
            } else {
                if (window._htRequestUndo) window._htRequestUndo();
            }
            return;
        }

        // ── Ctrl+Y — redo (write only) ──────────────────────────────────────
        if (ctrl && (key === 'y' || key === 'Y')) {
            if (window.HT_READONLY) return;
            e.preventDefault();
            if (window._htRequestRedo) window._htRequestRedo();
            return;
        }

        // ── Ctrl+S / Cmd+S — save version (write only) ──────────────────────
        if (ctrl && key === 's') {
            if (window.HT_READONLY) return;
            e.preventDefault();
            document.dispatchEvent(new CustomEvent('ht:save-version'));
            return;
        }

        // ── F — fit all (read-safe) ──────────────────────────────────────────
        if (key === 'f' || key === 'F') {
            if (window._cy) window._cy.fit();
            return;
        }
    });
})();
"""


def inject_canvas_shortcuts() -> None:
    """Inject keyboard shortcut handler into the page body."""
    ui.add_body_html(f"<script>{_CANVAS_SHORTCUTS_JS}</script>")
