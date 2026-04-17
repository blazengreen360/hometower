"""Canvas mode transitions — view-only / edit interaction states.

This module hides the Cytoscape.js API calls that switch between
view-only and edit interaction modes. If cytoscape's options API
changes, only this file needs updating.
"""

VIEW_MODE_JS: str = """
(function() {
    window.htSetViewMode = function() {
        if (!window._cy) return;
        window.HT_READONLY = true;
        window._cy.autoungrabify(true);
        // autounselectify deliberately omitted: it globally locks selectable:false
        // on all nodes, causing Ctrl+A and Escape shortcuts to silently no-op.
        window._cy.boxSelectionEnabled(false);
        if (window._htResizeSetEnabled) window._htResizeSetEnabled(false);
    };
})();
"""

EDIT_MODE_JS: str = """
(function() {
    window.htSetEditMode = function() {
        if (!window._cy) return;
        window.HT_READONLY = false;
        window._cy.autoungrabify(false);
        window._cy.autounselectify(false);
        window._cy.boxSelectionEnabled(true);
        if (window._htApplyNodeEditability) window._htApplyNodeEditability(window._cy);
        if (window._htResizeSetEnabled) window._htResizeSetEnabled(true);
        if (window._htResizeSyncFromSelection) window._htResizeSyncFromSelection();
    };
})();
"""
