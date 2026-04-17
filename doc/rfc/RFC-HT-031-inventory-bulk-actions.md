# RFC: Inventory Bulk Actions

**Story:** HT-031 · **Status:** Draft · **Date:** 2026-04-14
**Author:** Architect

---

## 1. Overview

HT-031 adds multi-select and bulk actions to the NiceGUI inventory table so Contributor and Admin users can apply repeated inventory changes without opening each device individually. The implementation remains inventory-page only and reuses the existing per-device backend routes for tags, location assignment, connection lookup, and deletion.

This RFC deliberately does **not** add bulk backend endpoints, schema changes, topology-canvas bulk behavior, arbitrary bulk field editing, or container assignment. The UI orchestrates a batch of existing single-device calls, shows progress in-page, and preserves failed rows for review.

---

## 2. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/ui/pages/inventory.py` | The route/auth shell boundary for `/inventory`; if page composition moves again, the route wrapper changes but the helpers do not. |
| `src/ui/pages/inventory_page_controller.py` | The inventory page’s local state machine: filters, selection, progress, and per-action orchestration. |
| `src/ui/pages/inventory_table.py` | The NiceGUI/Quasar table configuration, including whether bulk selection is native table selection or custom markup. |
| `src/ui/pages/inventory_bulk_toolbar.py` | The toolbar layout and control contract shown only when rows are selected. |
| `src/ui/pages/inventory_bulk_actions.py` | How a bulk action fans out into per-device HTTP requests and how partial results are normalized. |
| `src/ui/pages/inventory_delete_dialog.py` | Inventory delete confirmation wording and the distinction between single-delete and bulk-delete confirmation UX. |
| `src/ui/pages/inventory_filters.py` | Tag/type chip rendering and reuse of fetched tag reference data. |
| `src/domain/inventory.py` | Pure set/intersection rules for inventory-specific derived data such as “common tags across selected devices.” |

Decision: HT-031 should use **NiceGUI table native multiple selection** instead of custom header/row checkbox slots.

Reasoning:
- NiceGUI `ui.table` already supports `selection="multiple"`, `selected`, `on_select`, and `update_rows(clear_selection=...)`.
- The story requires header-checkbox behavior scoped to currently visible filtered rows. Native table selection gives this for free as long as `table.rows` already equals the filtered inventory view.
- The current `inventory_table.py` full-body slot is the main blocker; refactoring that file to targeted `body-cell-*` slots is lower risk than inventing custom checkbox/header event plumbing.

---

## 3. Data Model Changes

None.

- No SQLModel model changes.
- No Pydantic schema changes.
- No Alembic migration.
- No repository changes.
- Existing `DeviceUpdate.version: int` remains the optimistic-locking contract for bulk location updates.

**DevOps-Engineer migration review required:** No.

---

## 4. Domain Logic

`src/domain/inventory.py` remains pure. HT-031 adds only selection-derived helpers that do not import models outside `src/models/types.py`.

### New pure types/signatures

```python
from dataclasses import dataclass
from typing import Protocol, Sequence
import uuid


@dataclass(frozen=True)
class CommonTagOption:
    id: uuid.UUID
    name: str
    color: str


class TagRenderable(Protocol):
    id: uuid.UUID
    name: str
    color: str


class TaggableInventoryDevice(Protocol):
    tags: Sequence[TagRenderable]


def get_common_tags(
    devices: Sequence[TaggableInventoryDevice],
) -> list[CommonTagOption]:
    """Return the sorted tag intersection across all selected devices.

    Invariants:
    - empty selection -> []
    - one selected device -> all of that device's tags
    - many devices -> only tags present on every device
    - output sorted by lowercase name, then UUID for stability
    - never mutates the input devices or tag objects
    """
```

### Why this belongs in `src/domain/inventory.py`

- The “remove common tag” dropdown is a pure intersection rule.
- It is independent of NiceGUI, HTTP, and SQLModel.
- It gives Test-Automation-Engineer a stable unit seam without mocking UI code.

### No new domain behavior

- Bulk action retry policy stays in UI orchestration, not domain.
- Toast copy stays in UI.
- RBAC stays in UI auth guard plus existing API middleware.

