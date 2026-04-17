# RFC: Location Management + Inventory List View

**Stories:** HT-005 (Location Management) + HT-009 (Inventory List View)
**Status:** Draft — awaiting Feature-Engineer implementation
**Date:** 2026-04-09
**Author:** Architect

---

## 1. Overview

HT-005 creates the `Location` entity so that homelab owners can record where each device physically lives — a rack/row in a garage, or a geographic site for distributed nodes. HT-009 delivers a fast inventory table at `/inventory` that displays all devices with their location names and supports text search and type/tag filtering. The two stories are bundled because the inventory table's "location" column is only meaningful once HT-005 data exists, and the device response extension needed for HT-009 requires the `location_id` FK added in HT-005.

**Hidden design decisions (Parnas test):**
- `src/models/location.py` hides the Location SQLModel schema — if the location concept changes (e.g. adds floors), only this file changes.
- `src/domain/locations.py` hides location business rules (type-dependent required fields, coordinate bounds, cycle detection).
- `src/domain/inventory.py` hides the inventory filter algorithm (search, type chips, tag chips).
- `src/repositories/location_repository.py` hides the PostgreSQL query mechanics for Location, including ancestor resolution and the devices-at-location check.

---

## 2. Data Model Changes

### 2.1 New file: `src/models/location.py`

Follow the existing `{Entity}Base / {Entity} / {Entity}Create / {Entity}Update / {Entity}Response` pattern used in `src/models/device.py`.

```
LocationBase (SQLModel, no table):
  name:       str               — Field(min_length=1, max_length=255)
  type:       LocationType      — from src/models/types.py (rack | geo)
  lat:        Optional[float]   — Field(default=None)
  lng:        Optional[float]   — Field(default=None)
  rack:       Optional[str]     — Field(default=None, max_length=64)
  row:        Optional[str]     — Field(default=None, max_length=64)
  parent_id:  Optional[uuid.UUID] — Field(default=None, foreign_key="locations.id")

Location (LocationBase, table=True):
  __tablename__ = "locations"
  id:           uuid.UUID   — Field(default_factory=uuid.uuid4, primary_key=True)
  created_at:   datetime    — Field(default_factory=_utcnow)
  updated_at:   datetime    — Field(default_factory=_utcnow)

LocationCreate (LocationBase):
  — no additional fields; type-dependent validation is deferred to domain layer

LocationUpdate (SQLModel, no table):
  name:       Optional[str]
  type:       Optional[LocationType]
  lat:        Optional[float]
  lng:        Optional[float]
  rack:       Optional[str]
  row:        Optional[str]
  parent_id:  Optional[uuid.UUID]
  — All fields optional; type-consistency re-validation runs in location_service.update()

LocationResponse (LocationBase):
  id:           uuid.UUID
  created_at:   datetime
  updated_at:   datetime

LocationResponseWithAncestors (LocationResponse):
  ancestors: list[LocationResponse]   — ordered nearest→root
```

**Constraint:** No Pydantic validators in the model layer for type-dependent rules. Field length validators (`min_length`, `max_length`) are acceptable at the model layer. All business-rule validators live in `src/domain/locations.py`.

### 2.2 Modified file: `src/models/device.py`

Add `location_id` to `DeviceBase` so it propagates to `DeviceCreate`, `DeviceUpdate`, and `DeviceResponse`:

```
DeviceBase — add:
  location_id: Optional[uuid.UUID] — Field(default=None, foreign_key="locations.id")
```

This means `DeviceCreate` and `DeviceUpdate` both accept an optional `location_id`. `DeviceResponse` also gains `location_id: Optional[uuid.UUID]`.

**New response schema for enriched endpoint:**

```
DeviceResponseEnriched (DeviceResponse):
  location_name: Optional[str] = None
  — tags: list[TagSummary] = []  ← DEFERRED until HT-006 is implemented
```

