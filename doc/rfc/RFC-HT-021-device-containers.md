# RFC: Device Containers (Nested Logical/Physical Grouping)

**Story:** HT-021
**Status:** Draft — awaiting Feature-Engineer + UX-Designer implementation
**Date:** 2026-04-11
**Author:** Architect

---

## 1. Overview

HT-021 promotes containment to a first-class concept for Device. Any existing device can become a parent of other devices via a nullable self-referential `parent_id` FK. The canvas renders containment as Cytoscape compound nodes — visually nested boxes that collapse/expand. The inventory list stays flat; clients build the tree from `parent_id`.

The data model reuses the exact pattern already proven in `Location` (`parent_id` FK + `domain/locations.detect_cycle` + `get_parent_map`). This RFC calls out every analog so Feature-Engineer can follow the template verbatim.

**Hidden design decisions (Parnas test):**
- `src/domain/devices.py` hides the cycle-detection algorithm — if we later swap iterative walk for a recursive CTE, only this file changes.
- `src/models/device.py` hides the FK shape — if we later add a `containment_type` column, only this file changes.
- `src/repositories/device_repository.py` hides the children/parent_map queries — if we later denormalize a closure table, only this file changes.
- `src/ui/components/canvas_js.py` + `canvas_events.py` hide the Cytoscape compound-node representation — if we swap the engine, only these files change.
- `cytoscape_json.nodes[].collapsed` hides the collapse state — backwards-compatible; missing key = expanded.

---

## 2. Data Model Changes

### 2.1 Modified file: `src/models/device.py`

Add `parent_id` to `DeviceBase` so it propagates to `DeviceCreate`, `DeviceResponse`, and the enriched responses. Add it **explicitly** to `DeviceUpdate` (which does not inherit `DeviceBase` — see BUG-1101-12 for the inheritance gap).

```
DeviceBase — add:
  parent_id: Optional[uuid.UUID] — Field(default=None, foreign_key="devices.id")

DeviceUpdate — add (explicit, not inherited):
  parent_id: Optional[uuid.UUID] = None
  — Presence semantics: omitted  = no change
                       null set  = clear parent (become top-level)
                       uuid set  = move into that container
  — Use `data.model_dump(exclude_unset=True)` in the service to distinguish
    "omitted" from "explicitly null" (already the pattern in update()).

DeviceResponseEnriched — add:
  parent_id: Optional[uuid.UUID] = None             ← always populated
  children:  list[DeviceResponse] = []              ← only when ?include=children
  parent_chain: list[DeviceResponse] = []           ← only when ?include=parent_chain
                                                      ordered nearest→root
```

**Rationale for `DeviceResponse` children type:** Children are returned as lightweight `DeviceResponse` (not `DeviceResponseEnriched`) to avoid recursive enrichment blowups. One level of nesting only; clients build deeper trees from the flat list endpoint.

**Rationale for `parent_chain`:** The detail panel needs a clickable breadcrumb chain ("Inside: pve-01 → Rack-01"). Returning the whole chain in one response avoids a sequence of N round-trips.

### 2.2 DB-level self-loop guard

Add a CHECK constraint `parent_id IS NULL OR parent_id <> id` on the `devices` table (mirrors `ck_connection_no_self_loop` from migration 019). Cycle detection beyond depth-1 is handled in the domain layer; the DB constraint is defense-in-depth for the direct self-loop case only.

---

## 3. Domain Layer

### 3.1 Modified file: `src/domain/devices.py`

Add one new pure function. Do **not** add any new imports beyond `uuid` — this file must remain stdlib-only.

**`detect_parent_cycle(device_id, new_parent_id, parent_map) -> bool`**

- Signature:
  ```
  detect_parent_cycle(
      device_id: uuid.UUID,
      new_parent_id: uuid.UUID,
      parent_map: dict[uuid.UUID, Optional[uuid.UUID]],
  ) -> bool
  ```
- Returns `True` if setting `new_parent_id` as parent of `device_id` creates a cycle.
- Algorithm is a **verbatim copy** of `src/domain/locations.py::detect_cycle`:
  1. If `new_parent_id == device_id` → return `True` (direct self-loop).
  2. Seed `visited = {device_id}`.
  3. Walk `current = new_parent_id` upward through `parent_map`. On each step: if `current in visited` → return `True`; add to `visited`; advance `current = parent_map.get(current)`.
  4. Walk terminates at `None` → return `False`.
