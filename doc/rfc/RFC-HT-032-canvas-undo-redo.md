# RFC: Canvas Undo/Redo For The Topology Designer

**Story:** HT-032  
**Tracker:** T-001  
**Status:** Draft  
**Date:** 2026-04-14  
**Author:** Architect

---

## 1. Overview

HT-032 adds real undo/redo to the topology designer for the write paths users actually hit today: node moves, edge create/delete, published node delete, draft node delete, remove-from-view, and device detail-panel PATCH updates. HT-051's remove-from-view follow-up is folded into the same stack; it is not a separate mechanism.

The current code is fragmented in a way that makes mixed undo impossible:

- `src/ui/components/canvas_shortcuts.py` only knows a single `_htUndoStack` position entry.
- `src/ui/components/canvas_js_interactions.py` records one `dragfree` position snapshot, not a real stack.
- `src/ui/components/canvas_js_helpers.py` and `src/ui/components/canvas_events.py` call mutation APIs directly from JS for published actions.
- `src/ui/components/device_detail_panel.py` performs PATCHes from Python, outside any stack.
- HT-051 remove-from-view is local-only and autosaves, but it does not register a reversible action.

The implementation contract in this RFC is:

1. Keep the undo/redo stacks client-side and per-page-session.
2. Split actions into `local` reversals and `api` reversals.
3. Stop using direct JS fetches for published undoable mutations; JS emits a request, Python executes the mutation, then JS receives a normalized action result.
4. Add a dedicated published-device canvas delete/restore contract because the plain `DELETE /api/devices/{id}` route cannot return the diagram-version and snapshot data the page must keep synchronized.
5. Preserve the one-way flow from the canvas-bridge skill: JS emits events, Python/API mutates persisted state, the page updates the graph after the write succeeds.

## 2. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/ui/components/canvas_undo.py` | The client-side stack semantics, stack-size eviction, busy-locking, and local action replay rules. |
| `src/ui/components/canvas_undo_handlers.py` | The mapping from semantic undo actions to Python/API calls and the JS callback contract used to resolve success or failure. |
| `src/services/canvas_undo_service.py` | How a published-device delete is snapshotted, applied, and restored across devices, connections, and diagram layouts. |
| `src/models/canvas_undo.py` | The wire format of undo snapshot payloads returned by the API. |
| `src/ui/components/topology_undo_bar.py` | The toolbar button layout, IDs, and tooltip/disabled-state wiring. |
| `src/domain/devices.py` | The pure Cytoscape JSON surgery required to extract, remove, and restore a device placement inside saved diagram JSON. |

## 3. Data Model Changes

### 3.1 Database tables and Alembic

None. HT-032 adds no tables, no columns, and no migration.

### 3.2 New API-only schemas: `src/models/canvas_undo.py`

These are request/response contracts only. They are not SQLModel table models.

```python
class DiagramVersionRef(SQLModel):
    diagram_id: uuid.UUID
    version: int


class DiagramPlacementSnapshot(SQLModel):
    diagram_id: uuid.UUID
    node: dict[str, object]
    was_collapsed: bool = False


class PublishedConnectionSnapshot(SQLModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    type: ConnectionType
    label: str | None = None


class PublishedDeviceSnapshot(SQLModel):
    id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus
    ip: str | None = None
    mac: str | None = None
    os: str | None = None
    notes: str | None = None
    location_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    version: int


class PublishedDeviceDeleteSnapshot(SQLModel):
    device: PublishedDeviceSnapshot
    connections: list[PublishedConnectionSnapshot]
    placements: list[DiagramPlacementSnapshot]


class PublishedDeviceCanvasDeleteResult(SQLModel):
    snapshot: PublishedDeviceDeleteSnapshot
    modified_diagrams: list[DiagramVersionRef]


class PublishedDeviceCanvasRestoreResult(SQLModel):
    modified_diagrams: list[DiagramVersionRef]
```

### 3.3 Client-side stack contract

The stack entry stays in JS. It is not persisted and it is not sent back to the API as an opaque blob.

```javascript
type UndoEntry = {
  entry_id: string;
  type:
    | 'move_node'
    | 'create_edge'
    | 'delete_published_node'
    | 'delete_draft_node'
    | 'delete_edge'
    | 'remove_from_view'
    | 'update_device_field';
  label: string;
  execution: 'local' | 'api';
  forward: { op: string; payload: object };
  reverse: { op: string; payload: object };
};
```

Rules:

- `label` is created once when the action is recorded and drives both toolbar tooltips and keyboard hints.
- `execution='local'` means the action is replayed entirely in JS and then autosaved if needed.
- `execution='api'` means JS requests Python execution and does not move the entry between stacks until Python reports success.
- API-backed entries are peeked, not popped, while a request is in flight.

### 3.4 Action taxonomy and payload shape

Shared local structural snapshot:

```json
{
  "nodes": [
    {"group": "nodes", "data": {"id": "..."}, "position": {"x": 120, "y": 240}, "classes": "draft"}
  ],
  "edges": [
    {"group": "edges", "data": {"id": "edge-1", "source": "...", "target": "..."}}
  ]
}
```

