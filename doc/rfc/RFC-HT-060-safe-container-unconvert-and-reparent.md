# RFC: Safe Container Unconvert and Reparent Server Coordination

**Story:** HT-060 · **Status:** Draft · **Date:** 2026-04-13
**Author:** Architect

---

## 1. Overview

HT-060 closes two container-integrity bugs in the topology canvas without widening the destructive surface of the product. Reparent remains an inventory mutation on the existing Device resource and must stop doing a GET-then-PATCH race; unconvert remains a View mutation and must stop mutating Cytoscape before the server accepts the change.

**Decision:** HT-060 preserves HT-046, not supersedes it. Converting a container back to a plain node does **not** delete inventory devices or database connections. It removes the container's descendant subtree and affected edges from the current View's server-stored `diagram_layouts.cytoscape_json`, exactly as HT-046 intended, but now does so through an explicit, versioned server write before any DOM mutation.

**Why HT-046 is preserved:**
- `Device` is global inventory, not View-local state. Deleting children because one View changed its container representation would destroy inventory data shared across all Views and workspaces.
- Existing `device_service.delete()` is intentionally global and already cascades connection cleanup plus removal from **all** Views. Reusing that path for unconvert would turn a canvas-only undo into a cross-view destructive delete.
- The BUG-TOPO-007 report explicitly allows a safe, server-coordinated layout mutation instead of inventory deletion. That is the smallest correct fix.

**Story-contract reconciliation:**
- HT-060's acceptance bullet that says devices and edges are "permanently deleted from the server" is architecturally incorrect for Hometower's current model and conflicts with shipped HT-046.
- The canonical implementation contract is revised to: the confirmation modal previews which devices and edges will be removed from the **current View's server-stored layout**. The modal must explicitly say those devices stay in inventory.

---

## 2. Open Questions Resolved

1. **Unconvert deletion scope:** Recursive descendants.
   The operation removes the full descendant subtree from the current View, not just direct children. Direct-child-only removal would leave grandchildren orphaned or force a silent reparenting rule that HT-046 explicitly rejected.

2. **Reparent endpoint:** Reuse existing `PATCH /api/devices/{id}`.
   `parent_id` is already part of the Device update contract, optimistic locking already exists there, and adding a parent-only endpoint would duplicate the same transaction boundary with more surface area and no safety gain.

3. **Unconvert server call sequence:** Single versioned `PATCH /api/diagrams/{id}` carrying the post-unconvert `cytoscape_json`.
   Do **not** issue per-child DELETE/PATCH calls. Do **not** introduce inventory-deletion cascade semantics. The diagram PATCH is the single transactional backend coordination point for this View-only mutation.

---

## 3. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/ui/components/canvas_container_events.py` | The retry, preview, and rollback policy for container-specific canvas interactions. |
| `src/ui/services/topology_data.py` | Which inventory fields are copied into published Cytoscape node data for later client-side optimistic writes. |
| `src/ui/components/stencils_panel_js.py` | The drag/drop payload contract between the inventory stencil list and the canvas. |
| `src/ui/components/canvas_draft_publish.py` | How a published draft node inherits authoritative server metadata after replacement. |
| `src/ui/components/canvas_events.py` | How published-node create/duplicate flows seed canvas node metadata from API responses. |

No new backend module is introduced. Existing backend modules already hide the relevant changeable decisions:
- `src/services/device_service.py` hides device optimistic-lock transaction semantics.
- `src/services/diagram_service.py` hides diagram optimistic-lock transaction semantics.

---

## 4. Decision Summary

### 4.1 HT-046 preserved

`Convert to Node` remains a safe, server-coordinated **remove-from-View** operation.

Resulting product contract:
- Inventory devices remain in `devices`.
- Inventory connections remain in `connections`.
- Other Views remain unchanged.
- Only the current `diagram_layouts` row changes.

### 4.2 Reparent stays on Device PATCH

Reparent is still a Device containment mutation because `parent_id` is inventory truth and already drives the canvas hierarchy during data load.

### 4.3 No new API surface

HT-060 reuses:
- `PATCH /api/devices/{id}` for published-node reparent.
- `PATCH /api/diagrams/{id}` for View-local unconvert.

No new schema, migration, repository, or service method is required.

**DevOps-Engineer required:** No.
Reason: no migration, no infrastructure change, no schema change.

---

## 5. Data Model Changes

None.

HT-060 does **not** add or change SQLModel fields, enums, or Alembic migrations.

**DevOps-Engineer migration review required:** No.