`DeviceResponseEnriched` is a strict superset of `DeviceResponse`. All enriched-list endpoints return `DeviceResponseEnriched`; fields default to `None`/`[]` when not requested, preserving backward compatibility.

```
PaginatedDeviceResponseEnriched (SQLModel):
  items:  list[DeviceResponseEnriched]
  total:  int
  page:   int
  limit:  int
```

The existing `PaginatedDeviceResponse` is kept unchanged so that the un-enriched `GET /api/devices/` response type is not broken.

---

## 3. Domain Layer

### 3.1 New file: `src/domain/locations.py`

All functions are pure Python. No imports from SQLModel, FastAPI, or any package outside the standard library and `src/models/types.py`.

**`validate_location_fields(type, lat, lng, rack, row) -> None`**
- Invariants enforced:
  - If `type == LocationType.geo`: `lat` and `lng` must both be present. `rack` and `row` must be absent (None).
  - If `type == LocationType.rack`: `lat` and `lng` must both be absent. `rack` or `row` may be absent (neither is strictly required).
  - `lat` must be in `[-90.0, 90.0]` (inclusive). Raise `ValueError("lat must be between -90 and 90")`.
  - `lng` must be in `[-180.0, 180.0]` (inclusive). Raise `ValueError("lng must be between -180 and 180")`.
- Error messages must match the acceptance criteria verbatim:
  - `"Geographic locations require lat and lng"`
  - `"Rack locations must not have coordinates"`
  - `"lat must be between -90 and 90"`
  - `"lng must be between -180 and 180"`

**`detect_cycle(location_id, new_parent_id, parent_map) -> bool`**
- Signature: `(location_id: uuid.UUID, new_parent_id: uuid.UUID, parent_map: dict[uuid.UUID, Optional[uuid.UUID]]) -> bool`
- `parent_map` is a flat `{id: parent_id}` dict for **all** existing locations, loaded once per request by the service without filtering.
- Algorithm: Walk from `new_parent_id` upward through `parent_map`. If the walk reaches `location_id`, return `True`. If `new_parent_id == location_id`, return `True` immediately (direct self-loop). If a `None` parent is reached, return `False`.
- The walk must track visited nodes to guard against pre-existing corrupt cycles (return `True` on revisit).
- This function receives no database sessions; the repository loads `parent_map` and passes it in.

**`validate_location_deletable(device_names: list[str]) -> None`**
- If `device_names` is non-empty, raise `ValueError` with the message: `"Location has {n} device(s) assigned: {names}"` where `names` is a comma-joined list of device names (truncated to first 5 if longer, with ` (and N more)` appended).

### 3.2 New file: `src/domain/inventory.py`

**`filter_devices(devices, search, types, tag_ids) -> list[DeviceResponseEnriched]`**
- Signature:
  ```
  filter_devices(
      devices: list[DeviceResponseEnriched],
      search: str,
      types: set[DeviceType],
      tag_ids: set[uuid.UUID],
  ) -> list[DeviceResponseEnriched]
  ```
- Filter semantics (all applied together with AND between categories):
  1. **Search** (if non-empty after `.strip()`): case-insensitive substring match across `name`, `ip`, `notes`. A device matches if any of those fields contains the search string. `None` fields are treated as empty strings.
  2. **Type filter** (if `types` is non-empty): device's `type` must be in `types` (OR within the set).
  3. **Tag filter** (if `tag_ids` is non-empty): device must carry at least one tag whose id is in `tag_ids` (OR within the set). Compares against `device.tags` list (added in HT-006; pass an empty `set()` until then — function must not fail when tags are empty).
- Returns a new list in the same order as input. Does not mutate the input list.
- This function must be testable with zero mocks — all inputs are plain Python objects.

---

## 4. Repository Layer

### 4.1 New file: `src/repositories/location_repository.py`

Follows the method signature conventions in `src/repositories/device_repository.py`.