| Action | Producers | Execution | Payload shape |
|---|---|---|---|
| `move_node` | canvas drag gesture | `local` | `{"nodes": [{"id": str, "from": {"x": n, "y": n}, "to": {"x": n, "y": n}}]}` |
| `create_edge` | shift-tap association flow | `local` for draft edges, `api` for published edges | `{"scope": "draft|published", "connection_id": str, "source_id": str, "target_id": str, "connection_type": str, "label": str|null}` |
| `delete_published_node` | context menu delete on a published node | `api` | `{"snapshot": PublishedDeviceDeleteSnapshot}` |
| `delete_draft_node` | Delete key or context menu on a draft node | `local` | `NodeSetSnapshot` |
| `delete_edge` | Delete key, edge context menu, connection detail delete button | `local` for draft edges, `api` for published edges | same shape as `create_edge` |
| `remove_from_view` | HT-051 context menu item | `local` | `NodeSetSnapshot` for the removed node or container subtree |
| `update_device_field` | device detail panel inline editor and status select | `api` | `{"device_id": str, "field": str, "before": value, "after": value, "version_cursor": int, "node_patch": {...}}` |

Exact payload notes:

- `move_node` uses a list, not a single node, so container drags can capture descendants if Cytoscape moves them too.
- `delete_draft_node` and `remove_from_view` both use `NodeSetSnapshot`; a simple node has one node entry, a container action may carry the whole descendant subtree.
- `create_edge` and `delete_edge` deliberately share one semantic payload shape so redo can mutate `connection_id` after re-creation without changing the action type.
- `update_device_field.version_cursor` always stores the device version returned by the last successful PATCH so undo and redo remain version-correct across repeated cycles.

### 3.5 Published vs. draft reversal strategy

Draft and view-local reversals:

- `move_node`
- `delete_draft_node`
- draft `create_edge`
- draft `delete_edge`
- `remove_from_view`

These actions never call inventory APIs. JS mutates `window._cy`, schedules autosave, and pushes the entry directly.

Published reversals:

- published `create_edge`
- published `delete_edge`
- `delete_published_node`
- `update_device_field`

These actions do not call fetch directly from JS after HT-032. JS emits a semantic action request, Python executes it, then JS receives either:

- success: apply graph patch, push/move stack entry, update active diagram version if returned
- failure: show toast, keep the entry on the source stack, do not mutate the graph

### 3.6 Redo invalidation, cap, and lifetime

- A successful brand-new forward action clears the redo stack.
- A failed forward action does not clear the redo stack.
- A successful undo moves the entry from undo to redo.
- A successful redo moves the entry from redo to undo.
- The undo stack is capped at 50 entries. On push 51, evict the oldest undo entry.
- The stack lives only in page memory. On `pagehide`, or on a fresh topology-page load, reset both stacks.
- No `localStorage`, no cookies, and no persistence in `cytoscape_json`.

## 4. Domain Logic

### 4.1 Modified file: `src/domain/devices.py`

Keep the layout JSON extraction and restoration pure. Do not put Cytoscape JSON list surgery inside the new service.

Add two helpers and tighten one existing helper:

```python
def extract_device_view_snapshot(
    cytoscape_json: dict[str, object],
    device_id_str: str,
) -> tuple[dict[str, object] | None, bool]:
    """Return (node_snapshot, was_collapsed) for a placed device."""


def restore_device_to_cytoscape_json(
    cytoscape_json: dict[str, object],
    node_snapshot: dict[str, object],
    was_collapsed: bool,
) -> tuple[dict[str, object], bool]:
    """Reinsert a node element and collapsed-state marker if missing."""
```

Modify `filter_device_from_cytoscape_json(...)` so it also removes the device ID from `collapsedNodes` and preserves the original `elements` container shape.

Invariants:

- `extract_device_view_snapshot` must support both `elements: list[...]` and `elements: {nodes: [], edges: []}` layouts.
- `restore_device_to_cytoscape_json` must be idempotent: if the node already exists, return unchanged JSON with `False`.
- `restore_device_to_cytoscape_json` must not create duplicate `collapsedNodes` entries.

Before/after diff:

```diff
--- before: src/domain/devices.py
+++ after: src/domain/devices.py
@@
 def filter_device_from_cytoscape_json(
     cytoscape_json: dict[str, object],
     device_id_str: str,
 ) -> tuple[dict[str, object], bool]:
-    """Remove node/edge elements referencing *device_id_str* from cytoscape JSON.
+    """Remove node/edge elements and collapsed-state references for *device_id_str*.
@@
-    result["elements"] = filtered
+    result["elements"] = filtered_or_rebuilt_container
+    result["collapsedNodes"] = [cid for cid in collapsed if str(cid) != device_id_str]
     return result, True

+def extract_device_view_snapshot(...):
+    ...

+def restore_device_to_cytoscape_json(...):
+    ...
```

## 5. Service Layer

### 5.1 New file: `src/services/canvas_undo_service.py`

This module owns the only hard backend problem in HT-032: published-device delete and restore.

Exact service surface:

```python
def delete_published_device_for_canvas(
    device_id: uuid.UUID,
    session: Session,
) -> PublishedDeviceCanvasDeleteResult:
    """Capture a restore snapshot, delete the device, and return modified diagram versions."""


def restore_published_device_for_canvas(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
) -> PublishedDeviceCanvasRestoreResult:
    """Restore a previously deleted published device and its placements in one transaction."""
```

Delete flow:

1. Load device or 404.
2. Reuse the existing child-device guard. Published containers with children still return 400.
3. Read current connections via `connection_repository.get_by_device(...)`.
4. Read every layout via `diagram_repository.get_all_layouts(...)`.
5. For each layout that contains the device, call `extract_device_view_snapshot(...)`, then `filter_device_from_cytoscape_json(...)`, then increment `layout.version += 1` before `diagram_repository.update(...)`.
6. Delete the device and its connections in the same transaction.
7. Commit once.
8. Return `PublishedDeviceDeleteSnapshot` plus a `modified_diagrams` version map.

Restore flow:

1. Reject with 409 if the device ID already exists.
2. Recreate the `Device` row with the original ID and original `version` from the snapshot.
3. Recreate each connection row with the original IDs from the snapshot.
4. For each saved placement, lock the diagram row with `get_by_id_for_update(...)`, call `restore_device_to_cytoscape_json(...)`, increment `layout.version += 1`, then update.
5. Commit once.
6. Return the new `modified_diagrams` version map.

Error mapping:

- missing device on delete: 404
- device has children: 400
- restore device ID already reused: 409
- restore diagram missing: 409 with a layout-specific detail string
- connection/device integrity failure: 409 with the underlying business message, not a raw SQL error

### 5.2 Existing services deliberately unchanged

- `src/services/device_service.py::delete` stays as the inventory delete path.
- `src/services/connection_service.py` stays the create/delete path for published edges.
- `src/services/diagram_service.py::partial_update` stays the autosave/manual-save path.

Do not try to retrofit undo semantics into those existing service functions. The new canvas undo service exists precisely to avoid overloading them with UI-specific snapshot behavior.

## 6. API Layer

### 6.1 Modified file: `src/api/routers/device_sub_routes.py`

Add two device-scoped canvas routes.

```python
@router.post(
    "/{device_id}/canvas-delete",
    response_model=PublishedDeviceCanvasDeleteResult,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def canvas_delete_device(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> PublishedDeviceCanvasDeleteResult:
    return canvas_undo_service.delete_published_device_for_canvas(device_id, session)


@router.post(
    "/{device_id}/restore",
    response_model=PublishedDeviceCanvasRestoreResult,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def restore_canvas_deleted_device(
    device_id: uuid.UUID,
    data: PublishedDeviceDeleteSnapshot,
    session: Session = Depends(get_session),
) -> PublishedDeviceCanvasRestoreResult:
    if data.device.id != device_id:
        raise HTTPException(status_code=400, detail="Path device_id does not match snapshot device.id")
    return canvas_undo_service.restore_published_device_for_canvas(data, session)
```

Before/after diff:

```diff
--- before: src/api/routers/device_sub_routes.py
+++ after: src/api/routers/device_sub_routes.py
@@
 from src.models.connection import ConnectionResponse
+from src.models.canvas_undo import (
+    PublishedDeviceCanvasDeleteResult,
+    PublishedDeviceCanvasRestoreResult,
+    PublishedDeviceDeleteSnapshot,
+)
@@
 @router.get(
     "/{device_id}/connections",
@@
+@router.post(
+    "/{device_id}/canvas-delete",
+    response_model=PublishedDeviceCanvasDeleteResult,
+    dependencies=[Depends(require_role(Role.Contributor))],
+)
+def canvas_delete_device(...):
+    ...
+
+
+@router.post(
+    "/{device_id}/restore",
+    response_model=PublishedDeviceCanvasRestoreResult,
+    dependencies=[Depends(require_role(Role.Contributor))],
+)
+def restore_canvas_deleted_device(...):
+    ...
```

### 6.2 Existing routes reused by the undo coordinator

- `POST /api/connections/` for published edge create and edge recreation during undo
- `DELETE /api/connections/{id}` for published edge delete and redo of delete-edge
- `PATCH /api/devices/{id}` for detail-panel device-field undo/redo

No new connection routes are needed.

## 7. UI Layer

### 7.1 New file: `src/ui/components/canvas_undo.py`

This file owns:

- `window._htUndoState = { undoStack, redoStack, busy }`
- stack push/move/trim/reset helpers
- `window._htRequestCanvasAction(action)` for API-backed forward actions
- `window._htRequestUndo()` and `window._htRequestRedo()`
- local action application helpers
- `ht:undo-state-changed` dispatch after every stack mutation
- DOM updates for the toolbar buttons' disabled state and `title` attribute

Before emitting `delete_published_node` or replaying its undo/redo path, `window._htRequestCanvasAction(...)` must ensure the current layout is settled:

- if `window._htAutosaveTimer` or `window._htAutosavePending` is set, call `window._htFlushAutosave()` first
- wait until `window._htAutosaveInFlight`, `window._htAutosaveRequestInFlight`, and `window._htAutosavePending` are all false
- if autosave conflicts or fails, abort the published delete/restore request and leave the stack unchanged

Expose these exact window functions because they are called from separate injected script blocks:

```javascript
window._htRequestCanvasAction = function(action) { ... };
window._htPushCommittedUndoEntry = function(entry) { ... };
window._htRequestUndo = function() { ... };
window._htRequestRedo = function() { ... };
window._htResolveUndoApiSuccess = function(direction, entryId, result) { ... };
window._htResolveUndoApiFailure = function(direction, entryId, message) { ... };
window._htResetUndoState = function() { ... };
```

Important implementation rule from repo memory: these helpers must be `window`-scoped, not closure-only, because `canvas_shortcuts.py`, `topology_undo_bar.py`, `canvas_events.py`, and `device_detail_panel.py` all run in separate `<script>` blocks.

### 7.2 New file: `src/ui/components/canvas_undo_handlers.py`

This Python module registers the NiceGUI event bridge and performs every API-backed action.

Exact surface:

```python
def register_canvas_undo_handlers(token: str, user_role: str) -> None:
    """Register ui.on handlers for canvas action requests and undo/redo requests."""


async def apply_undoable_device_field_patch(
    token: str,
    *,
    device_id: uuid.UUID,
    field: str,
    before: object,
    after: object,
    version_cursor: int,
) -> tuple[bool, int]:
    """Apply a PATCH-backed device-field change and return (ok, new_version)."""
```