- Visited tracking guards against pre-existing corrupt cycles (should be impossible given the service-layer guards, but defense-in-depth).
- **Depth safety net:** The `visited` set bounds the walk at the total number of devices (finite). No explicit depth cap is required, matching `locations.detect_cycle` exactly. The story suggests depth 10 as a safety net — we reject that because it would silently fail legitimate 11+ level hierarchies. The visited-set approach is strictly better.

**`validate_device_no_children(child_count: int) -> None`**

- Raise `ValueError("Device has child devices — remove or reassign them first")` if `child_count > 0`.
- Mirrors `validate_device_deletable(connection_count)`.
- Message text is taken verbatim from the HT-021 AC "Given I `DELETE /api/devices/{id}` on a device that has children…".

No change to `validate_ip`, `validate_mac`, `validate_device_deletable`, or `generate_copy_name`.

### 3.2 Cycle detection semantics for `create()`

On create, the new device has no ID yet. A cycle cannot exist because the new node has no incoming edges. The only check required at create time is **parent existence** (`_assert_parent_exists`). Cycle detection runs on `update()` when `parent_id` changes.

---

## 4. Repository Layer

### 4.1 Modified file: `src/repositories/device_repository.py`

Add three methods. All follow existing conventions in the file.

**`get_children(session, parent_id: uuid.UUID) -> list[Device]`**
- `SELECT * FROM devices WHERE parent_id = ? ORDER BY name`.
- Used by `device_service.get_by_id_enriched` when `"children"` is in `include`, and by `delete()` for the "has children" guard.
- Mirrors `location_repository.get_children`.

**`count_children(session, parent_id: uuid.UUID) -> int`**
- `SELECT COUNT(*) FROM devices WHERE parent_id = ?`.
- Used by `device_service.delete()` — cheaper than loading rows when we only need to know "does this device have children?".
- Mirrors `connection_repository.count_by_device`.

**`get_parent_map(session) -> dict[uuid.UUID, Optional[uuid.UUID]]`**
- `SELECT id, parent_id FROM devices`.
- Used by `device_service.update()` to pass to `detect_parent_cycle`.
- Mirrors `location_repository.get_parent_map` verbatim.

**Note on `get_all_with_location`:** No change. The existing LEFT JOIN does not need to also join parent devices — the flat list already carries `parent_id`, and clients build the tree client-side per the HT-021 AC "list endpoint … remains flat — tree-building is client-side".

---

## 5. Service Layer

### 5.1 Modified file: `src/services/device_service.py`

Add one helper and extend three existing methods.

**New helper: `_assert_parent_exists(parent_id, session) -> None`**
- Mirrors `_assert_location_exists` exactly.
- Raises `HTTPException(400, "Parent device not found")` if `device_repository.get_by_id(session, parent_id)` returns None.

**Modified: `create(data, session)`**
- After the existing `_assert_location_exists` call, if `data.parent_id is not None`, call `_assert_parent_exists(data.parent_id, session)`.
- Cycle detection is skipped on create (see §3.2).
- Pass `parent_id=data.parent_id` to the `Device(...)` constructor.

**Modified: `update(device_id, data, session)`**
- After the existing `_assert_location_exists` call, if `"parent_id" in update_data` (present in the exclude_unset dump) and the new value is non-null:
  1. Call `_assert_parent_exists(update_data["parent_id"], session)`.
  2. Load `parent_map = device_repository.get_parent_map(session)`.
  3. If `device_domain.detect_parent_cycle(device_id, update_data["parent_id"], parent_map)` returns True:
     - If `update_data["parent_id"] == device_id` → `HTTPException(400, "Device cannot be its own parent")` (matches AC wording).
     - Else → `HTTPException(400, "Circular containment detected")` (matches AC wording).
- If `"parent_id" in update_data` and the new value is `None`, skip cycle detection entirely (clearing the parent can never introduce a cycle).
- The existing `version` optimistic-lock check remains unchanged and runs before any parent-id work.
- The existing IntegrityError → 409 rollback path (`_raise_device_conflict`) remains unchanged.

**Modified: `delete(device_id, session)`**
- Before the existing `_count_device_connections` check, add:
  ```
  child_count = device_repository.count_children(session, device_id)
  try:
      device_domain.validate_device_no_children(child_count)
  except ValueError as exc:
      raise HTTPException(status_code=400, detail=str(exc)) from exc
  ```