| Method | Signature | Notes |
|---|---|---|
| `create` | `(session, location: Location) -> Location` | `session.add`, `commit`, `refresh` |
| `get_by_id` | `(session, location_id: UUID) -> Location \| None` | `session.get` |
| `get_all` | `(session, type: Optional[LocationType] = None) -> list[Location]` | Optional WHERE filter on `type` column; returns full unpaginated list (location count is small) |
| `get_ancestors` | `(session, location_id: UUID) -> list[Location]` | Recursive parent walk; order is nearest→root. Stops at NULL parent. Max depth guard: abort after 50 hops and raise `ValueError("Location hierarchy depth exceeds limit")` |
| `get_devices_at_location` | `(session, location_id: UUID) -> list[Device]` | SELECT from devices WHERE location_id = ?; returns empty list, not None |
| `get_parent_map` | `(session) -> dict[UUID, Optional[UUID]]` | SELECT id, parent_id FROM locations; builds dict. Used by service to pass to `detect_cycle` |
| `update` | `(session, location: Location) -> Location` | `session.add`, `commit`, `refresh` |
| `delete` | `(session, location: Location) -> None` | `session.delete`, `commit` |

Import `Device` from `src/models/device` (cross-model import is acceptable in the repository layer — repositories may reference any model).

### 4.2 Modified file: `src/repositories/device_repository.py`

Add one new method:

**`get_all_with_location(session, page, limit) -> tuple[list[tuple[Device, Optional[str]]], int]`**
- Performs a LEFT OUTER JOIN of `devices` onto `locations` (`devices.location_id = locations.id`).
- Returns a list of `(Device, location_name_or_None)` tuples and the total count.
- Pagination parameters: `page: int = 1`, `limit: int = 1000`.
- Order: ascending `devices.created_at`.
- The `total` count uses a separate `SELECT COUNT(*)` against `devices` (no join needed for count).

Existing methods (`create`, `get_by_id`, `get_all`, `update`, `delete`, `count`) are unchanged.

---

## 5. Service Layer

### 5.1 New file: `src/services/location_service.py`

| Method | Responsibilities |
|---|---|
| `create(data: LocationCreate, session) -> Location` | 1. Call `locations_domain.validate_location_fields(data.type, data.lat, data.lng, data.rack, data.row)`. Catch `ValueError`, re-raise as `HTTPException(400)`. 2. If `data.parent_id` is set: load `parent_map` via `location_repository.get_parent_map(session)`. Call `detect_cycle(data.parent_id, data.parent_id, parent_map)` — note: for a new location, there is no existing ID yet, so cycle is impossible on create unless parent_id points to itself. Check `data.parent_id` exists (get_by_id, raise 404 if not). 3. Build `Location(...)` and call `location_repository.create`. Log `logger.info`. |
| `get_by_id(location_id, session) -> LocationResponse` | `location_repository.get_by_id`; raise `HTTPException(404)` if None. Return `LocationResponse.model_validate`. |
| `get_all(session, type=None) -> list[LocationResponse]` | Delegate to `location_repository.get_all(session, type)`. Return mapped list. |
| `get_with_ancestors(location_id, session) -> LocationResponseWithAncestors` | Get location (404 if missing). Load ancestors via `location_repository.get_ancestors`. Build `LocationResponseWithAncestors`. |
| `update(location_id, data: LocationUpdate, session) -> LocationResponse` | 1. Fetch existing (404 if not). 2. Merge fields: compute effective type/lat/lng/rack/row by overlaying `data` onto existing values (`exclude_unset=True`). 3. Re-run `validate_location_fields` on merged values. 4. If `data.parent_id` is set (and differs from current): load `parent_map`, call `detect_cycle(location_id, data.parent_id, parent_map)`, raise `HTTPException(400, "Cycle detected in location hierarchy")` if True. 5. Apply updates, set `updated_at`, call `location_repository.update`. Log. |
| `delete(location_id, session) -> None` | 1. Fetch existing (404 if not). 2. Call `location_repository.get_devices_at_location(session, location_id)` — get list of Device objects. 3. Call `locations_domain.validate_location_deletable([d.name for d in devices])`. Catch `ValueError`, re-raise as `HTTPException(400)`. 4. Call `location_repository.delete(session, location)`. Log. |