Handler responsibilities:

- validate `user_role in {Admin, Contributor}` before any write
- for published canvas deletes, call the new `/canvas-delete` and `/restore` routes
- for edge create/delete, call the existing connection routes
- for device-field PATCH undo/redo, call the existing device PATCH route
- on success, call back into JS with one normalized result payload
- on failure, call back into JS with an error string only

### 7.3 New file: `src/ui/components/topology_undo_bar.py`

Render two editor-only buttons with stable DOM IDs:

- `ht-undo-button`
- `ht-redo-button`

Behavior:

- default disabled
- visible for `Admin` and `Contributor`, hidden for `Reader`
- click handler calls `window._htRequestUndo()` / `window._htRequestRedo()`
- `title` attribute is updated by JS to `Undo: <label>` / `Redo: <label>`
- when `window.HT_READONLY` is true, keep disabled even if the stack is non-empty

### 7.4 Modified file: `src/ui/components/canvas.py`

Inject the new undo script after the draft/event helpers and before the init template.

Before/after diff:

```diff
--- before: src/ui/components/canvas.py
+++ after: src/ui/components/canvas.py
@@
 from src.ui.components.canvas_events import inject_canvas_events
+from src.ui.components.canvas_undo import inject_canvas_undo
@@
     inject_canvas_events()
+    inject_canvas_undo()
     inject_canvas_tooltip()
```

### 7.5 Modified file: `src/ui/components/canvas_shortcuts.py`

Replace the single-entry position undo with stack requests and add redo shortcuts.

Before/after diff:

```diff
--- before: src/ui/components/canvas_shortcuts.py
+++ after: src/ui/components/canvas_shortcuts.py
@@
-        // ── Ctrl+Z / Cmd+Z — undo last position (write only) ────────────────
+        // ── Ctrl+Z / Cmd+Z — undo (write only) ───────────────────────────────
         if (ctrl && key === 'z') {
             if (window.HT_READONLY) return;
-            var entry = window._htUndoStack;
-            if (!entry) return;
-            var node = window._cy.getElementById(entry.nodeId);
-            if (node && node.length) {
-                node.position(entry.prev);
-                window._htNodePositions = window._htNodePositions || {};
-                window._htNodePositions[entry.nodeId] = entry.prev;
-            }
-            window._htUndoStack = null;
+            e.preventDefault();
+            if (e.shiftKey) {
+                if (window._htRequestRedo) window._htRequestRedo();
+            } else {
+                if (window._htRequestUndo) window._htRequestUndo();
+            }
+            return;
+        }
+
+        // ── Ctrl+Y — redo (write only) ──────────────────────────────────────
+        if (ctrl && (key === 'y' || key === 'Y')) {
+            if (window.HT_READONLY) return;
+            e.preventDefault();
+            if (window._htRequestRedo) window._htRequestRedo();
             return;
         }
```

### 7.6 Modified file: `src/ui/components/canvas_js_interactions.py`

Stop creating undo state in `dragfree`. Record a gesture at `dragstart`, commit one move entry at `dragend`, and leave `dragfree` to position bookkeeping only.

Before/after diff:

```diff
--- before: src/ui/components/canvas_js_interactions.py
+++ after: src/ui/components/canvas_js_interactions.py
 @@
-        cy.on('dragfree', 'node', function(evt) {
-            var node = evt.target;
-            window._htNodePositions = window._htNodePositions || {};
-            var prev = window._htNodePositions[node.id()] || node.position();
-            window._htUndoStack = {
-                nodeId: node.id(),
-                prev: { x: prev.x, y: prev.y },
-                next: node.position()
-            };
-            window._htNodePositions[node.id()] = node.position();
-            if (window.scheduleAutosave) window.scheduleAutosave(800);
-        });
+        cy.on('dragstart', 'node', function(evt) {
+            if (window.HT_READONLY) return;
+            if (window._htBeginMoveGesture) window._htBeginMoveGesture(evt.target);
+        });
+
+        cy.on('dragend', 'node', function(evt) {
+            if (window.HT_READONLY) return;
+            if (window._htCommitMoveGesture) window._htCommitMoveGesture(evt.target);
+        });
+
+        cy.on('dragfree', 'node', function(evt) {
+            window._htNodePositions = window._htNodePositions || {};
+            window._htNodePositions[evt.target.id()] = evt.target.position();
+        });
```

### 7.7 Modified file: `src/ui/components/canvas_js_helpers.py`

Published edge create/delete stops using fetch directly. Draft edges remain local.

Before/after diff:

```diff
--- before: src/ui/components/canvas_js_helpers.py
+++ after: src/ui/components/canvas_js_helpers.py
 @@
-            fetch('/api/connections/', {
-                method: 'POST',
-                credentials: 'include',
-                headers: {
-                    'Content-Type': 'application/json',
-                },
-                body: JSON.stringify({ source_id: sourceId, target_id: targetId, type: 'Ethernet' })
-            }).then(function(r) { return r.ok ? r.json() : null; })
-              .then(function(conn) {
-                ...
-              });
+            if (window._htRequestCanvasAction) {
+                window._htRequestCanvasAction({
+                    type: 'create_edge',
+                    payload: {
+                        scope: 'published',
+                        source_id: sourceId,
+                        target_id: targetId,
+                        connection_type: 'Ethernet',
+                        label: null
+                    }
+                });
+            }
             return;
@@
-                fetch('/api/connections/' + d.id, {
-                    method: 'DELETE',
-                    credentials: 'include',
-                }).then(function(r) {
-                    if (r.ok || r.status === 404) window._cy.getElementById(d.id).remove();
-                });
+                if (window._htRequestCanvasAction) {
+                    window._htRequestCanvasAction({
+                        type: 'delete_edge',
+                        payload: {
+                            scope: 'published',
+                            connection_id: d.id,
+                            source_id: d.source || (d.data && d.data.source),
+                            target_id: d.target || (d.data && d.data.target),
+                            connection_type: d.type || (d.data && d.data.connection_type) || 'Ethernet',
+                            label: d.raw_label || d.label || (d.data && d.data.raw_label) || null
+                        }
+                    });
+                }
             });
```

