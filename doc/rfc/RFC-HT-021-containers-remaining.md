# RFC: HT-021 Device Containers — Remaining Work

**Story:** HT-021 · **Status:** Draft · **Date:** 2026-04-12

Covers the five unfinished work units. Backend model/domain/repo/service layers are complete.

---

## 1. API Enrichment

**File:** `src/services/device_service.py` — `get_by_id_enriched()`

Add two `include` branches after the existing `"services"` block:

```python
if "children" in include:
    children = device_repository.get_children(session, device_id)
    enriched.children = [DeviceResponse.model_validate(c.model_dump()) for c in children]
if "ancestors" in include:
    enriched.parent_chain = _load_parent_chain(device_id, session)
```

`_load_parent_chain` already exists in the service (added during Phase 1). It walks `parent_id` upward and returns `list[DeviceResponse]` nearest→root.

**File:** `src/api/routers/devices.py` — `get_device()`

No router changes needed — the handler already forwards `include_set` to `get_by_id_enriched`. Clients pass `?include=children` or `?include=ancestors` (comma-combinable with existing `tags,location,custom_fields,services`).

---

## 2. Canvas Rendering — Topology Data

**File:** `src/ui/services/topology_data.py` — `load_canvas_data()`

In the device→element loop, emit `data.parent` when `parent_id` is present:

```python
node_data = { "id": device_id, "label": ..., ... }
raw_parent = device.get("parent_id")
if raw_parent is not None:
    node_data["parent"] = str(raw_parent)
```

Cytoscape.js reads `data.parent` natively to create compound nodes — no plugin required.

**File:** `src/ui/components/canvas_styles.py` — `build_theme_style_json()`

Append compound-node selector rules to the style array:

```js
{ selector: ':parent',          // any node that has children
  style: {
    'shape': 'roundrectangle',
    'background-opacity': 0.12,
    'border-width': 2,
    'border-style': 'dashed',
    'padding': '24px',
    'text-valign': 'top',
    'text-halign': 'center'
  }
}
```

Use the theme's `surface` colour for border and a `0.12` opacity fill from the device-type colour. Keep the node label at the top.

---

## 3. Canvas Interaction

### 3a. Context Menu — "Convert to Container"

**File:** `src/ui/components/canvas_events.py`

Add handler for `ht:node-convert-container` custom event. On trigger:
1. The node already has `data.parent = undefined` and no children — visually it is unchanged.
2. Dispatch a no-op `PATCH /api/devices/{id}` with empty body (pure UI hint).
3. Set a transient `data._isContainer = true` class so the compound style applies even with zero children.

Actually, Cytoscape compound style (`:parent`) only activates when the node has child nodes. For zero-child containers, add a CSS class `container` on demand and a matching selector:

```js
{ selector: 'node.container', style: { /* same as :parent */ } }
```

The class is added via `node.addClass('container')` on "Convert to Container" and removed when the last child is dragged out.

### 3b. Drag-Reparent

**File:** `src/ui/components/canvas_events.py`

Listen to Cytoscape `free` event (node drag end). On `free`:
1. Get the dropped position via `node.position()`.
2. For every compound node (`:parent` or `.container`), check `compoundNode.boundingBox()` containment.
3. If inside a compound and node is not already a child: `PATCH /api/devices/{id}` with `{ parent_id: compoundId }`. On 200, call `node.move({ parent: compoundId })`.
4. If the node was a child but dropped outside its parent's bounding box: `PATCH` with `{ parent_id: null }`. On 200, call `node.move({ parent: null })`.
5. Ignore if the node is dropped onto itself or onto a descendant (server rejects cycles, but skip the round-trip).

### 3c. Collapse / Expand Toggle

**File:** `src/ui/components/canvas_events.py`

Add handler for `ht:node-collapse-toggle`:
1. **Collapse:** Hide all descendant nodes/edges. Replace compound with a single node showing the device icon + a badge `(N)` where N = direct child count. Store `data._collapsed = true`.
2. **Expand:** Restore children visibility. Remove badge. Set `data._collapsed = false`.
3. Connections incident on hidden children re-route to the collapsed parent (via Cytoscape `display: none` on children — edges auto-collapse to the nearest visible ancestor).

Collapse state persists in `DiagramLayout.cytoscape_json` under `collapsedNodes: [id, ...]`. `topology_data.py` reads this on load and applies collapse.

---

## 4. Detail Panel

**File:** `src/ui/components/device_detail_panel.py`

### 4a. Children Section

In `_refresh()`, after fetching the device, if the response has `children` (non-empty):
- Render a "Children ({n})" section with each child as a clickable row (icon + name).
- Clicking a child dispatches `ht:panel-select` with the child's ID to focus on it.

Fetch: `GET /api/devices/{id}?include=children` (append to the existing include set in `_api_get_device`).

### 4b. Parent Breadcrumb

If `device.parent_id` is set:
- Fetch ancestors: `GET /api/devices/{id}?include=ancestors`.
- Render "Inside: grandparent → parent" as clickable breadcrumb links above the device name.
- Each crumb dispatches `ht:panel-select` with that ancestor's ID.

---

## 5. Export / Import Round-Trip

### 5a. Export Schema

**File:** `src/models/export_schema.py` — `ExportedDevice`

Add field:
```python
parent_id: Optional[uuid.UUID] = None
```

No other schema changes. `ExportSchema` already contains `ExportedDevice` — the new field propagates automatically via `model_dump()`.

### 5b. Export Service

**File:** `src/services/export_service.py` — `build_full_export()`

No code change — `device.model_dump()` already includes `parent_id` once the schema field exists.

### 5c. Import Service

**File:** `src/services/import_service.py`

**Validation** — add `_validate_device_parent_refs(payload)` (mirrors `_validate_device_location_refs`): every `device.parent_id` must reference another device ID within the payload or be `None`.

**Ordering** — devices with `parent_id` references require parents to be inserted first. Add `topological_sort_devices()` to `src/domain/export.py` (clone `topological_sort_locations` logic — roots first, then children). Replace the `for d in payload.devices` loop with `for d in topological_sort_devices(payload.devices)`.

**Device constructor** — pass `parent_id=d.parent_id` in the `Device(...)` call inside the import loop.

---

## Files to Create/Modify

| File | Change |
|---|---|
| `src/services/device_service.py` | `children` + `ancestors` branches in `get_by_id_enriched` |
| `src/ui/services/topology_data.py` | Emit `data.parent` on node elements |
| `src/ui/components/canvas_styles.py` | `:parent` + `.container` compound-node styles |
| `src/ui/components/canvas_events.py` | Drag-reparent, collapse/expand, convert-to-container |
| `src/ui/components/device_detail_panel.py` | Children section + parent breadcrumb |
| `src/models/export_schema.py` | `parent_id` on `ExportedDevice` |
| `src/domain/export.py` | `topological_sort_devices()` |
| `src/services/import_service.py` | Parent-ref validation + topo-sort + pass `parent_id` |

## Validation

| Test file | Covers |
|---|---|
| `tests/unit/test_devices.py` | `topological_sort_devices`, domain cycle detection (existing) |
| `tests/unit/test_export.py` | Round-trip with `parent_id` present |
| `tests/integration/test_device_api.py` | `?include=children`, `?include=ancestors` |
| `tests/integration/test_import_export.py` | Import ordering, parent-ref validation |