**Cycle-detection note for `create`:** Because the new location has no `id` yet, a self-loop (`parent_id == None`) cannot occur at create time. What we must guard is: the proposed `parent_id` must exist in the DB (return 404 if not). The detection of "would this parent_id form a cycle in the existing tree" is not possible without the new node's id, so `detect_cycle` is not called at create time. It IS called at update time when `parent_id` changes.

### 5.2 Modified file: `src/services/device_service.py`

Add one new method:

**`get_all_enriched(session, page, limit, include: set[str]) -> tuple[list[DeviceResponseEnriched], int]`**
- If `"location"` is in `include`: call `device_repository.get_all_with_location(session, page, limit)`. Build `DeviceResponseEnriched` from each `(device, location_name)` tuple.
- If `"location"` is not in `include`: call existing `device_repository.get_all(session, page, limit)`. Build `DeviceResponseEnriched` with `location_name=None`.
- Tag enrichment (`"tags"` in `include`) is a stub that silently skips — implemented when HT-006 lands.
- Existing `get_all` method is not modified.

---

## 6. API Layer

### 6.1 New file: `src/api/routers/locations.py`

```
prefix: /api/locations
tags:   ["locations"]
```

| Method | Path | Request Body / Params | Response | RBAC |
|---|---|---|---|---|
| POST | `/` | `LocationCreate` body | `LocationResponse` (201) | `Role.Contributor` |
| GET | `/` | `?type=rack\|geo` (optional query param) | `list[LocationResponse]` | `Role.Reader` |
| GET | `/{id}` | `?include=ancestors` (optional query param) | `LocationResponse` or `LocationResponseWithAncestors` | `Role.Reader` |
| PATCH | `/{id}` | `LocationUpdate` body | `LocationResponse` | `Role.Contributor` |
| DELETE | `/{id}` | — | 204 No Content | `Role.Contributor` |

**`GET /{id}` response type selection:** If `include=ancestors` is present in the query string, the handler calls `location_service.get_with_ancestors` and returns `LocationResponseWithAncestors`. Otherwise it calls `location_service.get_by_id` and returns `LocationResponse`. Use `Union[LocationResponse, LocationResponseWithAncestors]` as the `response_model`, or annotate with the supertype and let FastAPI serialize naturally.

**Error propagation:** Catch `ValueError` from service calls and re-raise as `HTTPException(422)` for validation errors; `HTTPException` raised in service passes through directly to the client.

### 6.2 Modified file: `src/api/routers/devices.py`

Extend `list_devices` (`GET /`):

- Add query param: `include: str = Query(default="")` — comma-separated include keys, e.g. `"location"` or `"location,tags"`.
- Parse into `include_set: set[str] = {k.strip() for k in include.split(",") if k.strip()}`.
- If `include_set` is non-empty: call `device_service.get_all_enriched(session, page, limit, include_set)`, return `PaginatedDeviceResponseEnriched`.
- If `include_set` is empty: call existing `device_service.get_all(session, page, limit)`, return existing `PaginatedDeviceResponse` (unchanged path — backward compatible).
- Raise the `limit` cap from `le=100` to `le=1000` to support the inventory page's full-dataset fetch.

Extend `create_device` and `update_device` (POST `/`, PATCH `/{id}`):
- `DeviceCreate` and `DeviceUpdate` now carry `location_id: Optional[uuid.UUID]` (from `DeviceBase` change in §2.2). No code changes needed in the router — Pydantic will deserialize it automatically.
- `device_service.create` and `device_service.update` must validate that `location_id`, if provided, exists in the `locations` table. Add an `_assert_location_exists(location_id, session)` helper in `device_service.py` that calls `location_repository.get_by_id`; raise `HTTPException(400, "Location not found")` if missing.

