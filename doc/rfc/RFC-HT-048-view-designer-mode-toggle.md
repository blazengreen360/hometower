# RFC: View Designer — View Mode / Edit Mode with RBAC Gate

**Story:** HT-048
**Status:** Draft — awaiting Feature-Engineer implementation
**Date:** 2026-04-12
**Author:** Architect

---

## 1. Overview

The View Designer (topology canvas) currently opens in **edit mode** for Contributors and Admins — palette visible, drag enabled, context menu active. This is unsafe: accidental drags reposition nodes and trigger autosave. HT-048 inverts the default so **all users** open in **view-only mode**. Contributors/Admins see an "Edit" toggle to enter edit mode on demand. Readers never see the toggle and remain permanently view-only.

This is a pure UI-layer change. No new API endpoints, no database models, no Alembic migrations.

---

## 2. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/ui/components/canvas_mode.py` *(new)* | The JS function calls that transition Cytoscape between view/edit interaction states — if Cytoscape's API changes or we swap to D3, only this file changes |
| `src/ui/components/topology_edit_toggle.py` *(new)* | The "Edit" / "Stop Editing" button widget, its placement, and the draft-device warning prompt — if we change the button to a toggle switch or move it, only this file changes |
| `src/ui/pages/topology.py` | The page-level mode state and how mode affects which components render — the orchestration point |

---

## 3. Mode State Model

Mode is page-local runtime state, never persisted:

```
_edit_mode: bool = False   # topology.py page-level state
```

The JS global `window.HT_READONLY` tracks the mode on the client side:
- **View mode:** `HT_READONLY = true` for ALL users (including Admin/Contributor)
- **Edit mode:** `HT_READONLY = false` (only reachable by Contributor/Admin via the toggle)

On every page load, `HT_READONLY` starts as `true`. Navigating away or reloading resets to view-only.

---

## 4. Cytoscape.js Interaction Options

### 4.1 View-Only State (default for all users)

```javascript
// Applied on canvas init and when exiting edit mode
function htSetViewMode() {
    if (!window._cy) return;
    window.HT_READONLY = true;
    window._cy.autoungrabify(true);    // nodes cannot be dragged
    window._cy.autounselectify(true);  // nodes cannot be selected via click
    window._cy.boxSelectionEnabled(false);
    window._cy.userZoomingEnabled(true);   // zoom always allowed
    window._cy.userPanningEnabled(true);   // pan always allowed
}
```

Interactions available in view mode:
- Pan (click-drag on background)
- Zoom (scroll wheel / pinch)
- Fit to screen (`F` key)
- Tap node → opens device detail panel (read-only)
- Tap edge → opens connection detail panel (read-only)
- Escape → close panels

### 4.2 Edit State (Contributor/Admin only, after toggle)

```javascript
// Applied when entering edit mode
function htSetEditMode() {
    if (!window._cy) return;
    window.HT_READONLY = false;
    window._cy.autoungrabify(false);   // nodes draggable
    window._cy.autounselectify(false); // nodes selectable
    window._cy.boxSelectionEnabled(true);
}
```

Interactions available in edit mode (in addition to view mode):
- Drag nodes to reposition
- Select nodes (click / box-select)
- Context menu (right-click node)
- Delete / Backspace — delete selected
- Ctrl+D — duplicate selected
- Ctrl+Z — undo last position
- Ctrl+S — save layout
- Palette drag-and-drop to create nodes
- Edge creation via "Start Association"
- Autosave fires on `dragfree`

---

## 5. File-by-File Changes

### 5.1 New file: `src/ui/components/canvas_mode.py` (~40 lines)

Hides the Cytoscape interaction state transition. Provides two JS snippets as Python string constants:

```python
"""Canvas mode transitions — view-only ↔ edit interaction states.

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
        window._cy.autounselectify(true);
        window._cy.boxSelectionEnabled(false);
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
    };
})();
"""
```

Both functions are injected once on page load (via `ui.add_body_html`). The topology page calls `htSetViewMode()` or `htSetEditMode()` via `ui.run_javascript()` on toggle.

### 5.2 New file: `src/ui/components/topology_edit_toggle.py` (~80 lines)

Hides the Edit/Stop Editing button, its visibility logic, and the draft-device warning.

**Signature:**

```python
def render_edit_toggle(
    user_role: str,
    on_enter_edit: Callable[[], Awaitable[None]],
    on_exit_edit: Callable[[], Awaitable[None]],
) -> None:
```