---

## 6. Domain Logic

None.

HT-060 does not add a new pure-domain rule. It relies on already-shipped rules:
- `Device.parent_id` remains the inventory containment source of truth.
- `device_service.update()` already rejects stale versions with HTTP 409.
- `diagram_service.partial_update()` already rejects stale layout versions with HTTP 409.

---

## 7. Service Layer

No new service methods.

### 7.1 Reused device transaction boundary

Reparent uses the existing service unchanged:

```python
def update(device_id: uuid.UUID, data: DeviceUpdate, session: Session) -> Device:
    device = device_repository.get_by_id(session, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    expected_version = update_data.pop("version")
    if expected_version != device.version:
        raise HTTPException(
            status_code=409,
            detail="Conflict: device was modified by another request",
        )

    ...
    result = device_repository.update(session, device)
    session.commit()
```

**Transaction semantics:**
- Each reparent attempt is one `Device` row update.
- A version mismatch fails before commit.
- Client retries are safe because each retry uses a newly fetched server version.

### 7.2 Reused diagram transaction boundary

Unconvert uses the existing diagram partial update unchanged:

```python
def partial_update(
    layout_id: uuid.UUID,
    data: DiagramLayoutUpdate,
    owner_id: uuid.UUID,
    session: Session,
) -> DiagramLayout:
    layout = diagram_repository.get_by_id_for_update(session, layout_id)
    ...
    if data.version != layout.version:
        raise HTTPException(
            status_code=409,
            detail="Conflict: diagram was modified by another request",
        )
    if data.cytoscape_json is not None:
        layout.cytoscape_json = data.cytoscape_json
    layout.version += 1
    result = diagram_repository.update(session, layout)
    session.commit()
```

**Transaction semantics:**
- The entire View mutation is one row write to `diagram_layouts`.
- No child-by-child partial success is possible.
- Client rollback is trivial: if PATCH fails, do not mutate Cytoscape.

---

## 8. API Layer

### 8.1 Reparent API

**Use as-is:** `PATCH /api/devices/{device_id}`

**Required role:** `Contributor` (already enforced)

**Request body:**

```json
{
  "parent_id": "<uuid-or-null>",
  "version": 7
}
```

**Success path:**
- `200 OK`
- response body is full `DeviceResponse`
- client must copy `response.version` into `node.data('version')`

**Conflict path:**
- `409 Conflict`
- detail remains `Conflict: device was modified by another request`
- client retries up to 3 times, re-fetching latest device before each retry

### 8.2 Unconvert API

**Use as-is:** `PATCH /api/diagrams/{diagram_id}`

**Required role:** `Contributor` (already enforced)

**Request body:**

```json
{
  "cytoscape_json": { "elements": [...], "zoom": 1.0, "pan": { "x": 0, "y": 0 }, "collapsedNodes": [] },
  "version": 12
}
```

**Success path:**
- `200 OK`
- response body is full `DiagramLayoutResponse`
- client must set `window._htDiagramVersion = response.version`
- only after that may the DOM be mutated to match the already-sent JSON

**Conflict path:**
- `409 Conflict`
- detail remains `Conflict: diagram was modified by another request`
- no client retry for HT-060; user gets toast and unchanged canvas

### 8.3 No new endpoint

Rejected alternatives:
- `PATCH /api/devices/{id}/parent`: duplicates existing device PATCH semantics.
- `DELETE /api/devices/{id}?cascade=true`: violates HT-046, widens destructive scope, and would delete inventory.
- `POST /api/diagrams/{id}/unconvert-container`: redundant with existing versioned diagram PATCH.

---

## 9. UI Layer

### 9.1 Reparent UX contract

**Trigger:** drag published node onto a new container or out to top level.

**Behavior:**
- No initial GET.
- First attempt uses `node.data('version')` already present on the canvas node.
- On HTTP 409 only:
  1. GET latest `DeviceResponse`.
  2. If server `parent_id` already equals the user's target parent, treat as success and update local `version`.
  3. Otherwise retry PATCH with the refreshed `version`.
  4. Maximum 3 PATCH attempts total.
- If all retries fail with 409:
  - animate node back to its pre-drag position over 200ms ease-out
  - keep original parent relationship
  - show toast: `Reparent failed — the device was modified by another user. Your change was not saved.`
- If a non-409 response or network error occurs:
  - animate node back to its pre-drag position
  - show generic toast: `Reparent failed — your change was not saved.`