### 7.8 Modified file: `src/ui/components/canvas_events.py`

Published node delete becomes an undo-aware action request. Draft delete remains local and pushes a `delete_draft_node` entry.

Before/after diff:

```diff
--- before: src/ui/components/canvas_events.py
+++ after: src/ui/components/canvas_events.py
 @@
-            _confirmDelete("Delete device '" + _escapeHtml(deviceName) + "'? This cannot be undone.", function() {
-                fetch('/api/devices/' + d.id, {
-                    method: 'DELETE',
-                    credentials: 'include',
-                }).then(function(r) {
-                    if (r.ok || r.status === 404) {
-                        var el = window._cy.getElementById(d.id);
-                        if (el.length > 0) {
-                            el.remove();
-                        }
-                    } else {
-                        ...
-                    }
-                });
-            });
+            _confirmDelete("Delete device '" + _escapeHtml(deviceName) + "'? This cannot be undone.", function() {
+                if (!window._htRequestCanvasAction) return;
+                window._htRequestCanvasAction({
+                    type: 'delete_published_node',
+                    payload: {
+                        device_id: d.id,
+                        active_diagram_id: window._htDiagramId || null,
+                        active_node: window._htSnapshotNodeSet ? window._htSnapshotNodeSet(window._cy.getElementById(d.id)) : null
+                    }
+                });
+            });
```

### 7.9 Modified file: `src/ui/components/canvas_draft_events.py`

HT-051 remove-from-view must build a reversible local entry instead of mutating the graph ad hoc.

Before/after diff:

```diff
--- before: src/ui/components/canvas_draft_events.py
+++ after: src/ui/components/canvas_draft_events.py
 @@
-                    var el = window._cy.getElementById(d.id);
-                    if (el.length > 0) {
-                        el.connectedEdges().remove();
-                        el.remove();
-                    }
-                    if (window.scheduleAutosave) window.scheduleAutosave(800);
-                    document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
-                    _notify('Device removed from View.', 'info');
+                    var el = window._cy.getElementById(d.id);
+                    if (!el.length || !window._htCommitLocalRemoveFromView) return;
+                    window._htCommitLocalRemoveFromView(el);
```

`_htCommitLocalRemoveFromView(el)` must:

- capture a `NodeSetSnapshot`
- remove the node or container subtree
- schedule autosave
- dispatch `ht:stencil-refresh`
- push a `remove_from_view` entry with reverse payload equal to the captured snapshot

### 7.10 Modified file: `src/ui/components/device_panel_helpers.py`

Turn the inline editor into a caller-supplied save hook so topology can route device field updates through the undo coordinator.

Before/after diff:

```diff
--- before: src/ui/components/device_panel_helpers.py
+++ after: src/ui/components/device_panel_helpers.py
 @@
 def render_editable_row(
     label: str,
     current: Optional[str],
@@
-    on_saved: Callable[[], None] | None = None,
+    on_saved: Callable[[], None] | None = None,
+    save_value: Callable[[Optional[str]], Awaitable[bool]] | None = None,
 ) -> None:
@@
-            async def _save() -> None:
-                new_val: Optional[str] = inp.value.strip() or None
-                try:
-                    async with httpx.AsyncClient() as c:
-                        r = await c.patch(...)
-                    ...
-                except httpx.HTTPError as exc:
-                    ...
+            async def _save() -> None:
+                new_val: Optional[str] = inp.value.strip() or None
+                if save_value is not None:
+                    ok = await save_value(new_val)
+                else:
+                    ok = await _legacy_direct_patch(new_val)
+                if ok and on_saved is not None:
+                    on_saved()
```

### 7.11 Modified file: `src/ui/components/device_detail_panel.py`

Use the undo-aware save path for `name`, `notes`, `ip`, `mac`, `os`, and `status`.

Rules:

- unchanged values do not create stack entries
- only successful PATCHes create stack entries
- the node label/data on the canvas must be patched immediately after a successful change
- `status` uses the same `update_device_field` action type as the inline text rows

### 7.12 Modified file: `src/ui/components/connection_detail_panel.py`

The Delete button must go through the same `delete_edge` action path as keyboard/context-menu delete. Do not leave a second untracked delete path in the page.

The Save button for connection type/label PATCH is explicitly out of scope for HT-032 and remains unchanged.

### 7.13 Modified file: `src/ui/pages/topology.py`

Add the undo bar to the header and register the new handlers once per page.

Before/after diff:

```diff
--- before: src/ui/pages/topology.py
+++ after: src/ui/pages/topology.py
 @@
 from src.ui.components.canvas_shortcuts import inject_canvas_shortcuts
+from src.ui.components.canvas_undo_handlers import register_canvas_undo_handlers
+from src.ui.components.topology_undo_bar import render_topology_undo_bar
@@
 def _render_header_actions(...):
     render_layout_bar(...)
+    render_topology_undo_bar(user_role)
     ui.label("").props('id="ht-draft-badge"')
     render_edit_toggle(...)
@@
 async def topology_page(...):
@@
+    register_canvas_undo_handlers(token, user_role)
@@
-    ui.add_body_html("<script>(function(){window._htEventsWired=false;if(window._htTopologyTeardownInit)return;window._htTopologyTeardownInit=true;window.addEventListener('pagehide',function(){window._htEventsWired=false;});})();</script>")
+    ui.add_body_html("<script>(function(){window._htEventsWired=false;if(window._htTopologyTeardownInit)return;window._htTopologyTeardownInit=true;window.addEventListener('pagehide',function(){window._htEventsWired=false;if(window._htResetUndoState)window._htResetUndoState();});})();</script>")
```

### 7.14 Files intentionally unchanged

- `src/ui/components/canvas_context_menu.py` keeps dispatching the same semantic events; no menu rewrite is needed.
- `src/ui/components/canvas_mode.py` stays the mode gate; undo/redo buttons and shortcuts honor `HT_READONLY` on top of it.
- `src/ui/services/topology_data.py` and helpers do not need stack awareness.

## 8. Security Boundaries

- Readers never see undo/redo buttons and cannot trigger undoable writes.
- `window.HT_READONLY` remains an immediate UX gate for keyboard shortcuts and toolbar clicks.
- Python undo handlers reject non-editor roles before any API call.
- Every persisted mutation still terminates in an API route with `Depends(require_role(Role.Contributor))`.
- Undo snapshots stay in page memory only. They are never written to disk, localStorage, or the database.
- Do not log serialized undo snapshots; they contain device notes, IPs, MACs, and potentially topology structure.

## 9. Edge Cases

| Category | Decision |
|---|---|
| Empty state | Both buttons render disabled. Tooltip text is `Undo unavailable` / `Redo unavailable`. No stack entry is created for no-op moves or unchanged field saves. |
| Boundary values | Stack cap is exactly 50. Entry 51 evicts the oldest undo entry. A move where `from == to` is dropped. A detail-panel save where `before == after` is dropped. |
| Concurrent access | Published PATCH undo/redo uses `version_cursor`. A 409 or 404 keeps the entry on the source stack and shows `Undo failed: <detail>` or `Redo failed: <detail>`. Published device delete/restore also waits for autosave settlement before it reads or mutates server-side layout state. Collaborative merge is still out of scope. |
| Cascade effects | Published device delete snapshot captures direct connections and every affected diagram placement. Existing child-device protection remains: containers with children cannot be globally deleted. Local remove-from-view and draft delete must capture container descendants to avoid orphaned compound-node children. |
| RBAC per operation | Reader: no undo UI, no handler execution, API rejects writes. Contributor/Admin: full stack behavior in edit mode only. |
| Round-trip integrity | Published delete/restore preserves the original device ID and original connection IDs inside the snapshot-backed restore route. Draft and remove-from-view actions preserve exact Cytoscape node/edge payloads. |
| Canvas impact | The delete/restore device routes return updated diagram versions so the page can keep `window._htDiagramVersion` in sync and avoid stale-version autosave conflicts after undoable published deletes. |
| Performance at scale | Stack entries snapshot only the affected structure, not the whole canvas. `delete_published_node` reads connections by device and only diagrams that actually contain the device. The 50-entry cap bounds client memory. |

Additional non-goals inside HT-032:

- connection type/label PATCH undo in `connection_detail_panel.py`
- duplicate-device undo
- container convert/unconvert undo
- draft publish undo

Those actions must remain behaviorally unchanged and must not be silently added to the stack under this story.

## 10. Files To Create/Modify

| File | Action | Purpose |
|---|---|---|
| `doc/rfc/RFC-HT-032-canvas-undo-redo.md` | Create | Implementation contract for HT-032. |
| `src/models/canvas_undo.py` | Create | API-only snapshot/result schemas for published device delete/restore. |
| `src/domain/devices.py` | Modify | Pure helpers for extract/remove/restore of device placements in Cytoscape JSON. |
| `src/services/canvas_undo_service.py` | Create | Transactional published-device snapshot/delete/restore orchestration. |
| `src/api/routers/device_sub_routes.py` | Modify | Add `/canvas-delete` and `/restore` device routes. |
| `src/ui/components/canvas_undo.py` | Create | JS stack manager, local replay helpers, toolbar state sync. |
| `src/ui/components/canvas.py` | Modify | Inject the undo module. |
| `src/ui/components/canvas_shortcuts.py` | Modify | Route Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, and Ctrl+Y to the real stack. |
| `src/ui/components/canvas_js_interactions.py` | Modify | Dragstart/dragend move batching. |
| `src/ui/components/canvas_js_helpers.py` | Modify | Route published edge create/delete through the undo request bridge. |
| `src/ui/components/canvas_events.py` | Modify | Route published node delete through the undo request bridge. |
| `src/ui/components/canvas_draft_events.py` | Modify | Register local remove-from-view undo entries. |
| `src/ui/components/device_panel_helpers.py` | Modify | Accept an injected save callback for undo-aware PATCH actions. |
| `src/ui/components/device_detail_panel.py` | Modify | Record undoable device field changes and status changes. |
| `src/ui/components/connection_detail_panel.py` | Modify | Route published edge deletes through the stack-aware path. |
| `src/ui/components/topology_undo_bar.py` | Create | Undo/redo toolbar controls. |
| `src/ui/components/canvas_undo_handlers.py` | Create | Python-side action executor and `ui.on(...)` registration. |
| `src/ui/pages/topology.py` | Modify | Render undo bar, register handlers, reset stack on `pagehide`. |
| `tests/unit/test_domain_devices.py` | Modify | Cover extract/remove/restore layout helpers and collapsed-state round-trip. |
| `tests/unit/test_canvas_undo.py` | Create | Stack-cap, redo-clear, busy-lock, and local-action JS contract tests. |
| `tests/unit/test_canvas_shortcuts.py` | Modify | Assert redo shortcuts and removal of the single-entry `_htUndoStack` behavior. |
| `tests/unit/test_ui_canvas.py` | Modify | Assert action producers emit undo-aware requests instead of direct fetches. |
| `tests/unit/test_topology_undo_bar_execution.py` | Create | Page-execution coverage for toolbar rendering and click wiring. |
| `tests/unit/test_device_detail_panel_execution.py` | Create | Page-execution coverage for stack-aware device field saves. |
| `tests/unit/test_connection_detail_panel_execution.py` | Create | Page-execution coverage for stack-aware edge delete from the panel. |
| `tests/integration/test_canvas_undo_api.py` | Create | RBAC, snapshot capture, restore, version-sync, and failure-path coverage for the new API routes. |
| `tests/e2e/test_topology_canvas_undo_redo.py` | Create | Browser proof for keyboard and toolbar undo/redo across mixed actions. |