---

## 5. Service Layer

None — reuse current service contracts exactly.

Existing services used by HT-031:

| Service | Existing method | Why reused |
|---|---|---|
| `src/services/device_service.py` | `get_all_enriched(...)` | Inventory page initial load already uses this. |
| `src/services/tag_service.py` | `get_all(...)` | Existing tags list for filter chips and add-tag choices. |
| `src/services/location_service.py` | `get_all(...)` | Existing location list for set-location choices. |
| `src/services/tag_service.py` | `attach_to_device(...)` | Existing single-device add-tag mutation. |
| `src/services/tag_service.py` | `detach_from_device(...)` | Existing single-device remove-tag mutation. |
| `src/services/device_service.py` | `update(...)` | Existing single-device location patch with optimistic locking. |
| `src/services/device_service.py` | `delete(...)` | Existing single-device delete behavior. |
| `src/services/connection_service.py` | `get_connections_for_device(...)` | Existing per-device connection list used for bulk-delete skip preflight. |

Transaction boundaries stay unchanged in the backend. The page performs a batch by calling these existing per-device routes one device at a time.

---

## 6. API Layer

No new API routes are needed.

### Existing routes HT-031 reuses

| Method | Path | Response model | Required role | HT-031 usage |
|---|---|---|---|---|
| `GET` | `/api/devices/?include=location,tags,services,networks&limit=1000` | `PaginatedDeviceResponseEnriched` | `Reader` | initial inventory load |
| `GET` | `/api/tags/` | `list[TagWithCountResponse]` | `Reader` | tag filter chips and add-tag choices |
| `GET` | `/api/locations/` | `list[LocationResponse]` | `Reader` | set-location choices |
| `GET` | `/api/devices/{device_id}/connections` | `list[ConnectionResponse]` | `Reader` | bulk-delete skip preflight |
| `POST` | `/api/devices/{device_id}/tags` | `204 No Content` | `Contributor` | add tag |
| `DELETE` | `/api/devices/{device_id}/tags/{tag_id}` | `204 No Content` | `Contributor` | remove common tag |
| `PATCH` | `/api/devices/{device_id}` | `DeviceResponse` | `Contributor` | set location |
| `DELETE` | `/api/devices/{device_id}` | `204 No Content` | `Contributor` | delete selected device |

### Explicit backend/API surface note

**No new backend route, service, repository, model, or schema surface is required for HT-031.**

HT-031 does require one **UI-layer helper module** to orchestrate batches over existing endpoints:

- `src/ui/pages/inventory_bulk_actions.py`

### Important delete-contract note

Current backend behavior for `DELETE /api/devices/{id}` is to **cascade-delete connections**. HT-031’s story copy says bulk delete should **skip devices with active connections**.

To satisfy the story **without changing backend contracts**, the inventory page must perform a UI-side preflight using `GET /api/devices/{id}/connections` and classify any device with a non-empty connection list as `skipped`, never calling `DELETE` for that device.

This keeps HT-031 within scope and preserves the current single-device delete API.

Residual caveat:

- If a connection is created after the preflight check and before the delete request for another device, bulk delete remains best-effort because the server still allows cascade deletion. A stricter invariant would require a future backend story and is explicitly out of scope for HT-031.

---

## 7. UI Layer

### 7.1 Selection State Model

The inventory page keeps a page-scoped mutable state dictionary; the authoritative selection model is a Python `set[str]` of selected device IDs.

```python
state: dict[str, object] = {
    "all": list[DeviceResponseEnriched],
    "filtered": list[DeviceResponseEnriched],
    "search": str,
    "types": set[DeviceType],
    "tag_ids": set[uuid.UUID],
    "q": str,
    "orphan_ids": set[str],
    "placement_counts": dict[str, int],
    "orphan_only": bool,
    "selected_ids": set[str],
    "bulk_busy": bool,
    "bulk_action": str | None,
    "bulk_progress_done": int,
    "bulk_progress_total": int,
    "all_tags": list[dict[str, object]],
    "locations": list[LocationResponse] | None,
}
```

Rules:

- `state["selected_ids"]` is the source of truth for the toolbar and action targeting.
- `table.selected` is a UI mirror of the currently selected row objects.
- Selection is page-scoped only. Reloading or leaving `/inventory` resets it naturally.
- Bulk selection exists only when `user_role in {Role.Contributor, Role.Admin}`.
- Reader pages do not instantiate the bulk toolbar and create the table with `selection=None`.

### 7.2 Header Checkbox and Row Checkbox Behavior

Implementation decision: use native `ui.table(..., selection="multiple", on_select=...)` when the user can bulk edit.

Behavior:

- Row checkbox toggles one currently rendered row.
- Header checkbox toggles all rows currently present in `table.rows`.
- Because the page already replaces `table.rows` with the client-filtered inventory list, the header checkbox is automatically scoped to the visible filtered rows rather than the full database.
- Sorting does not clear selection because sort changes ordering, not membership.
- Filter/search changes do clear selection because they change membership.

### 7.3 Filter/Search Clear Policy

Selection clears when any user-driven control changes the visible row set:

| Control | Clear selection? | Implementation |
|---|---|---|
| Search input | Yes | `_apply_filters(clear_selection=True)` |
| Type chip toggle | Yes | pass a clear-selection wrapper into `render_type_chips(...)` |
| Tag chip toggle | Yes | pass a clear-selection wrapper into `render_tag_chip_filters(...)` / `load_tag_chips(...)` |
| Orphan-only checkbox | Yes | `_apply_filters(clear_selection=True)` |
| Clear filters button | Yes | `_clear_filters()` -> `_apply_filters(clear_selection=True)` |
| Table column sort | No | native Quasar sort only reorders current rows |
| Per-action row updates | No | `_apply_filters(clear_selection=False)` or `table.update_rows(..., clear_selection=False)` |

Concrete rule:

```python
def _apply_filters(*, clear_selection: bool) -> None:
    ...
    table.update_rows(new_rows, clear_selection=clear_selection)
    if clear_selection:
        state["selected_ids"].clear()
        table.selected = []
        sync_bulk_toolbar(...)
```

### 7.4 Bulk Toolbar Contract and Placement

Placement: directly **below the filter controls** and **above the inventory table** inside the same `app_shell(...)` content column.

Why here:

- The toolbar applies to the table as a whole, not the page header.
- It stays visually coupled to the filtered result set.
- It avoids touching the topology canvas or global shell.

#### New module

`src/ui/pages/inventory_bulk_toolbar.py`

```python
from dataclasses import dataclass
from collections.abc import Callable
from nicegui.element import Element


@dataclass
class BulkToolbarRefs:
    root: Element
    count_label: Element
    add_tag_select: Element
    remove_tag_select: Element
    location_select: Element
    delete_button: Element
    progress_row: Element
    progress_bar: Element
    progress_label: Element
    helper_label: Element


def create_bulk_toolbar(
    *,
    on_add_tag: Callable[[str], object],
    on_remove_tag: Callable[[str], object],
    on_set_location: Callable[[str], object],
    on_delete: Callable[[], object],
) -> BulkToolbarRefs:
    ...


def sync_bulk_toolbar(
    refs: BulkToolbarRefs,
    *,
    selection_count: int,
    all_tags: list[dict[str, object]],
    common_tags: list[CommonTagOption],
    locations: list[LocationResponse] | None,
    busy: bool,
    action_label: str | None,
    progress_done: int,
    progress_total: int,
) -> None:
    ...
```

Toolbar contract:

- Hidden when `selection_count == 0`.
- Hidden for `Reader`.
- Shows count badge text: `"{N} selected"`.
- Uses `ui.select` controls rather than freeform inputs.
- `Add tag` options: all tags fetched for filter chips, sorted by name.
- `Remove common tag` options: intersection of currently selected devices via `inventory_domain.get_common_tags(...)`.
- `Set location` options: lazily fetched `GET /api/locations/` and cached in `state["locations"]`.
- `Delete` remains a destructive button that opens confirmation before requests start.
- While `busy=True`, all controls are disabled and the progress row is visible.

Accessibility:

- Add explicit `aria-label` props for all bulk controls.
- Keep native table checkboxes for keyboard navigation and Space toggling.