**Draft-node compatibility:**
- Draft nodes never call `/api/devices/{id}`.
- If the dragged node ID is draft-shaped, reparent stays layout-local: `node.move({ parent: newParent })` and normal autosave handles persistence.

### 9.2 Unconvert UX contract

**Title:** `Convert container to node?`

**Body rules:**
- First line: `Devices stay in inventory. This removes them from this View.`
- List up to 5 direct child names.
- If more than 5 direct children: show `+N more direct children`.
- If nested descendants exist: show `Includes X nested descendants under those children.`
- Show affected edge count as `Y connections will be removed from this View.`

**Buttons:**
- `Cancel` — default focus, Escape closes.
- `Remove from View` — warning/destructive styling, but copy must not say delete inventory devices.

**Success toast:** `Container converted to node.`

**Failure toast:** `Convert to node failed — this View was not changed.`

### 9.3 Unconvert server sequencing

The client must build a candidate layout JSON in memory, not mutate Cytoscape first.

Sequence:
1. Resolve container node.
2. Compute removal set = all recursive descendants.
3. Compute preview = direct child names + descendant count + affected edge count.
4. Show confirmation dialog.
5. On confirm, guard:
   - if `window._htDiagramId` or `window._htDiagramVersion` is missing, show `Save this View before converting containers.` and abort.
   - if `window._htAutosaveInFlight` or `window._htAutosaveRequestInFlight`, show `Save in progress — wait a moment and try again.` and abort.
6. Call `window.cancelAutosave()` to clear a pending timer.
7. Build `candidateJson = getCanvasJson()` clone with:
   - descendant nodes removed
   - edges touching removed nodes removed
   - container node stripped of `container`, `collapsed`, and `_collapsed`
   - target node removed from `collapsedNodes`
8. PATCH `/api/diagrams/{diagramId}` with `candidateJson` and current layout version.
9. If response is `200`, set `window._htDiagramVersion` from response and only then apply the same mutation to the live canvas.
10. Dispatch `ht:stencil-refresh` after success so removed published devices return to the stencil panel.
11. Do **not** schedule a second autosave for this already-persisted mutation.

### 9.4 Exact file impacts

#### `src/ui/components/canvas_container_events.py`

This is the primary HT-060 file.

**Before:**

```javascript
fetch('/api/devices/' + nodeId, { credentials: 'include' })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(device) {
        if (!device) { return null; }
        patchBody.version = device.version;
        return fetch('/api/devices/' + nodeId, {
            method: 'PATCH',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(patchBody)
        });
    })
```

```javascript
function doUnconvert() {
    descendants.connectedEdges().remove();
    descendants.remove();
    node.removeClass('container');
    node.removeClass('collapsed');
    node.removeData('_collapsed');
    if (window.scheduleAutosave) window.scheduleAutosave(800);
}
```

**After:**

```javascript
cy.on('grab', 'node', function(evt) {
    var node = evt.target;
    window._htContainerDragOrigin = window._htContainerDragOrigin || {};
    window._htContainerDragOrigin[node.id()] = {
        parentId: node.data('parent') || null,
        position: { x: node.position().x, y: node.position().y }
    };
});

cy.on('dragfree', 'node', function(evt) {
    if (window.HT_READONLY) return;
    var node = evt.target;
    var nodeId = node.id();
    var targetParent = _htResolveDropParent(node);

    if (window._htIsDraft && window._htIsDraft(nodeId)) {
        node.move({ parent: targetParent });
        if (window.scheduleAutosave) window.scheduleAutosave(800);
        return;
    }

    var knownVersion = node.data('version');
    _htAttemptReparent(node, targetParent, knownVersion, 0);
});
```

```javascript
document.addEventListener('ht:node-unconvert-container', function(evt) {
    var plan = _htBuildUnconvertPlan(evt.detail.id);
    if (!plan) return;
    _htShowUnconvertDialog(plan, function onConfirm() {
        if (!window._htDiagramId || window._htDiagramVersion == null) {
            _notify('Save this View before converting containers.', 'warning');
            return;
        }
        if (window._htAutosaveInFlight || window._htAutosaveRequestInFlight) {
            _notify('Save in progress — wait a moment and try again.', 'warning');
            return;
        }
        if (window.cancelAutosave) window.cancelAutosave();
        fetch('/api/diagrams/' + window._htDiagramId, {
            method: 'PATCH',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cytoscape_json: plan.candidateJson,
                version: window._htDiagramVersion
            })
        }).then(function(r) {
            if (!r.ok) throw r;
            return r.json();
        }).then(function(layout) {
            window._htDiagramVersion = layout.version;
            _htApplyUnconvertPlan(plan);
            document.dispatchEvent(new CustomEvent('ht:stencil-refresh'));
            _notify('Container converted to node.', 'positive');
        }).catch(function() {
            _notify('Convert to node failed — this View was not changed.', 'negative');
        });
    });
});
```