- The existing connection-count guard runs after the child-count guard. Either failure returns a 400; the message text is preserved.

**Modified: `get_by_id_enriched(device_id, session, include)`**
- Add handling for two new `include` keys:
  - `"children"` → call `device_repository.get_children(session, device_id)`, map to `DeviceResponse`, assign to `enriched.children`.
  - `"parent_chain"` → walk parents iteratively using `device_repository.get_by_id`, depth-capped at 50 (defensive; cycle-free by invariant), return ordered nearest→root, assign to `enriched.parent_chain`.
- The walk helper lives in the service file, not the repository, because it is orchestration — the repository stays query-only.

### 5.2 Unchanged service methods

`get_by_id`, `get_all`, `get_all_enriched`, and the `_apply_collection_enrichment` batching helper are unchanged. The flat list endpoint already includes `parent_id` via the `DeviceResponseEnriched` field added in §2.1.

---

## 6. API Layer

### 6.1 Modified file: `src/api/routers/devices.py`

Three changes. No new endpoints — containment is a property of the existing Device resource.

**`POST /api/devices/`**
- `DeviceCreate` now carries `parent_id: Optional[uuid.UUID]` via the `DeviceBase` change in §2.1. No handler change needed — Pydantic deserializes automatically. The service layer validates.

**`PATCH /api/devices/{id}`**
- `DeviceUpdate` now carries `parent_id: Optional[uuid.UUID]`. No handler change needed. The service layer runs cycle detection.

**`GET /api/devices/{id}`**
- Expand the `include` parser to accept `"children"` and `"parent_chain"` (already a comma-separated set, so this is purely a service-layer pass-through).
- Update the router docstring to mention the new include keys.

**`DELETE /api/devices/{id}`**
- No handler change. The service layer now raises 400 on child-count > 0 (§5.1); the router already translates `HTTPException` naturally.

### 6.2 No new router file

HT-021 does not require a containers router. Rejecting that alternative keeps the Device resource coherent — "any device can be a container" is the whole point.

---

## 7. Migration Plan

### Migration 020 — `020_add_device_parent_id.py`

**Revises:** `019`

Three operations in a single migration (PostgreSQL applies them in one transaction):

1. **Add column** — `devices.parent_id UUID NULL` with FK to `devices.id ON DELETE RESTRICT`.
   - Rationale for RESTRICT: service-layer enforces "cannot delete if has children" and returns a friendly 400. The FK constraint is defense-in-depth; if a code path bypasses the service, the DB still refuses.
2. **Create index** — `ix_devices_parent_id` on `(parent_id)` — supports the `get_children` and `count_children` queries and the `get_parent_map` scan.
3. **Create CHECK constraint** — `ck_device_no_self_parent` as `parent_id IS NULL OR parent_id <> id` — mirrors `ck_connection_no_self_loop` (migration 019) verbatim.

**Alembic template:**

```python
def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_devices_parent_id",
        "devices",
        "devices",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_devices_parent_id", "devices", ["parent_id"])
    op.create_check_constraint(
        "ck_device_no_self_parent",
        "devices",
        "parent_id IS NULL OR parent_id <> id",
    )


def downgrade() -> None:
    op.drop_constraint("ck_device_no_self_parent", "devices", type_="check")
    op.drop_index("ix_devices_parent_id", table_name="devices")
    op.drop_constraint("fk_devices_parent_id", "devices", type_="foreignkey")
    op.drop_column("devices", "parent_id")
```

**Data migration:** None. Nullable column; all existing rows default to NULL (top-level).

**DevOps-Engineer migration review required** — new FK on a production table.

---

## 8. Canvas & UI Changes

### 8.1 Modified file: `src/ui/components/canvas_js.py`

**Compound node support.** Cytoscape compound nodes are native — a node becomes a compound parent when any other node has `data.parent = <id>`. The changes required:

1. **Element builder** — when emitting nodes to Cytoscape, include `data.parent` for every device whose DB record has `parent_id`. The existing `/api/diagrams/{id}` fetch already returns a flat Cytoscape JSON; add a synthesis step that walks the device list, matches `device.parent_id` to the parent node's `data.id`, and sets `data.parent` on the child.
2. **Container visual** — add a compound-node style rule (translucent fill, dashed border, padding). Colors use existing design tokens. Container "empty state" — a compound node with zero children renders as a normal node unless the user explicitly used "Convert to Container" (see §8.2).
3. **Collapse state** — store `collapsed: bool` in each node entry of `cytoscape_json`. On layout load, if a compound node is marked collapsed:
   - Hide its children (`child.style('display', 'none')`).
   - Replace the compound box with a single badge node showing the child count (e.g., "+3").
   - Route any edges that terminated on a hidden child to the compound parent instead (visual re-routing only; the underlying Connection records are unchanged).