**Behaviour:**
- If `user_role` is `"Reader"` → renders nothing (returns immediately).
- Otherwise renders an "Edit" button (icon: `edit`) styled per design tokens.
- On click → calls `on_enter_edit` callback. Button label changes to "Stop Editing" (icon: `edit_off`).
- On "Stop Editing" click:
  1. Runs JS to check for draft devices: `window._cy.nodes('.draft').length` (future HT-051 hook; returns 0 if no `.draft` class exists).
  2. If draft count > 0: shows a NiceGUI confirmation dialog — "You have {N} unpublished draft device(s). They will remain as drafts on this View. Continue?"
  3. If confirmed (or count is 0): triggers autosave flush via `ui.run_javascript('if(window._htFlushAutosave) window._htFlushAutosave()')`, then calls `on_exit_edit`.
- Button uses design token colours: `var(--ht-accent)` background in edit-active state, `var(--ht-bg-surface-raised)` in default state.

### 5.3 Modified: `src/ui/pages/topology.py` (~200 lines after changes)

**Changes summary:**
1. Import `canvas_mode.py` constants and `topology_edit_toggle.py` renderer.
2. Set `HT_READONLY = true` for **all** users (remove the `if role == Role.Reader` branch).
3. Inject mode transition JS functions via `ui.add_body_html`.
4. Hide palette initially for all users (not just Readers).
5. Add `_palette_container` reference — a `ui.element("div")` wrapper around `render_palette()` with `visible=False`.
6. Render `render_edit_toggle(user_role, on_enter_edit, on_exit_edit)` inside the `header_actions` lambda alongside `render_layout_bar`.
7. Define `on_enter_edit` / `on_exit_edit` callbacks that toggle `_palette_container.set_visibility()` and call `htSetEditMode()` / `htSetViewMode()`.

**Detailed diff description:**

```python
# BEFORE (line ~127):
if role == Role.Reader:
    ui.add_body_html('<script>window.HT_READONLY = true;</script>')
else:
    ui.add_body_html('<script>window.HT_READONLY = false;</script>')

# AFTER:
ui.add_body_html('<script>window.HT_READONLY = true;</script>')
ui.add_body_html(f"<script>{VIEW_MODE_JS}</script>")
ui.add_body_html(f"<script>{EDIT_MODE_JS}</script>")
```

```python
# BEFORE (palette section ~139):
if role != Role.Reader:
    with ui.element("div").style("flex-shrink: 0; overflow-y: auto;"):
        render_palette()

# AFTER:
palette_container = ui.element("div").style(
    "flex-shrink: 0; overflow-y: auto;"
)
palette_container.set_visibility(False)
if role != Role.Reader:
    with palette_container:
        render_palette()
```

```python
# header_actions lambda — BEFORE:
header_actions=lambda: render_layout_bar(token, user_role),

# AFTER:
header_actions=lambda: _render_header_actions(token, user_role, palette_container),
```

New helper (defined inside `topology_page` or as module-level):

```python
def _render_header_actions(
    token: str,
    user_role: str,
    palette_container: ui.element,
) -> None:
    render_layout_bar(token, user_role)
    render_edit_toggle(
        user_role,
        on_enter_edit=_make_enter_edit(palette_container),
        on_exit_edit=_make_exit_edit(palette_container),
    )
```

**Enter/exit callbacks:**

```python
def _make_enter_edit(palette_container: ui.element) -> Callable:
    async def _enter() -> None:
        palette_container.set_visibility(True)
        await ui.run_javascript("htSetEditMode()")
        # Wire event handlers if not already wired
        await ui.run_javascript(
            "if(!window._htEventsWired && window._htInitEventHandlers){"
            "window._htInitEventHandlers(window._htDeviceShapes||{});"
            "window._htEventsWired=true;}"
        )
    return _enter

def _make_exit_edit(palette_container: ui.element) -> Callable:
    async def _exit() -> None:
        await ui.run_javascript("if(window._htFlushAutosave) window._htFlushAutosave()")
        palette_container.set_visibility(False)
        await ui.run_javascript("htSetViewMode()")
    return _exit
```

### 5.4 Modified: `src/ui/components/canvas_js.py` (lines ~97-100)

Currently, event handlers are wired eagerly based on `HT_READONLY`:

```javascript
// BEFORE:
if (!window.HT_READONLY) {
    window._htInitEventHandlers(deviceShapes || {});
}

// AFTER:
// Store deviceShapes for deferred wiring when entering edit mode
window._htDeviceShapes = deviceShapes || {};
// Event handlers are wired on-demand when edit mode is entered.
// For Readers, they are never wired.
```

This change defers event handler wiring. On entering edit mode, `topology.py`'s `_enter_edit` callback calls `_htInitEventHandlers` if not already wired (guarded by `_htEventsWired` flag).

Additionally, the `autoungrabify` behaviour must be set after canvas init:

```javascript
// AFTER cy init (insert after window._cy = cy; line):
// Default to view-only interaction state for all users
cy.autoungrabify(true);
cy.autounselectify(true);
cy.boxSelectionEnabled(false);
```

### 5.5 Modified: `src/ui/components/canvas_js_utils.py` (autosave guard)

Add a view-mode guard to `_htFlushAutosave`:

```javascript
// BEFORE:
window._htFlushAutosave = function() {
    if (window._htAutosaveTimer) { ... }
    if (!window._htDiagramId || window._htDiagramVersion == null) return;
    ...

// AFTER:
window._htFlushAutosave = function() {
    if (window._htAutosaveTimer) {
        clearTimeout(window._htAutosaveTimer);
        window._htAutosaveTimer = null;
    }
    if (window.HT_READONLY) return;  // ← NEW: no-op in view mode
    if (!window._htDiagramId || window._htDiagramVersion == null) return;
    ...
```

The `beforeunload` handler already calls `_htFlushAutosave` which will now no-op in view mode. When exiting edit mode, the `on_exit_edit` callback explicitly flushes *before* setting `HT_READONLY = true`, ensuring pending changes are saved.

### 5.6 Modified: `src/ui/components/canvas_shortcuts.py` (no changes needed)

All write-action shortcuts already check `if (window.HT_READONLY) return;`. Read-safe shortcuts (Escape, F for fit, Ctrl+A) remain active in view mode. **No modifications required.**

### 5.7 Modified: `src/ui/components/canvas_zoom.py` (no changes needed)

Zoom controls (plus, minus, fit) are read-safe. **No modifications required.**

### 5.8 Modified: `src/ui/components/topology_layout_bar.py` (minor)

The layout save/rename/delete buttons should be hidden in view mode. The `render_layout_bar` function already uses `is_editor` to gate these controls, but this only checks role. Add an `edit_mode` parameter:

```python
# BEFORE:
def render_layout_bar(token: str, user_role: str) -> None:

# AFTER:
def render_layout_bar(token: str, user_role: str, edit_mode: bool = False) -> None:
```

The save/rename/delete buttons become conditioned on `is_editor and edit_mode`. The layout **selector** (dropdown) remains visible in view mode — users can switch between saved layouts for browsing. Only mutation controls hide.

The `topology.py` caller must pass the current `edit_mode` state and re-render the header when mode toggles.

---

## 6. Autosave Behaviour

| Mode | Autosave triggers? | `beforeunload` flushes? |
|---|---|---|
| View mode | No — `dragfree` never fires (autoungrabify=true); `_htFlushAutosave` no-ops via `HT_READONLY` guard | No-op (guard) |
| Edit mode | Yes — same 800ms debounce on `dragfree` as today | Yes — same `beforeunload` as today |
| Transition edit→view | `on_exit_edit` explicitly calls `_htFlushAutosave` *before* setting `HT_READONLY=true` | N/A |
| Page navigate away (edit) | `beforeunload` fires → `_htFlushAutosave` runs (HT_READONLY still false until page unloads) | Yes |

---

## 7. Edge Cases

### 7.1 Switching to View Mode With Unsaved Changes
The `on_exit_edit` callback flushes autosave before transitioning. Node positions saved via `dragfree` debounce may still be pending — the explicit flush call catches them. No data loss.

### 7.2 Switching to View Mode With Draft Devices (future HT-051)
The toggle component checks `window._cy.nodes('.draft').length`. If > 0, a confirmation dialog warns the user. Drafts remain on canvas in both modes — they are just not interactable in view mode. This is a forward-compatible hook; until HT-051 adds `.draft` class, the count is always 0.

### 7.3 Keyboard Shortcuts in View Mode
All write shortcuts (`Delete`, `Ctrl+D`, `Ctrl+Z`, `Ctrl+S`) already early-return when `HT_READONLY = true`. Read shortcuts (`Escape`, `F`, `Ctrl+A`) remain functional. No changes needed.