#### `src/ui/services/topology_data.py`

Add device version to published node data.

**Before:**

```python
device_elem_data: dict[str, object] = {
    "id": device_id,
    "label": html.escape(device_name),
    "raw_name": device_name,
    "shape": shape,
    "device_type": html.escape(device_type),
    "raw_device_type": device_type,
    "status": html.escape(_safe_text(device.get("status", "Active"))),
```

**After:**

```python
device_elem_data: dict[str, object] = {
    "id": device_id,
    "label": html.escape(device_name),
    "raw_name": device_name,
    "shape": shape,
    "device_type": html.escape(device_type),
    "raw_device_type": device_type,
    "version": int(device.get("version", 1)),
    "status": html.escape(_safe_text(device.get("status", "Active"))),
```

#### `src/ui/pages/topology.py`

Preserve version when building stencil device payloads.

**Before:**

```python
devices.append({
    "id": str(item.get("id", "")),
    "name": str(item.get("name", "")),
    "type": str(item.get("type", "")),
    "ip": str(item.get("ip", "") or ""),
})
```

**After:**

```python
devices.append({
    "id": str(item.get("id", "")),
    "name": str(item.get("name", "")),
    "type": str(item.get("type", "")),
    "ip": str(item.get("ip", "") or ""),
    "version": int(item.get("version", 1)),
})
```

#### `src/ui/components/stencils_panel.py` and `src/ui/components/stencils_panel_js.py`

Carry version through drag/drop.

**Before:**

```javascript
function htStencilCardDrag(el, deviceId, deviceName, deviceType, deviceIp) {
    e.dataTransfer.setData('inventoryDeviceId', deviceId);
    e.dataTransfer.setData('inventoryDeviceName', deviceName);
    e.dataTransfer.setData('inventoryDeviceType', deviceType);
    e.dataTransfer.setData('inventoryDeviceIp', deviceIp || '');
}
```

```javascript
window._cy.add({
    data: {
        id: deviceId,
        label: _escapeHtml(deviceName),
        raw_name: deviceName,
        ...
    }
});
```

**After:**

```javascript
function htStencilCardDrag(el, deviceId, deviceName, deviceType, deviceIp, deviceVersion) {
    e.dataTransfer.setData('inventoryDeviceVersion', String(deviceVersion || 1));
}
```

```javascript
var deviceVersion = Number(d.deviceVersion || 1);
window._cy.add({
    data: {
        id: deviceId,
        label: _escapeHtml(deviceName),
        raw_name: deviceName,
        version: deviceVersion,
        ...
    }
});
```

#### `src/ui/components/canvas_events.py`

Duplicate flow must seed the new node's version.

**Before:**

```javascript
data: {
    id: String(device.id),
    label: escapedName,
    raw_name: rawName,
    shape: deviceShapes[device.type] || 'rectangle',
```

**After:**

```javascript
data: {
    id: String(device.id),
    label: escapedName,
    raw_name: rawName,
    version: Number(device.version || 1),
    shape: deviceShapes[device.type] || 'rectangle',
```

#### `src/ui/components/canvas_draft_publish.py`

Published draft replacement node must seed the authoritative version.

**Before:**

```javascript
var newData = {
    id: newId,
    label: window._htEscapeHtml(device.name || ''),
    raw_name: device.name || '',
```

**After:**

```javascript
var newData = {
    id: newId,
    label: window._htEscapeHtml(device.name || ''),
    raw_name: device.name || '',
    version: Number(device.version || 1),
```

### 9.5 Files intentionally unchanged

- `src/api/routers/devices.py`
- `src/api/routers/diagrams.py`
- `src/services/device_service.py`
- `src/services/diagram_service.py`
- `src/repositories/device_repository.py`
- `src/repositories/diagram_repository.py`

These existing layers already provide the correct transaction and optimistic-lock semantics. HT-060 is about using them correctly from the canvas.

---

## 10. Security Boundaries