4. **Drag-reparent** — listen to `cy.on('dragfree', 'node', ...)`. When the drop position is inside another node's bounding box (Cytoscape provides `node.boundingBox()`), fire `PATCH /api/devices/{id}` with `{"parent_id": <parent_id>, "version": <current>}`. When the drop is outside any compound bounding box (and the dragged node currently has a parent), fire `PATCH` with `{"parent_id": null, "version": <current>}`. Handle 409 (optimistic lock miss) by re-fetching the device and surfacing a toast.

**Existing drag handler (BUG-1101-03 target):** The dragfree handler currently only writes to `window._htNodePositions`. HT-021 adds reparent logic to the SAME handler, so the two changes should be made together to avoid merge conflicts. **HT-021 does not fix BUG-1101-03** — it adds the reparent branch, leaving the position-persistence branch intact (or broken, as today). Position autosave remains the bug sweep's problem.

### 8.2 Modified file: `src/ui/components/canvas_events.py`

**"Convert to Container" right-click action.** Add a context-menu item (the file already dispatches node events via `ht:node-*` custom events). When the user selects Convert to Container:
- The node is flagged in `cytoscape_json` as an explicit container (new field `is_explicit_container: bool` on the layout JSON; not a Device DB column).
- Visual treatment switches to compound-node style even with zero children.
- Dropping a device inside this node becomes a valid drop target.

**Design rationale:** "Container-ness" is partially a canvas state (visual hint that empty containers should stay visible) and partially a DB state (parent_id on children). By storing the explicit flag in the layout JSON, we avoid a `Device.is_container` column that would need a migration and would be redundant with `count_children > 0`.

**Deduplication note:** The current `canvas_events.py` already has a `cy.on('tap', 'node', ...)` handler (BUG-1101-08 duplicate). HT-021 does NOT consolidate the duplicate — that's the bug sweep's job. HT-021's context-menu logic must attach to whichever handler survives the sweep, so Feature-Engineer should coordinate with the UX-Designer before both initiatives land.

### 8.3 Modified file: `src/ui/pages/topology.py` (or the device detail panel component)

**Children section.** When the selected device has children (i.e., `detail.children` is non-empty from `GET /api/devices/{id}?include=children`), render a "Children" panel section:
- Heading: "Children ({count})"
- One row per child: type icon + name. Clickable → selects that child.

**Parent breadcrumb.** When the selected device has a parent chain (i.e., `detail.parent_chain` is non-empty from `?include=children,parent_chain`), render a breadcrumb above the device name:
- "Inside: {immediate_parent.name} → {grandparent.name} → {root.name}"
- Each segment is clickable → selects that ancestor.

Both sections use existing design tokens. No new tokens required.

### 8.4 Cytoscape JSON schema extension

Extend each `cytoscape_json.elements.nodes[].data` entry with two optional fields:

```
data.collapsed:             Optional[bool]   — True means render as collapsed badge
data.is_explicit_container: Optional[bool]   — True means render as container even with 0 children
```

Both default to False when missing (backwards-compatible). No migration needed — `cytoscape_json` is `jsonb` and the server does not introspect these fields. The layout load/save round-trip preserves them verbatim.

**Children relationships in the layout JSON are NOT duplicated.** Cytoscape's `data.parent` on each child node is computed at render time from the Device.parent_id DB state, not stored in the layout JSON. This avoids two sources of truth — the DB is authoritative for containment; the layout JSON only owns visual hints (positions, collapse state, explicit-container flag).

---

## 9. Security Boundaries

- `parent_id` is a UUID input from an authenticated API caller; it must reference an existing device (service-layer `_assert_parent_exists` + DB-level FK). UUIDs resist enumeration.
- Cycle detection runs in-process on a pre-loaded `parent_map` (single query). No user-controlled input can cause unbounded DB traversal — the `visited` set bounds the walk.
- RBAC: re-parenting requires `Role.Contributor` (same as device edit, enforced via existing `require_role(Role.Contributor)` on `PATCH /api/devices/{id}`). Readers see the nested canvas but cannot modify containment.
- The CHECK constraint provides defense-in-depth against direct self-loops, even if a future code path bypasses the service.
- No new log events. No PII introduced. The `logger.info("Device updated: id={} name={}", ...)` line already covers re-parent operations; `parent_id` itself is safe to log.