### 7.5 Progress Indicator and Partial-Result UX

Progress presentation lives in the toolbar, not in a modal.

UX rules:

- When a bulk action starts, set `state["bulk_busy"] = True` **before the first `await`**.
- The toolbar shows a linear progress bar and a compact text label such as `"Deleting 3 of 10"`.
- Controls disable immediately to prevent concurrent double-submit.
- Successful rows update as each request settles.
- On completion:
  - all-success -> clear selection, hide toolbar, show success toast
  - partial-success -> keep failed/skipped rows selected, keep toolbar visible, show warning toast
  - network abort -> stop the loop, preserve unprocessed + failed rows selected, show error toast

Toast policy for new bulk flows:

- Use `src/ui/components/toast.py::show_toast(...)` for consistent multiline summaries.
- Keep the existing single-device dialog notifications unchanged.

### 7.6 Bulk Action Execution Flow

#### New module

`src/ui/pages/inventory_bulk_actions.py`

```python
from dataclasses import dataclass, field
from collections.abc import Callable, Sequence
import uuid

from src.models.device import DeviceResponse, DeviceResponseEnriched
from src.models.location import LocationResponse


@dataclass(frozen=True)
class BulkFailure:
    device_id: str
    device_name: str
    detail: str


@dataclass(frozen=True)
class BulkProgress:
    completed: int
    total: int


@dataclass(frozen=True)
class BulkActionOutcome:
    succeeded_ids: list[str] = field(default_factory=list)
    updated_devices: dict[str, DeviceResponse] = field(default_factory=dict)
    failed: list[BulkFailure] = field(default_factory=list)
    skipped: list[BulkFailure] = field(default_factory=list)
    aborted: bool = False
    abort_detail: str | None = None


ProgressCallback = Callable[[BulkProgress], None]


async def list_locations(token: str) -> list[LocationResponse]: ...


async def add_tag_to_devices(
    devices: Sequence[DeviceResponseEnriched],
    tag_id: uuid.UUID,
    token: str,
    on_progress: ProgressCallback,
) -> BulkActionOutcome: ...


async def remove_tag_from_devices(
    devices: Sequence[DeviceResponseEnriched],
    tag_id: uuid.UUID,
    token: str,
    on_progress: ProgressCallback,
) -> BulkActionOutcome: ...


async def set_location_for_devices(
    devices: Sequence[DeviceResponseEnriched],
    location_id: uuid.UUID,
    token: str,
    on_progress: ProgressCallback,
) -> BulkActionOutcome: ...


async def delete_devices_with_connection_preflight(
    devices: Sequence[DeviceResponseEnriched],
    token: str,
    on_progress: ProgressCallback,
) -> BulkActionOutcome: ...
```

Execution policy for all four actions:

- Reuse one `httpx.AsyncClient` per bulk action.
- Execute **sequentially**, not concurrently.
- Update progress after every settled request.
- Continue past ordinary HTTP failures so partial success is possible.
- Abort immediately on `httpx.HTTPError` and return `aborted=True`.

Why sequential is correct for HT-031:

- The story is medium-sized and explicitly prefers simple reuse of single-device endpoints.
- Deterministic per-row progress is easier to reason about and test.
- Optimistic-lock conflicts on location patch are simpler when processed one device at a time.
- The story’s target batch size is roughly 50 devices; this does not justify concurrency complexity.

#### 7.6.1 Add Tag

Request per selected device:

```http
POST /api/devices/{id}/tags
{"tag_id": "<uuid>"}
```

Flow:

1. User picks a tag from the toolbar.
2. Controller sets `bulk_busy`, resets progress to `0/N`, disables selection controls.
3. Action helper loops selected devices.
4. For `204`, controller appends the chosen tag to the local device’s `tags` list if absent.
5. Table rerenders after each success.
6. On completion, clear successful selections; keep failures selected.
7. Toast:
   - success: `Tag 'prod' added to 6 devices`
   - partial: `Tag 'prod' added to 4 of 6 devices` + `2 failed. Selection kept for review.`

No extra backend helper is needed.

#### 7.6.2 Remove Common Tag

Flow:

1. Controller derives `common_tags = inventory_domain.get_common_tags(selected_devices)`.
2. Toolbar populates `Remove common tag` only with that intersection.
3. If intersection is empty, the control stays disabled and shows helper text `No common tags across selection`.
4. Action helper issues:

```http
DELETE /api/devices/{id}/tags/{tag_id}
```

5. For each `204`, controller removes the tag from the local device’s `tags` list.
6. Table rerenders after each success.
7. Successes clear; failures remain selected.

No extra backend helper is needed.

#### 7.6.3 Set Location

Flow:

1. On first use of the toolbar, controller lazily loads `GET /api/locations/` and caches the result in `state["locations"]`.
2. User picks a location.
3. For each selected device, helper issues:

```http
PATCH /api/devices/{id}
{"location_id": "<uuid>", "version": <current device.version>}
```

4. On `200`, helper stores the returned `DeviceResponse` in `BulkActionOutcome.updated_devices[device_id]`.
5. Controller updates the local selected device with:
   - `location_id = chosen_location.id`
   - `location_name = chosen_location.name`
   - `version = response.version`
   - `updated_at = response.updated_at`
6. Conflicts (`409`) and validation errors (`4xx`) remain selected for retry/review.
7. Toast:
   - success: `Moved 6 devices to Rack 1`
   - partial: `Moved 4 of 6 devices to Rack 1`

No extra backend helper is needed.

#### 7.6.4 Delete Selected Devices With Skip/Partial Reporting

Bulk delete uses the existing single-device delete endpoint plus a UI-side connection preflight.

Bulk confirm text:

`Delete {N} devices? This cannot be undone. Devices with active connections will be skipped.`

Flow per selected device:

1. `GET /api/devices/{id}/connections`
2. If the response is `200` and non-empty, classify as:
   - `skipped`
   - detail: `has active connections`
   - do **not** call delete for that device
3. Else call:

```http
DELETE /api/devices/{id}
```

4. On `204`, remove the device from:
   - `state["all"]`
   - `state["filtered"]`
   - `state["selected_ids"]`
   - `state["orphan_ids"]`
   - `state["placement_counts"]`
5. Table rerenders immediately so deleted rows disappear during progress.
6. On `4xx/5xx`, classify as `failed` and keep the row selected.
7. On network error, abort the remaining queue and preserve all not-yet-attempted rows selected.

Completion toast examples:

- all success: `Deleted 5 devices`
- partial with skips: `Deleted 7 of 10 devices` + `3 skipped: have active connections`
- mixed failures: `Deleted 7 of 10 devices` + `2 skipped, 1 failed. Selection kept for review.`
- network abort: `Bulk delete stopped after a network error` + `4 of 10 completed before the connection failed`

### 7.7 Inventory Controller Extraction

The current `src/ui/pages/inventory.py` is already near the file-size budget. HT-031 must not inline the new bulk-selection workflow into that file.

#### New file

`src/ui/pages/inventory_page_controller.py`

```python
async def render_inventory_page(token: str, user_role: Role | None) -> None:
    """Render the full inventory page body inside app_shell()."""
```

Responsibilities:

- render search/filter controls, toolbar, table, and empty state
- load devices + orphan metadata + tag options
- apply filters with optional selection clearing
- keep `state["selected_ids"]` in sync with `table.selected`
- resolve selected `DeviceResponseEnriched` objects from `state["all"]`
- dispatch bulk actions through `inventory_bulk_actions.py`
- apply local per-row updates after each successful mutation
- preserve only failed/skipped selections after partial completion

#### Before/after diff for `src/ui/pages/inventory.py`

```diff
@@
-from src.ui.pages.inventory_delete_dialog import show_delete_confirmation
-from src.ui.pages.inventory_filters import (
-    load_tag_chips,
-    render_tag_chip_filters,
-    render_type_chips,
-)
-from src.ui.pages.inventory_table import build_inventory_rows, create_inventory_table
+from src.ui.pages.inventory_page_controller import render_inventory_page
@@
 @ui.page("/inventory")
 async def inventory_page() -> None:
     """Inventory page — lists all devices with search and type filters."""
     if redirect_if_unauthenticated(current_path="/inventory"):
         return
     token: str = nicegui_app.storage.user.get("access_token", "")
     user_role = get_ui_role()
-    can_delete = user_role is not None and user_role in (Role.Contributor, Role.Admin)
-    state: dict = {...}
-    refs: dict = {}
-    ...
-    await _load_devices()
-    await load_tag_chips(...)
+    await render_inventory_page(token=token, user_role=user_role)
```