### 6.3 Modified file: `src/api/app.py`

Register the new locations router. Follow the same `include_router` pattern used for devices.

---

## 7. Migration Plan

Migrations follow the `0NN_*.py` naming convention. Next sequence numbers after `006`:

### Migration 007 — `007_create_locations_table.py`

**Revises:** `006`

Create the `locations` table:

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default gen_random_uuid() |
| `name` | VARCHAR(255) | NOT NULL |
| `type` | `location_type` enum | NOT NULL |
| `lat` | FLOAT | nullable |
| `lng` | FLOAT | nullable |
| `rack` | VARCHAR(64) | nullable |
| `row` | VARCHAR(64) | nullable |
| `parent_id` | UUID | nullable, FK → `locations.id` ON DELETE RESTRICT |
| `created_at` | TIMESTAMP WITH TIME ZONE | NOT NULL |
| `updated_at` | TIMESTAMP WITH TIME ZONE | NOT NULL |

Create PostgreSQL native enum type `location_type` with values `('rack', 'geo')` using idempotent `DO $$ BEGIN … EXCEPTION WHEN duplicate_object THEN null; END $$` pattern (same as migration 002).

Create index `ix_locations_type` on `(type)` — supports `GET /api/locations?type=geo` filtering.

**Downgrade:** Drop index, drop table, drop enum type.

**DevOps-Engineer migration review required** (new table, new enum type).

### Migration 008 — `008_add_location_id_to_devices.py`

**Revises:** `007`

Add column to `devices`:

| Column | Type | Constraints |
|---|---|---|
| `location_id` | UUID | nullable, FK → `locations.id` ON DELETE RESTRICT |

**Rationale for ON DELETE RESTRICT (not SET NULL):** The service layer enforces the "block delete if devices exist" rule and returns a user-friendly 400 with device names. The DB constraint provides defense-in-depth — if a code path bypasses the service check, the DB will still refuse the delete rather than silently nullifying the FK. This matches the business invariant.

**Downgrade:** Drop FK constraint, drop column.

**DevOps-Engineer migration review required** (FK change on production table).

---

## 8. UI Pages

### 8.1 New file: `src/ui/pages/settings_locations.py`

**Route:** `/settings/locations`

**Page structure (NiceGUI):**
```
Page title: "Locations"
[+ Add Location] button — opens create modal

ui.table (columns: Name, Type, Rack, Row, Lat, Lng, Parent, Actions)
  — "Edit" icon button per row → opens edit modal pre-populated
  — "Delete" icon button per row → confirms then DELETE /api/locations/{id}

Modal state (shared create/edit):
  mode: "create" | "edit"
  location_id: Optional[uuid.UUID]   — None in create mode
  name: str
  type_toggle: LocationType          — drives field visibility below
  [if type == rack]:
    rack: str
    row: str
    parent_id: Optional[uuid.UUID]   — select from existing rack locations
  [if type == geo]:
    lat: str                         — rendered with monospace token; parsed to float on submit
    lng: str                         — same
  [Submit] / [Cancel] buttons
```

**Data flow:**
- Page load: `GET /api/locations/` → populate table.
- Type toggle change: swap visible form fields; clear fields that are hidden.
- Submit create: `POST /api/locations/` → on success, close modal, refresh table, show success toast.
- Submit edit: `PATCH /api/locations/{id}` → on success, close modal, refresh table, show success toast.
- Delete: confirmation dialog → `DELETE /api/locations/{id}` → on 400, show inline error (list of blocking device names from the API error detail) → on 204, refresh table.

**RBAC:** The "Add Location" button, Edit, and Delete actions are hidden (not just disabled) from `Role.Reader` users. Page itself is accessible to `Role.Reader`.