---

## 10. Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `src/models/device.py` | MODIFY | Add `parent_id` to `DeviceBase` + `DeviceUpdate`; add `children`, `parent_chain` to `DeviceResponseEnriched` |
| `src/domain/devices.py` | MODIFY | Add `detect_parent_cycle` + `validate_device_no_children` (pure, stdlib-only) |
| `src/repositories/device_repository.py` | MODIFY | Add `get_children`, `count_children`, `get_parent_map` |
| `src/services/device_service.py` | MODIFY | Add `_assert_parent_exists`; extend `create`, `update`, `delete`, `get_by_id_enriched` |
| `src/api/routers/devices.py` | MODIFY | Extend `get_device` include parser to accept `children` and `parent_chain`; update docstrings |
| `alembic/versions/020_add_device_parent_id.py` | CREATE | Add `parent_id` FK + index + CHECK constraint |
| `src/ui/components/canvas_js.py` | MODIFY | Compound-node element synthesis, compound style, collapse render, dragfree reparent branch |
| `src/ui/components/canvas_events.py` | MODIFY | "Convert to Container" context-menu entry; collapse/expand toggle handler |
| `src/ui/pages/topology.py` | MODIFY | Children section + parent breadcrumb in detail panel |
| `tests/unit/test_devices_domain.py` | MODIFY (or CREATE) | `detect_parent_cycle` (self-loop, direct 2-cycle, 3-cycle, valid chain, empty parent_map); `validate_device_no_children` |
| `tests/unit/test_device_service.py` | MODIFY | Reparent happy path, self-parent 400, circular 400, nonexistent parent 400, clear parent; delete-blocked-by-children 400 |
| `tests/integration/test_devices.py` | MODIFY | `POST` with `parent_id`; `PATCH` reparent; `PATCH` clear parent; `DELETE` with children → 400; `GET ?include=children,parent_chain` |
| `tests/integration/test_canvas_reparent.py` | CREATE | End-to-end: create parent + child via API, fetch layout JSON, assert `data.parent` is set on child element |

---

## 11. Dependency Graph

```
Level 0 (already exists):
  └─ src/models/types.py, src/domain/locations.py (template)

Level 1 (depends only on Level 0):
  ├─ src/models/device.py                          ← add parent_id
  └─ alembic/versions/020_add_device_parent_id.py  ← new migration

Level 2 (depends on Level 1, pure functions only):
  └─ src/domain/devices.py                         ← add detect_parent_cycle + validate_device_no_children

Level 3 (depends on Level 1):
  └─ src/repositories/device_repository.py         ← add get_children, count_children, get_parent_map

Level 4 (depends on Level 2-3):
  └─ src/services/device_service.py                ← extend create/update/delete/get_by_id_enriched

Level 5 (depends on Level 4):
  └─ src/api/routers/devices.py                    ← extend include parser

Level 6 (depends on Level 5, can run in parallel with Level 7):
  ├─ tests/unit/test_devices_domain.py             ← TDD write-first at Level 2
  ├─ tests/unit/test_device_service.py             ← depends on Level 4
  └─ tests/integration/test_devices.py             ← depends on Level 5

Level 7 (depends on Level 5 — UX parallel track):
  ├─ src/ui/components/canvas_js.py                ← compound nodes + dragfree reparent
  ├─ src/ui/components/canvas_events.py            ← convert-to-container context menu
  ├─ src/ui/pages/topology.py                      ← children + breadcrumb panel sections
  └─ tests/integration/test_canvas_reparent.py     ← end-to-end reparent
```

**Critical path:** models → migration → domain → repository → service → router → integration tests. UX track (Level 7) parallelizes off the API contract once Level 5 is stable.

**Parallelization opportunity:** Unit tests for `detect_parent_cycle` (Level 2) can be written TDD-style **before** the function body. Same for `validate_device_no_children`. This is the preferred Feature-Engineer entry point.

---

## 12. Validation