#### Before/after diff for `src/ui/pages/inventory_filters.py`

```diff
@@
 async def load_tag_chips(
     token: str,
     tag_chip_row: Element,
     selected_tag_ids: set[uuid.UUID],
     tag_chip_metas: list[dict[str, object]],
     apply_filters: Callable[[], None],
-) -> None:
+) -> list[dict[str, object]]:
@@
-        if tresp.status_code != 200:
-            return
+        if tresp.status_code != 200:
+            return []
         all_tags = tresp.json()
         render_tag_chip_filters(...)
+        return all_tags
     except Exception as exc:
         logger.error("Tag chips load: {}", str(exc))
+    return []
```

#### Before/after diff for `src/ui/pages/inventory_table.py`

```diff
@@
-_INVENTORY_TABLE_BODY_SLOT = r"""
-<q-tr :props="props">
-  ... custom full-row template ...
-</q-tr>
-"""
+_ICON_SLOT = r"""<q-td key="icon" :props="props"><q-icon :name="props.row.icon" size="sm" /></q-td>"""
+_NAME_SLOT = r"""... orphan icon markup ..."""
+_STATUS_SLOT = r"""... q-badge markup ..."""
+_IP_SLOT = r"""... copy button markup ..."""
+_SERVICES_SLOT = r"""... service badge markup ..."""
+_NETWORKS_SLOT = r"""... network chips markup ..."""
+_ACTIONS_SLOT = r"""... edit/topology/delete buttons ..."""
@@
-def create_inventory_table() -> Element:
+def create_inventory_table(
+    *,
+    can_bulk_edit: bool,
+    on_select: Callable[[TableSelectionEventArguments], None],
+) -> Element:
     """Create inventory table with custom cell slots and selection wiring."""
     table = ui.table(
         columns=_INVENTORY_TABLE_COLUMNS,
         rows=[],
         row_key="id",
+        selection="multiple" if can_bulk_edit else None,
+        on_select=on_select if can_bulk_edit else None,
     )
-    table.add_slot("body", _INVENTORY_TABLE_BODY_SLOT)
+    table.add_slot("body-cell-icon", _ICON_SLOT)
+    table.add_slot("body-cell-name", _NAME_SLOT)
+    table.add_slot("body-cell-status", _STATUS_SLOT)
+    table.add_slot("body-cell-ip", _IP_SLOT)
+    table.add_slot("body-cell-services", _SERVICES_SLOT)
+    table.add_slot("body-cell-networks", _NETWORKS_SLOT)
+    table.add_slot("body-cell-actions", _ACTIONS_SLOT)
     return table
```

#### Before/after diff for `src/ui/pages/inventory_delete_dialog.py`

```diff
@@
 async def show_delete_confirmation(...):
     ...

+async def show_bulk_delete_confirmation(
+    selected_count: int,
+    on_confirm: Callable[[], object],
+) -> None:
+    """Confirm bulk delete, then hand control back to the toolbar progress flow."""
+    with ui.dialog() as dialog, ui.card().style("min-width:400px"):
+        ui.label(f"Delete {selected_count} devices?")
+        ui.label(
+            "This cannot be undone. Devices with active connections will be skipped."
+        )
+        with ui.row().classes("w-full justify-end q-mt-md"):
+            ui.button("Cancel", on_click=dialog.close).props("flat color=grey")
+            ui.button("Delete devices", on_click=...)  # closes dialog, then runs on_confirm
+    dialog.open()
```

---

## 8. Security Boundaries

- UI hides bulk selection and the bulk toolbar for `Reader`.
- Existing API middleware still enforces:
  - `Reader` for loading devices, tags, locations, and per-device connections
  - `Contributor` for add-tag, remove-tag, patch location, and delete