- Reparent continues to rely on existing `Contributor` RBAC at `PATCH /api/devices/{id}`.
- Unconvert continues to rely on existing `Contributor` RBAC at `PATCH /api/diagrams/{id}`.
- `HT_READONLY` remains a UX hint only; the server remains authoritative.
- No new secrets or credentials cross module boundaries.
- No new logging is required. Existing device and diagram update logs are sufficient.
- The unconvert modal must explicitly say devices remain in inventory to prevent destructive-user-misunderstanding risk.

---

## 11. Edge Cases

1. **Empty state**
   - Empty container: no confirmation list required; still use the same versioned diagram PATCH, just with zero descendants and zero edges.
   - No saved layout ID/version: block unconvert and show `Save this View before converting containers.`

2. **Boundary values**
   - Direct-child preview lists max 5 names, then `+N more direct children`.
   - Edge count may be zero and must still render as `0 connections will be removed from this View.`
   - Recursive descendant count may exceed direct child count and must be shown separately.

3. **Concurrent access**
   - Reparent: 3 PATCH attempts max, refreshing device version before attempts 2 and 3.
   - Unconvert: one diagram PATCH only; on 409, no DOM mutation and conflict toast.

4. **Cascade effects**
   - Reparent changes only `devices.parent_id`.
   - Unconvert removes descendant nodes and connected edges from the current View only.
   - Inventory devices, inventory connections, and other Views are unaffected.

5. **RBAC per operation**
   - Readers remain view-only and never see effective write behavior.
   - Contributors/Admins can reparent and unconvert only through edit mode and existing API role gates.

6. **Round-trip integrity**
   - A successful unconvert updates the server-stored `cytoscape_json`; reload of the same View must match the post-success canvas exactly.
   - Inventory export/import remains unchanged because inventory entities are untouched.

7. **Canvas impact**
   - Published nodes must carry `version` in their `data` payload from initial load, stencil placement, duplication, and draft publish.
   - Draft nodes remain layout-local and bypass device PATCH.

8. **Performance at scale**
   - Reparent remains one PATCH plus up to two retry GET+PATCH cycles.
   - Unconvert remains one diagram PATCH regardless of subtree size; preview computation is client-side graph traversal only.
   - No O(descendants) network fan-out is allowed.

---

## 12. Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `doc/rfc/RFC-HT-060-safe-container-unconvert-and-reparent.md` | CREATE | Implementation contract for HT-060 |
| `src/ui/components/canvas_container_events.py` | MODIFY | Remove GET-then-PATCH race; add 409 retry/snapback; make unconvert diagram-PATCH-first |
| `src/ui/services/topology_data.py` | MODIFY | Seed published node `version` in Cytoscape data |
| `src/ui/pages/topology.py` | MODIFY | Preserve `version` when building stencil inventory payloads |
| `src/ui/components/stencils_panel.py` | MODIFY | Widen stencil device payload shape to include version |
| `src/ui/components/stencils_panel_js.py` | MODIFY | Carry inventory device version through drag/drop and onto placed nodes |
| `src/ui/components/canvas_events.py` | MODIFY | Seed duplicated published nodes with server version |
| `src/ui/components/canvas_draft_publish.py` | MODIFY | Seed newly published nodes with server version |
| `tests/unit/test_topology_data.py` | MODIFY | Assert published node data includes version and merge logic does not overwrite it |
| `tests/unit/test_stencils_panel.py` | MODIFY | Assert version is carried in drag/drop payload and stored on placed nodes |
| `tests/unit/test_ui_canvas.py` | MODIFY | Assert container JS uses retry loop, no initial GET for published reparent, and unconvert patches diagrams before DOM mutation |
| `tests/integration/test_devices.py` | MODIFY | Assert stale device version still returns 409 for client retry contract reference |
| `tests/integration/test_diagrams_patch.py` | MODIFY | Assert stale diagram version still returns 409 for unconvert conflict path reference |
| `CHANGELOG.md` | MODIFY | Add `[Unreleased]` note for HT-060 when Feature-Engineer ships |

No repository, domain, service, router, or Alembic files are required for HT-060 implementation.

---

## 13. Test Plan

### 13.1 Unit tests

**`tests/unit/test_ui_canvas.py`**
- Assert `CANVAS_CONTAINER_EVENTS_JS` no longer contains the initial `fetch('/api/devices/' + nodeId, { credentials: 'include' })` preflight for published reparent.
- Assert a 3-attempt reparent retry path exists.
- Assert the final 409 toast string matches story copy exactly.
- Assert unconvert handler patches `/api/diagrams/` before `descendants.remove()` or `connectedEdges().remove()` appears in the success path.
- Assert unconvert no longer calls `window.scheduleAutosave(800);` after the explicit diagram PATCH success path.