**Design tokens:** Coordinate fields (`lat`, `lng`) use the monospace font token. Rack/row fields use the standard font. Error styling uses `COLOR_ERROR`. No hardcoded colors.

### 8.2 New file: `src/ui/pages/inventory.py`

**Route:** `/inventory`

**Page structure (NiceGUI):**
```
Page title: "Inventory"
Search input (single line, placeholder "Search by name, IP, or notes…")
  — on_change: store search string; debounce 200ms before calling _apply_filters()

Filter bar: [DeviceType chips] | [Tag chips]
  — DeviceType chips: one per DeviceType enum value; toggle active/inactive
  — Tag chips: loaded from GET /api/tags/ (HT-006 dependency; hide bar section until HT-006 lands)
  — active_types: set[DeviceType] (Python state)
  — active_tag_ids: set[uuid.UUID] (Python state)

ui.table (virtual scroll enabled) OR ui.aggrid
  Columns: icon, name, type badge, IP, location name, tags, updated_at
  — icon: DeviceType → Material Icon name mapping (defined in tokens.py or inline dict)
  — type badge: colored chip using DEVICE_TYPE_COLORS mapping (add to tokens.py)
  — IP cell: monospace font; clipboard icon on hover
  — location cell: plain text (location_name from enriched response)
  — tags cell: small chips (HT-006 dependency; empty until then)
  — updated_at cell: human-readable relative time (e.g. "3 hours ago")

Row click: ui.navigate.to(f'/topology?device_id={device.id}')

Empty state (when filtered list is empty):
  "No devices match — try clearing filters"
  [Clear filters] button → resets search, active_types, active_tag_ids, calls _apply_filters()
```

**State management:**
```
_all_devices: list[DeviceResponseEnriched]  — loaded once on page load
_filtered: list[DeviceResponseEnriched]     — result of filter_devices(); bound to table
_search: str = ""
_active_types: set[DeviceType] = set()
_active_tag_ids: set[uuid.UUID] = set()
_debounce_timer: Optional[asyncio.TimerHandle] = None
```

**`_apply_filters()` method:** Calls `inventory_domain.filter_devices(_all_devices, _search, _active_types, _active_tag_ids)` and updates `_filtered`. Table refresh is driven by the reactive state binding.

**Debounce implementation:** On search input `on_change`, cancel the existing `_debounce_timer` if set, then schedule `_apply_filters()` via `asyncio.get_event_loop().call_later(0.2, _apply_filters)`. Store the handle in `_debounce_timer`.

**Column sorting:** Handled client-side by the NiceGUI `ui.table` `sort` prop or `ui.aggrid` `sortable=True` column config. No server round-trip needed.

**Data load:** On page load, call `GET /api/devices/?include=location&limit=1000`. Store raw response as `_all_devices`. Do NOT load all devices on every filter change.

**File size gate:** If `inventory.py` exceeds 250 lines, extract the filter bar (`DeviceType` chips + `Tag` chips + search input) into `src/ui/components/inventory_filter_bar.py`. The extracted component receives `on_change` callbacks for `search`, `active_types`, and `active_tag_ids`.

**Design tokens required in `src/ui/design/tokens.py`:**
- `DEVICE_TYPE_COLORS: dict[DeviceType, str]` — one color per device type for type badge chips. Add this mapping to `tokens.py`.
- `DEVICE_TYPE_ICONS: dict[DeviceType, str]` — Material Icon name per device type. Add to `tokens.py`.
- `FONT_MONO` constant — monospace font CSS value for IP/MAC cells. Add to `tokens.py`.

---

## 9. Security Boundaries