| Constraint | Test |
|---|---|
| `detect_parent_cycle` catches direct self-loop (`new_parent_id == device_id`) | `test_devices_domain.py::test_detect_cycle_self_parent` |
| `detect_parent_cycle` catches A→B→A 2-cycle | `test_devices_domain.py::test_detect_cycle_direct_two_cycle` |
| `detect_parent_cycle` catches A→B→C→A 3-cycle | `test_devices_domain.py::test_detect_cycle_three_cycle` |
| `detect_parent_cycle` allows valid deep chain | `test_devices_domain.py::test_detect_cycle_valid_chain` |
| `detect_parent_cycle` terminates on `None` parent | `test_devices_domain.py::test_detect_cycle_root_parent` |
| `detect_parent_cycle` tolerates pre-existing corrupt cycle in parent_map | `test_devices_domain.py::test_detect_cycle_corrupt_map_guard` |
| `validate_device_no_children` raises on count > 0 | `test_devices_domain.py::test_no_children_guard` |
| `POST /api/devices/` with `parent_id` → child created with parent | `test_devices.py::test_post_with_parent` |
| `POST` with `parent_id` pointing to nonexistent device → 400 | `test_devices.py::test_post_nonexistent_parent` |
| `POST` with `parent_id == null` → top-level device (backward compat) | `test_devices.py::test_post_no_parent_backward_compat` |
| `PATCH /api/devices/{id}` with `parent_id` → reparents | `test_devices.py::test_patch_reparent` |
| `PATCH` with `parent_id = self` → 400 "Device cannot be its own parent" | `test_devices.py::test_patch_self_parent_rejected` |
| `PATCH` introducing cycle → 400 "Circular containment detected" | `test_devices.py::test_patch_cycle_rejected` |
| `PATCH` with `parent_id = null` → clears parent | `test_devices.py::test_patch_clear_parent` |
| `DELETE /api/devices/{id}` with children → 400 + message | `test_devices.py::test_delete_blocked_by_children` |
| `GET /api/devices/{id}?include=children` returns `children` array | `test_devices.py::test_get_include_children` |
| `GET /api/devices/{id}?include=parent_chain` returns breadcrumb chain | `test_devices.py::test_get_include_parent_chain` |
| `GET /api/devices/` list includes `parent_id` on each row | `test_devices.py::test_list_includes_parent_id` |
| DB-level CHECK rejects `parent_id = id` on direct SQL UPDATE | `test_devices.py::test_check_constraint_self_parent` |
| Layout round-trip preserves `collapsed` + `is_explicit_container` | `test_canvas_reparent.py::test_layout_json_roundtrip` |
| All source files ≤ 250 lines | `find src/ -name "*.py" ! -path "*/tests/*" \| xargs wc -l` |
| Type check | `docker compose exec api mypy src/ --ignore-missing-imports` |
| All tests pass | `docker compose exec api pytest` |
| Images build clean | `docker compose build` |

---

## 13. Non-Goals (reaffirmed from HT-021)

- No auto-discovery (Proxmox/Docker → auto-populate children). Phase 2 (LT-001, LT-002).
- No container templates. Future delighter.
- No type-aware containment rules ("only Servers contain VMs"). v1 allows any device to contain any device.
- No drag-to-reorder children within a container. Children are freely positioned on the canvas.
- No container-level aggregate stats. Future delighter.
- No group-level connections. Connections remain device-to-device.
- **No fix for BUG-1101-03 (drag position persistence).** That belongs to the bug sweep. HT-021 only adds the reparent branch to `dragfree`.
- **No fix for BUG-1101-08 (duplicate tap handlers).** Same rationale. HT-021's context-menu work must coordinate with whatever handler structure survives the sweep.

---

## 14. Open Risks

1. **Canvas compound node + existing drag-to-free-position interaction.** Cytoscape compound nodes still allow children to be dragged within the parent's bounding box. If the user drags a child partway outside, the reparent threshold must be clear (rule of thumb: drop point must be > 50% outside the parent bounding box to count as "leaving"). Feature-Engineer + UX-Designer to tune the threshold empirically during implementation.
2. **Collapse state conflicts with diagram last-write-wins.** If two users collapse different containers concurrently, the second save overwrites the first (already the diagram concurrency model). Documented as acceptable for v1 — no behavior change from HT-021.
3. **Parent chain depth performance.** The service-layer iterative walk is O(depth). With the 50-hop cap, this is constant time. Real homelab hierarchies are 3-5 levels deep. No index or materialized path required for Phase 1.