### 7.4 Context Menu in View Mode
The `_CONTEXT_MENU_JS` handler already checks `if (window.HT_READONLY) return;`. No changes needed.

### 7.5 Multiple Tabs
Mode state is per-page-instance. Two tabs of the same view each independently start in view mode. There is no cross-tab mode synchronisation (same last-write-wins model as current autosave).

### 7.6 Browser Back/Forward
NiceGUI re-executes the page function on navigation. Mode resets to view-only on every page entry. No stale edit state.

### 7.7 layout_id Query Parameter (view-only deep link)
Not addressed in this RFC — HT-047 defines `topology_id` routing. When `layout_id` is supported on the topology route, the page opens in view mode by default, which is the correct behaviour. No special handling needed.

---

## 8. Security Boundaries

- **RBAC is double-gated:** The UI hides the Edit button for Readers (client-side), and the API enforces role checks on all mutation endpoints (server-side). Even if a Reader bypasses the UI gate, API calls to `POST /api/devices/`, `PATCH /api/diagrams/`, etc. will return 403.
- No new secrets or credentials are introduced.
- No new API endpoints.
- No changes to `src/api/middleware/auth.py`.

---

## 9. Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `src/ui/components/canvas_mode.py` | **Create** | JS constants for `htSetViewMode()` / `htSetEditMode()` |
| `src/ui/components/topology_edit_toggle.py` | **Create** | Edit/Stop Editing button with RBAC gate and draft warning |
| `src/ui/pages/topology.py` | **Modify** | Default to view-only; wire mode toggle; defer palette visibility |
| `src/ui/components/canvas_js.py` | **Modify** | Defer event handler wiring; set view-only Cytoscape options after init |
| `src/ui/components/canvas_js_utils.py` | **Modify** | Add `HT_READONLY` guard to `_htFlushAutosave` |
| `src/ui/components/topology_layout_bar.py` | **Modify** | Add `edit_mode` parameter; hide mutation buttons in view mode |

---

## 10. Test Plan

### 10.1 Unit Tests (domain — not applicable)
No domain logic changes. No new unit tests.

### 10.2 UI Integration Tests

| Test | Validates |
|---|---|
| Page loads with `HT_READONLY = true` for Admin | Default view-only mode applies regardless of role |
| Page loads with `HT_READONLY = true` for Contributor | Same |
| Page loads with `HT_READONLY = true` for Reader | Same (existing behaviour preserved) |
| Edit button visible for Admin | RBAC-gated toggle renders |
| Edit button visible for Contributor | RBAC-gated toggle renders |
| Edit button NOT visible for Reader | Permanent view-only |
| Click Edit → `HT_READONLY` becomes `false` | Mode transition works |
| Click Edit → palette becomes visible | Palette toggling works |
| Click Edit → `autoungrabify` is `false` | Cytoscape interaction options updated |
| Click Stop Editing → `HT_READONLY` becomes `true` | Reverse transition works |
| Click Stop Editing → palette hides | Palette toggling works |
| Click Stop Editing → `autoungrabify` is `true` | Cytoscape interaction options restored |
| Click Stop Editing → autosave flushes | Pending positions saved before view mode |
| Context menu blocked in view mode | Existing `HT_READONLY` guard holds |
| Delete key blocked in view mode | Existing shortcut guard holds |
| Drag blocked in view mode (`autoungrabify`) | Node positions immutable |
| Page reload resets to view mode | Mode not persisted |
| Layout dropdown works in view mode | Browse-only layout selection |
| Layout save/rename/delete hidden in view mode | Mutation controls gated on edit_mode |
| Autosave does NOT fire in view mode | `_htFlushAutosave` guard rejects |

### 10.3 E2E Tests (Playwright — User Simulator)

| Scenario | Steps |
|---|---|
| Reader browses topology | Login as Reader → navigate to topology → verify no Edit button → attempt right-click → no context menu → verify panning works |
| Contributor edits and returns to view | Login as Contributor → navigate → verify view-only → click Edit → drag a node → click Stop Editing → verify node position was autosaved → verify dragging is now blocked |
| Admin session lifecycle | Login as Admin → navigate → click Edit → add device via palette → click Stop Editing → confirm prompt if drafts exist → verify back in view mode |