- `location_id` in `DeviceCreate` / `DeviceUpdate` is a UUID input from an authenticated API caller; it must be validated to reference an existing location (service-layer check in §5.2). Direct integer/sequential IDs are not used (UUIDs resist enumeration).
- Ancestor traversal in `get_ancestors` is depth-capped at 50 hops to prevent DoS via malicious deep chains.
- JWT/RBAC: all location mutations require `Role.Contributor` minimum; reads require `Role.Reader`. Same pattern as devices router — enforced via `Depends(require_role(...))` before handler executes.
- Coordinate values (`lat`, `lng`) are stored as `Float`, not raw strings. Validation in domain prevents injection of non-numeric payloads.
- Location names and rack/row fields are bounded (`max_length=255`/`64`) via SQLModel `Field`, mitigating oversized string storage.
- Nothing location-related needs to be excluded from logs — no PII is introduced. Device names shown in delete-block errors are acceptable (internal homelab context).

---

## 10. Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `src/models/location.py` | CREATE | Location SQLModel + all response schemas |
| `src/models/device.py` | MODIFY | Add `location_id` to `DeviceBase`; add `DeviceResponseEnriched`, `PaginatedDeviceResponseEnriched` |
| `src/domain/locations.py` | CREATE | `validate_location_fields`, `detect_cycle`, `validate_location_deletable` |
| `src/domain/inventory.py` | CREATE | `filter_devices` pure function |
| `src/repositories/location_repository.py` | CREATE | Full CRUD + `get_ancestors` + `get_devices_at_location` + `get_parent_map` |
| `src/repositories/device_repository.py` | MODIFY | Add `get_all_with_location` method |
| `src/services/location_service.py` | CREATE | Location CRUD service with all business rule enforcement |
| `src/services/device_service.py` | MODIFY | Add `get_all_enriched` + `_assert_location_exists` helper |
| `src/api/routers/locations.py` | CREATE | FastAPI router for `/api/locations` |
| `src/api/routers/devices.py` | MODIFY | Add `include` query param + raise `limit` cap to 1000 |
| `src/api/app.py` | MODIFY | Register locations router |
| `src/ui/design/tokens.py` | MODIFY | Add `DEVICE_TYPE_COLORS`, `DEVICE_TYPE_ICONS`, `FONT_MONO` |
| `src/ui/pages/settings_locations.py` | CREATE | Settings → Locations page (table + modal) |
| `src/ui/pages/inventory.py` | CREATE | `/inventory` page with virtual-scroll table + filter bar |
| `src/ui/components/inventory_filter_bar.py` | CREATE (conditional) | Extracted filter bar if `inventory.py` exceeds 250 lines |
| `alembic/versions/007_create_locations_table.py` | CREATE | PostgreSQL `locations` table + `location_type` enum |
| `alembic/versions/008_add_location_id_to_devices.py` | CREATE | Add `devices.location_id` FK → `locations.id` |
| `tests/unit/test_locations_domain.py` | CREATE | `validate_location_fields` (all error paths), `detect_cycle` (direct loop, indirect loop, valid chain, None parent), `validate_location_deletable` |
| `tests/unit/test_inventory_domain.py` | CREATE | `filter_devices` (empty search, type filter, tag filter, AND across categories, OR within, empty result) |
| `tests/integration/test_locations.py` | CREATE | CRUD API through FastAPI test client; covers 400s for bad create, delete-blocked-by-devices |
| `tests/integration/test_devices_include.py` | CREATE | `GET /api/devices/?include=location` returns `location_name`; backward compat without `include` param |

---

## 11. Dependency Graph

The build must proceed in this order. Items at the same level can be implemented in parallel.