- No new endpoint bypasses RBAC.
- No new secret-bearing data is introduced.
- Bulk result toasts must not log bearer tokens or raw server payloads.
- Progress/result logging should use `logger.error("Inventory bulk action failed: {}", str(exc))` style only for exceptions, not device notes or other rich content.

Double gate:

- UI hides checkboxes and toolbar for `Reader`.
- API already rejects non-Contributor mutation attempts with `403`.

---

## 9. Edge Cases

### 1. Empty state

- Zero inventory rows: table renders empty, no toolbar, no selection.
- Filtered result becomes empty after user input: selection clears, toolbar hides, existing empty-state card remains visible.
- Selected rows deleted until none remain: toolbar hides automatically.

### 2. Boundary values

- `limit=1000` remains the page load cap; HT-031 does not alter pagination.
- Tag names and location names reuse existing response data with existing max lengths.
- A single selected device still shows the same toolbar and supports all four actions.
- `Remove common tag` on one selected device means all of that device’s tags are eligible.

### 3. Concurrent access

- Bulk location patch can hit `409` if a device version changed after page load. Those rows remain selected.
- Add/remove tag operations are naturally idempotent at the route layer and can be retried.
- Bulk delete’s connection-skip policy is best-effort because the server delete contract still cascades connections. This race is accepted for HT-031.

### 4. Cascade effects

- Successful delete still triggers the existing backend cascade behavior for connections and diagram cleanup.
- HT-031’s UI preflight intentionally avoids calling delete for devices that currently show active connections.
- Devices with children can still fail delete with the existing backend `400`; those rows remain selected and surface in the partial-result toast.

### 5. RBAC per operation

| Operation | Reader | Contributor | Admin |
|---|---|---|---|
| View inventory rows, filters, tags, locations | Yes | Yes | Yes |
| See selection checkboxes | No | Yes | Yes |
| See bulk toolbar | No | Yes | Yes |
| Bulk add/remove tag | No | Yes | Yes |
| Bulk set location | No | Yes | Yes |
| Bulk delete | No | Yes | Yes |

### 6. Round-trip integrity

- No import/export schema changes.
- No JSON shape changes.
- No mutation of topology payloads beyond the existing backend delete behavior.

### 7. Canvas impact

- No topology multi-select work.
- No Cytoscape JS changes.
- Existing delete route can still clean diagram placements if a bulk-deleted device is actually deleted.
- HT-031 does not change canvas affordances, shortcuts, or edit mode.

### 8. Performance at scale

- Inventory page still loads once and filters client-side.
- Bulk execution is sequential and updates progress after each request; this is acceptable for story-scale batches around 50 devices.
- `GET /api/locations/` is lazy-loaded only when the user first uses `Set location`.
- `GET /api/devices/{id}/connections` adds one preflight request per delete candidate; this is acceptable for HT-031 and avoids backend changes.

---

## 10. Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `doc/rfc/RFC-HT-031-inventory-bulk-actions.md` | Create | Architecture and implementation contract for HT-031. |
| `src/ui/pages/inventory.py` | Modify | Reduce the route file to auth + delegation so it stays below the source-file cap. |
| `src/ui/pages/inventory_page_controller.py` | Create | Own inventory page state, render flow, selection sync, progress state, and bulk-action orchestration. |
| `src/ui/pages/inventory_table.py` | Modify | Refactor the table to native multiple selection plus targeted cell slots. |
| `src/ui/pages/inventory_filters.py` | Modify | Return fetched tag payload so the page can reuse it for bulk add-tag choices. |
| `src/ui/pages/inventory_bulk_toolbar.py` | Create | Render and sync the bulk toolbar shown above the table. |
| `src/ui/pages/inventory_bulk_actions.py` | Create | Normalize sequential per-device HTTP execution and partial-result reporting. |
| `src/ui/pages/inventory_delete_dialog.py` | Modify | Add bulk delete confirmation while preserving single-device delete behavior. |
| `src/domain/inventory.py` | Modify | Add pure common-tag intersection helper for the remove-tag control. |
| `tests/unit/test_inventory_domain.py` | Modify | Cover common-tag intersection edge cases. |
| `tests/unit/test_inventory_helpers.py` | Modify | Cover table selection mode, toolbar-related helper behavior, and delete-dialog additions. |
| `tests/unit/test_inventory_page_execution.py` | Modify | Cover selection clear-on-filter, RBAC hiding, and page-level bulk orchestration. |
| `tests/unit/test_inventory_bulk_actions.py` | Create | Cover add/remove/location/delete batch normalization, network abort, and partial-result logic. |
| `tests/unit/nicegui_fakes.py` | Modify | Add fake support for `table.selection`, `table.selected`, `table.update_rows`, and `ui.linear_progress`. |
| `tests/e2e/test_stories_e2e.py` | Modify | Add an HT-031 end-to-end scenario over the inventory page. |