## 11. Test Plan

### 11.1 Unit tests

- `tests/unit/test_domain_devices.py`
  - extracting a node snapshot from list-format and dict-format `elements`
  - removing a device also removes its `collapsedNodes` membership
  - restoring a device is idempotent and preserves `was_collapsed`

- `tests/unit/test_canvas_undo.py`
  - new forward action clears redo only after success
  - failed API undo leaves the entry on the source stack
  - stack eviction at 51 entries drops the oldest undo entry
  - busy lock blocks repeated Ctrl+Z/Ctrl+Y spam while an API request is unresolved
  - `pagehide` reset empties both stacks

- `tests/unit/test_canvas_shortcuts.py`
  - Ctrl/Cmd+Z calls `window._htRequestUndo`
  - Ctrl/Cmd+Shift+Z and Ctrl+Y call `window._htRequestRedo`
  - no remaining references to `_htUndoStack = null` or single-entry restore code

- `tests/unit/test_ui_canvas.py`
  - `canvas_js_helpers.py` no longer posts/deletes published edges directly
  - `canvas_events.py` no longer deletes published devices directly
  - `canvas_draft_events.py` routes remove-from-view through the local undo helper
  - drag gesture code exists in `dragstart`/`dragend`, not `dragfree`

### 11.2 Integration tests

- `tests/integration/test_canvas_undo_api.py`
  - contributor can call `POST /api/devices/{id}/canvas-delete` and receives a non-empty snapshot
  - reader receives 403 on both new routes
  - restore recreates the device row with the same ID and restores deleted connections
  - restore updates diagram versions for affected layouts
  - restore returns 409 if the device ID already exists
  - delete still returns 400 when the device has children

- Extend `tests/integration/test_device_deletion.py`
  - verify the canvas-delete path captures placements before deletion
  - verify diagram versions increment when canvas-delete mutates layouts

Fixtures to reuse: `client`, `session`, `contributor_token`, `reader_token`, `two_devices`.

### 11.3 Page-execution coverage

- `tests/unit/test_topology_undo_bar_execution.py`
  - editors get disabled Undo/Redo buttons with stable DOM IDs
  - readers do not get the buttons
  - button clicks call the correct JS entrypoints

- `tests/unit/test_device_detail_panel_execution.py`
  - a successful name/status change calls the stack-aware save path and refreshes the panel
  - unchanged values do not push stack entries

- `tests/unit/test_connection_detail_panel_execution.py`
  - Delete in the connection panel goes through the stack-aware path and closes the panel only on success

### 11.4 Browser proof

- `tests/e2e/test_topology_canvas_undo_redo.py`
  - move node, undo, redo via keyboard
  - create published edge, undo, redo
  - remove from view, undo via toolbar
  - delete published device, undo, redo
  - rename device in detail panel, undo

This is the only test layer that proves the mixed stack behaves correctly across real keyboard events, toolbar clicks, and canvas rendering.

## 12. Critical Path

1. Add the backend snapshot/restore contract first: `src/models/canvas_undo.py`, `src/domain/devices.py`, `src/services/canvas_undo_service.py`, and the two new device sub-routes.
2. Add the client stack manager and toolbar next: `canvas_undo.py`, `topology_undo_bar.py`, and the topology-page wiring.
3. Rewire action producers in this order: move batching, published edge create/delete, published node delete, remove-from-view, draft delete.
4. Rewire the device detail panel and the connection detail delete button to use the shared stack-aware path.
5. Add unit tests before browser proof; finish with the e2e file because that is where cross-surface regressions will show.

## 13. Implementation Plan: RFC-HT-032 Canvas Undo/Redo

### 1. Data model

- `src/models/canvas_undo.py` — add `DiagramVersionRef`, `DiagramPlacementSnapshot`, `PublishedConnectionSnapshot`, `PublishedDeviceSnapshot`, `PublishedDeviceDeleteSnapshot`, `PublishedDeviceCanvasDeleteResult`, `PublishedDeviceCanvasRestoreResult`.
- `src/models/device.py` — none, existing `DeviceResponse`/`DeviceUpdate` already cover the PATCH-backed device-field path.
- `src/models/connection.py` — none, existing `ConnectionCreate`/`ConnectionResponse` already cover published edge create/delete.

### 2. Migration

- none — no schema change.
- Backfill strategy: none.
- Rollback path: none.
- Online-safe? yes, because the database schema is unchanged.

### 3. Repository