**`tests/unit/test_topology_data.py`**
- Assert published node `data.version` is present after `load_canvas_data()`.
- Assert `merge_saved_layout()` still only applies position/classes and does not overwrite the API-loaded version.

**`tests/unit/test_stencils_panel.py`**
- Assert `inventoryDeviceVersion` is written in `STENCIL_DRAG_JS`.
- Assert `deviceVersion` is read in `STENCIL_DROP_HANDLER_JS` and stored as `data.version`.

### 13.2 Integration tests

**`tests/integration/test_devices.py`**
- Keep/extend stale-version PATCH case as the contract the client retries against.
- Add a regression note that `PATCH /api/devices/{id}` remains the reparent endpoint; no parent-only endpoint exists.

**`tests/integration/test_diagrams_patch.py`**
- Keep/extend stale-version PATCH case as the contract unconvert relies on.
- Add a case proving diagram PATCH accepts a pruned `cytoscape_json` and increments version once.

### 13.3 UI / browser tests

If Playwright coverage is added in the same implementation batch, include:
- Reparent 409 lane: second client bumps device version; first client drag-reparents; retries; final failure snaps back and shows conflict toast.
- Unconvert cancel lane: modal opens, cancel leaves DOM unchanged.
- Unconvert success lane: confirm triggers server PATCH first; descendants disappear only after success toast.

### 13.4 Fixtures

Reuse existing fixtures from `tests/conftest.py`:
- `client`
- `contributor_token`
- `reader_token`
- `session`

No new SQLModel registration is required.

---

## 14. Implementation Plan: RFC-HT-060 Safe Container Unconvert and Reparent Server Coordination

### 1. Data model
- none — HT-060 reuses existing `Device.version`, `Device.parent_id`, and `DiagramLayout.version`

### 2. Migration
- none — no schema change

### 3. Repository
- none — existing repositories already support the reused routes/services

### 4. Domain (pure)
- none — no new pure-function rule is required

### 5. Service
- `services/device_service.py` — none; reuse existing optimistic-lock update behavior
- `services/diagram_service.py` — none; reuse existing optimistic-lock partial update behavior

### 6. API routes
- `api/routers/devices.py` — none; continue using:
  | Method | Path | response_model | Required role |
  |---|---|---|---|
  | PATCH | `/api/devices/{id}` | `DeviceResponse` | Contributor |
- `api/routers/diagrams.py` — none; continue using:
  | Method | Path | response_model | Required role |
  |---|---|---|---|
  | PATCH | `/api/diagrams/{id}` | `DiagramLayoutResponse` | Contributor |

### 7. UI
- `ui/components/canvas_container_events.py` — add drag-origin capture, published-node retry logic, draft-node bypass, unconvert preview builder, explicit diagram PATCH-first flow, snapback animation
- `ui/services/topology_data.py` — add `version` to published node data
- `ui/pages/topology.py` — include `version` in stencil device payload bootstrap
- `ui/components/stencils_panel.py` — widen payload typing to carry version
- `ui/components/stencils_panel_js.py` — carry `inventoryDeviceVersion` through drag/drop
- `ui/components/canvas_events.py` — copy returned version into duplicated node data
- `ui/components/canvas_draft_publish.py` — copy returned version into published node data
- Canvas changes: follow `canvas-bridge` skill; DB remains source of truth and DOM mutation follows server confirmation

### 8. Tests
- `tests/unit/test_ui_canvas.py` — JS-bridge regression assertions for retry and diagram-PATCH-first flow
- `tests/unit/test_topology_data.py` — node version propagation
- `tests/unit/test_stencils_panel.py` — version drag/drop propagation
- `tests/integration/test_devices.py` — stale-version contract reference
- `tests/integration/test_diagrams_patch.py` — diagram stale-version and pruned-layout reference

### 9. Docs
- `CHANGELOG.md` — add `[Unreleased]` HT-060 entry at implementation time

### 10. Verification
- `.github/skills/verify-gate/scripts/run.sh --fast`

### Risks / open questions for Feature-Engineer
- none — this RFC resolves all story-level open questions and preserves HT-046 explicitly

---

## 15. Final Decision Record

- HT-046 is preserved.
- Unconvert scope is recursive descendants in the current View.
- Reparent uses existing `PATCH /api/devices/{id}`.
- Unconvert uses existing versioned `PATCH /api/diagrams/{id}`.
- No DevOps-Engineer review is required.