---

## 11. Test Plan

### Unit tests

`tests/unit/test_inventory_domain.py`

- `get_common_tags([]) -> []`
- one selected device returns all of its tags
- multiple selected devices return only the intersection
- tag order is stable and alphabetical

`tests/unit/test_inventory_helpers.py`

- `create_inventory_table(can_bulk_edit=True, ...)` sets `selection="multiple"`
- `create_inventory_table(can_bulk_edit=False, ...)` sets no selection
- body-cell action slot still contains edit/topology/delete actions
- bulk delete dialog renders the correct confirmation copy

`tests/unit/test_inventory_bulk_actions.py`

- add-tag all success
- add-tag partial HTTP failure
- remove common tag all success
- set-location uses each device’s current version and captures returned versions
- delete preflight skips devices whose connection list is non-empty
- delete aborts on `httpx.HTTPError` and reports completed count so far
- failed and skipped device IDs are distinct from succeeded IDs

`tests/unit/test_inventory_page_execution.py`

- Contributor sees selection-capable table and hidden toolbar until selection exists
- Reader sees no selection checkboxes and no toolbar
- changing search text clears selection and hides the toolbar
- changing type/tag/orphan filters clears selection
- partial bulk result keeps failed/skipped rows selected
- full success clears selection

`tests/unit/nicegui_fakes.py`

- extend fake table element with `selection`, `selected`, `update_rows(clear_selection=...)`
- add a fake `linear_progress` element so progress state can be asserted

### Integration tests

None required for new backend surfaces because HT-031 does not introduce any.

Existing integration coverage already proves the reused routes:

- device list/load
- device patch with version
- tag attach/detach
- device delete
- device connection lookup
- RBAC on all of the above

### E2E tests

Extend `tests/e2e/test_stories_e2e.py` with an HT-031 inventory scenario:

1. Log in as Admin or Contributor.
2. Create a small fixture set via API: devices, two tags, one location, and one connection on one of the devices.
3. Open `/inventory`.
4. Select two visible rows and verify the toolbar shows `2 selected`.
5. Use the header checkbox with a filter active and verify only filtered rows become selected.
6. Change the search/filter and verify selection clears and the toolbar hides.
7. Re-select rows and bulk add a tag; verify toast and updated table tags.
8. Bulk remove a common tag; verify only common tags are offered.
9. Bulk set a location; verify location column updates.
10. Bulk delete a selection containing one connected device and one unconnected device; verify the unconnected device disappears, the connected device remains, and the toast reports the skip.

Fixtures already available from `tests/conftest.py`:

- `client`
- `admin_token`
- `contributor_token`
- `reader_token`
- `session`

No new DB model fixture registration is needed.

---

## 12. Implementation Order

1. Refactor `src/ui/pages/inventory.py` into a thin route wrapper and add `src/ui/pages/inventory_page_controller.py`.
2. Refactor `src/ui/pages/inventory_table.py` to native selection plus body-cell slots.
3. Extend `src/ui/pages/inventory_filters.py` to return fetched tag data.
4. Add `inventory_domain.get_common_tags(...)`.
5. Add `src/ui/pages/inventory_bulk_toolbar.py`.
6. Add `src/ui/pages/inventory_bulk_actions.py`.
7. Add bulk delete confirmation to `src/ui/pages/inventory_delete_dialog.py`.
8. Wire controller state, selection sync, toolbar sync, and per-action handlers.
9. Add/extend unit tests including fake NiceGUI support.
10. Add the HT-031 E2E story scenario.