```
Level 0 (no dependencies in this RFC):
  └─ src/models/types.py          ← already exists; LocationType already present; NO CHANGE

Level 1 (depends only on Level 0):
  ├─ src/models/location.py       ← new
  └─ alembic/versions/007_create_locations_table.py  ← new

Level 2 (depends on Level 1):
  ├─ alembic/versions/008_add_location_id_to_devices.py  ← depends on 007
  └─ src/models/device.py         ← add location_id (FK references locations table from 007)

Level 3 (depends on Level 1-2, pure functions only):
  ├─ src/domain/locations.py      ← depends on LocationType only
  └─ src/domain/inventory.py      ← depends on DeviceResponseEnriched (from Level 2)

Level 4 (depends on Level 1-3):
  ├─ src/repositories/location_repository.py   ← depends on Location model (Level 1)
  └─ src/repositories/device_repository.py     ← modify; depends on Location model (Level 1)

Level 5 (depends on Level 3-4):
  ├─ src/services/location_service.py   ← depends on domain + location_repository
  └─ src/services/device_service.py     ← modify; depends on device_repository + location_repository

Level 6 (depends on Level 5):
  ├─ src/api/routers/locations.py   ← depends on location_service
  └─ src/api/routers/devices.py     ← modify; depends on device_service enriched method

Level 7 (depends on Level 6):
  └─ src/api/app.py                 ← register locations router

Level 8 (depends on Level 6-7, requires running server):
  ├─ src/ui/design/tokens.py                      ← modify; add color/icon maps
  ├─ src/ui/pages/settings_locations.py           ← depends on locations router
  └─ src/ui/pages/inventory.py                    ← depends on enriched devices endpoint
      └─ src/ui/components/inventory_filter_bar.py  ← conditional extraction

Level 9 (can be written in parallel with Level 3+):
  ├─ tests/unit/test_locations_domain.py     ← pure function tests, no DB needed
  ├─ tests/unit/test_inventory_domain.py     ← pure function tests, no DB needed
  ├─ tests/integration/test_locations.py     ← requires Level 6
  └─ tests/integration/test_devices_include.py  ← requires Level 6
```

**Critical path:** `types.py` → `location.py` → migration 007 → migration 008 + `device.py` → repositories → services → routers → UI pages.

Unit tests at Level 9 (domain only) can be written and run as soon as Level 3 is complete — no migration or server needed. This allows TDD: write failing unit tests for `validate_location_fields` and `filter_devices` before implementing the domain functions.

---

## 12. Validation

| Constraint | Test |
|---|---|
| `validate_location_fields` rejects geo without lat/lng | `tests/unit/test_locations_domain.py::test_geo_requires_lat_lng` |
| `validate_location_fields` rejects rack with coordinates | `tests/unit/test_locations_domain.py::test_rack_no_coordinates` |
| `validate_location_fields` rejects lat > 90 | `tests/unit/test_locations_domain.py::test_lat_out_of_range` |
| `detect_cycle` catches direct self-loop | `tests/unit/test_locations_domain.py::test_direct_self_loop` |
| `detect_cycle` catches indirect cycle (A→B→A) | `tests/unit/test_locations_domain.py::test_indirect_cycle` |
| `detect_cycle` allows valid parent assignment | `tests/unit/test_locations_domain.py::test_valid_parent` |
| `filter_devices` search is case-insensitive | `tests/unit/test_inventory_domain.py::test_search_case_insensitive` |
| `filter_devices` AND across type + tag | `tests/unit/test_inventory_domain.py::test_and_across_categories` |
| `filter_devices` OR within types | `tests/unit/test_inventory_domain.py::test_or_within_types` |
| `filter_devices` empty type set = no type filter | `tests/unit/test_inventory_domain.py::test_empty_type_set_no_filter` |
| POST location with type=geo, no lat/lng → 400 | `tests/integration/test_locations.py::test_create_geo_missing_coords` |
| DELETE location with assigned devices → 400 | `tests/integration/test_locations.py::test_delete_blocked_by_devices` |
| GET /api/devices/?include=location returns location_name | `tests/integration/test_devices_include.py::test_include_location` |
| GET /api/devices/ without include is backward compatible | `tests/integration/test_devices_include.py::test_no_include_backward_compat` |
| All source files ≤ 250 lines | CI: `find src/ -name "*.py" | xargs wc -l` (test files exempt) |
| Type check | `docker compose exec api mypy src/ --ignore-missing-imports` |
| All tests pass | `docker compose exec api pytest` |
| Images build clean | `docker compose build` |