- none — existing repositories are sufficient.
- Reuse `device_repository.get_by_id/create/delete/count_children`.
- Reuse `connection_repository.get_by_device/create/delete_by_device`.
- Reuse `diagram_repository.get_all_layouts/get_by_id_for_update/update`.
- Repositories still `flush()`, never `commit()`.

### 4. Domain (pure)

- `src/domain/devices.py` — add `extract_device_view_snapshot(...) -> tuple[dict[str, object] | None, bool]`.
- `src/domain/devices.py` — add `restore_device_to_cytoscape_json(...) -> tuple[dict[str, object], bool]`.
- `src/domain/devices.py` — modify `filter_device_from_cytoscape_json(...)` to strip `collapsedNodes` membership and preserve both supported element container shapes.

### 5. Service

- `src/services/canvas_undo_service.py` — add `delete_published_device_for_canvas(...) -> PublishedDeviceCanvasDeleteResult`.
- `src/services/canvas_undo_service.py` — add `restore_published_device_for_canvas(...) -> PublishedDeviceCanvasRestoreResult`.
- Errors:
  - missing device -> `HTTPException(404, "Device not found")`
  - child device present -> reuse existing 400
  - restore device ID conflict -> `HTTPException(409, ...)`
  - missing diagram during restore -> `HTTPException(409, ...)`
  - integrity failures when restoring connections -> `HTTPException(409, ...)`

### 6. API routes

- `src/api/routers/device_sub_routes.py` — add endpoints:

| Method | Path | response_model | Required role |
|---|---|---|---|
| `POST` | `/api/devices/{device_id}/canvas-delete` | `PublishedDeviceCanvasDeleteResult` | `Contributor` |
| `POST` | `/api/devices/{device_id}/restore` | `PublishedDeviceCanvasRestoreResult` | `Contributor` |

- Existing routes reused by UI undo handlers:

| Method | Path | response_model | Required role |
|---|---|---|---|
| `POST` | `/api/connections/` | `ConnectionResponse` | `Contributor` |
| `DELETE` | `/api/connections/{connection_id}` | `204 No Content` | `Contributor` |
| `PATCH` | `/api/devices/{device_id}` | `DeviceResponse` | `Contributor` |

### 7. UI

- `src/ui/components/canvas_undo.py` — add stack state, local action replay, busy-lock, toolbar state broadcast.
- `src/ui/components/canvas_undo.py` — gate published device delete/restore until autosave settles.
- `src/ui/components/canvas_undo_handlers.py` — add Python action handlers for API-backed forward/undo/redo requests.
- `src/ui/components/topology_undo_bar.py` — add Undo/Redo toolbar buttons.
- `src/ui/components/canvas.py` — inject the undo module.
- `src/ui/components/canvas_shortcuts.py` — replace the single-entry Ctrl+Z logic with stack requests; add redo shortcuts.
- `src/ui/components/canvas_js_interactions.py` — capture moves on `dragstart`/`dragend`.
- `src/ui/components/canvas_js_helpers.py` — published edge create/delete becomes request emission instead of direct fetch.
- `src/ui/components/canvas_events.py` — published device delete becomes request emission instead of direct fetch.
- `src/ui/components/canvas_draft_events.py` — remove-from-view becomes a local undoable action.
- `src/ui/components/device_panel_helpers.py` — accept injected save callback.
- `src/ui/components/device_detail_panel.py` — route device field/status updates through the undo-aware save callback.
- `src/ui/components/connection_detail_panel.py` — route Delete through the undo-aware edge-delete path.
- `src/ui/pages/topology.py` — render the undo bar, register handlers, clear stack on `pagehide`.
- Canvas changes? yes — see the canvas-bridge skill. The JS files that change are `canvas_undo.py`, `canvas_shortcuts.py`, `canvas_js_interactions.py`, `canvas_js_helpers.py`, `canvas_events.py`, and `canvas_draft_events.py`.

### 8. Tests (Test-Automation-Engineer)

- `tests/unit/test_domain_devices.py` — pure layout extraction/removal/restore cases and collapsed-state boundaries.
- `tests/unit/test_canvas_undo.py` — stack semantics, cap, busy-lock, redo-clear rules.
- `tests/unit/test_canvas_shortcuts.py` — keyboard wiring.
- `tests/unit/test_ui_canvas.py` — JS producer contract assertions.
- `tests/unit/test_topology_undo_bar_execution.py` — page-execution toolbar wiring.
- `tests/unit/test_device_detail_panel_execution.py` — page-execution PATCH-backed undo registration.
- `tests/unit/test_connection_detail_panel_execution.py` — page-execution edge delete path.
- `tests/integration/test_canvas_undo_api.py` — new API route happy path, RBAC negative path, 409 restore conflict.
- `tests/e2e/test_topology_canvas_undo_redo.py` — mixed keyboard + toolbar + canvas interaction proof.
- New fixture? none — existing fixtures are sufficient.

### 9. Docs

- `CHANGELOG.md` — add an `[Unreleased]` entry when code lands.
- `doc/tracker.md` — mark `T-001` resolved after HT-032 ships.

### 10. Verification

- `bash .github/skills/verify-gate/scripts/run.sh --fast`
- `docker compose exec api pytest tests/unit/test_canvas_undo.py tests/integration/test_canvas_undo_api.py -v`
- `docker compose exec api pytest tests/e2e/test_topology_canvas_undo_redo.py -v` if the browser harness is part of the pipeline

### Risks / open questions for Architect

- none — the route split, action taxonomy, and out-of-scope actions are fixed by this RFC. Feature-Engineer should not re-decide them.