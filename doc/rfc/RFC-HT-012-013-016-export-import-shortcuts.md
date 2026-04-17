# RFC: Export to JSON, Import from JSON, Canvas Keyboard Shortcuts

**Stories**: HT-012, HT-013, HT-016  
**Status**: DRAFT  
**Date**: 2026-04-10  
**Author**: Architect

---

## 1. Overview

This RFC covers three tightly-related quality-of-life additions:

- **HT-012** — `GET /api/export` produces a deterministic, streaming JSON snapshot of the entire database so homelabbers can back up their inventory in a portable, human-readable format.
- **HT-013** — `POST /api/import` destructively replaces all data from a previously-exported JSON file, enabling disaster-recovery and migration between Hometower instances.
- **HT-016** — Keyboard shortcuts on the Cytoscape.js canvas reduce mouse-only friction for power users managing large topologies.

HT-012 and HT-013 share a single schema definition (`ExportSchema`) that serialises the complete database graph preserving original UUIDs and insertion ordering. HT-016 is a purely front-end addition with no new API surface.

---

## 2. Parnas Information-Hiding Audit

Every new module must hide exactly one changeable design decision:

| Module | Decision hidden |
|---|---|
| `src/domain/export.py` | The canonical entity ordering, field-inclusion rules, and the version string for the export envelope — if we add versioned migrations or change field inclusion, only this file changes |
| `src/services/export_service.py` | Which repositories are queried, in what order, and how they are assembled into a dict — adapts if a new top-level entity is added without touching the router |
| `src/services/import_service.py` | The TRUNCATE-then-INSERT transaction strategy and the dependency-respecting delete/insert ordering — if we switch to soft-delete or upsert semantics, only this file changes |
| `src/api/routers/data_transfer.py` | The HTTP streaming/chunking strategy and the `Content-Disposition` header format — if we switch to chunked XHR or SSE streaming, only this router changes |
| `src/ui/pages/settings_data.py` | The Settings → Data UI layout and the file-picker + confirmation UX — if design tokens or layout change, only this page changes |
| `src/ui/components/canvas_shortcuts.py` | The keyboard shortcut key-code mapping and the `activeElement` guard logic — if we change which keys trigger which actions (e.g., add customisable hotkeys), only this file changes |

---

## 3. Data Model Changes

**No new database tables are required.**

### 3.1 `ExportSchema` — new Pydantic-only model (no `table=True`)

**File**: `src/models/export_schema.py` (new)

This module hides the canonical wire format for backup/restore. It is a pure Pydantic model that is never persisted — it is the contract between export and import.

```python
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from src.models.types import DeviceType, ConnectionType, LocationType, Role


# ── Nested record types (UUID-preserving, no password_hash) ─────────────────

class ExportedDevice(BaseModel):
    id: uuid.UUID
    name: str
    type: DeviceType
    ip: Optional[str]
    mac: Optional[str]
    os: Optional[str]
    notes: Optional[str]
    location_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

class ExportedConnection(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    type: ConnectionType
    label: Optional[str]
    created_at: datetime
    updated_at: datetime

class ExportedLocation(BaseModel):
    id: uuid.UUID
    name: str
    type: LocationType
    lat: Optional[float]
    lng: Optional[float]
    rack: Optional[str]
    row: Optional[str]
    parent_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

class ExportedTag(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    created_at: datetime
    updated_at: datetime

class ExportedDeviceTag(BaseModel):
    device_id: uuid.UUID
    tag_id: uuid.UUID

class ExportedCustomField(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    key: str
    value: str
    created_at: datetime
    updated_at: datetime

class ExportedDiagramLayout(BaseModel):
    id: uuid.UUID
    name: str
    cytoscape_json: str
    created_at: datetime
    updated_at: datetime

class ExportedUser(BaseModel):
    """password_hash is intentionally absent."""
    id: uuid.UUID
    username: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Envelope ─────────────────────────────────────────────────────────────────

class ExportSchema(BaseModel):
    version: str                          # must be "1.0"
    exported_at: datetime
    devices: list[ExportedDevice]
    connections: list[ExportedConnection]
    locations: list[ExportedLocation]
    tags: list[ExportedTag]
    device_tags: list[ExportedDeviceTag]
    custom_fields: list[ExportedCustomField]
    diagram_layouts: list[ExportedDiagramLayout]
    users: list[ExportedUser]
```

No Alembic migration is required. No `DevOps-Engineer migration review` needed for this story.

---

## 4. Domain Logic

**File**: `src/domain/export.py` (new)

This module hides the canonical export field-inclusion rules, entity sort order, and version string.  
It contains only pure functions — no SQLModel imports, no I/O.

```python
from datetime import datetime, timezone
from src.models.export_schema import (
    ExportSchema, ExportedDevice, ExportedConnection, ExportedLocation,
    ExportedTag, ExportedDeviceTag, ExportedCustomField, ExportedDiagramLayout,
    ExportedUser,
)
from src.models.device import Device
from src.models.connection import Connection
from src.models.location import Location
from src.models.tag import Tag, DeviceTag
from src.models.custom_field import CustomField
from src.models.diagram import DiagramLayout
from src.models.user import User

EXPORT_VERSION = "1.0"
SUPPORTED_VERSIONS = {"1.0"}


def build_export_envelope(
    devices: list[Device],
    connections: list[Connection],
    locations: list[Location],
    tags: list[Tag],
    device_tags: list[DeviceTag],
    custom_fields: list[CustomField],
    diagram_layouts: list[DiagramLayout],
    users: list[User],
) -> ExportSchema:
    """
    Build the canonical export envelope. Sorts every collection by created_at
    for deterministic output. Excludes password_hash from users.
    All arguments are in-memory SQLModel instances (no I/O performed here).
    """
    ...


def validate_export_version(version: str) -> None:
    """
    Raise ValueError("unsupported_version") if version is not in SUPPORTED_VERSIONS.
    Callers catch this and translate to HTTP 400.
    """
    ...


def _map_device(d: Device) -> ExportedDevice: ...
def _map_connection(c: Connection) -> ExportedConnection: ...
def _map_location(l: Location) -> ExportedLocation: ...
def _map_tag(t: Tag) -> ExportedTag: ...
def _map_device_tag(dt: DeviceTag) -> ExportedDeviceTag: ...
def _map_custom_field(cf: CustomField) -> ExportedCustomField: ...
def _map_diagram_layout(dl: DiagramLayout) -> ExportedDiagramLayout: ...
def _map_user(u: User) -> ExportedUser: ...
```

### Invariants enforced by `build_export_envelope`

- All collections sorted ascending by `created_at` (then `id` as tiebreaker) — guarantees byte-for-byte reproducible JSON for the same DB state.
- `ExportedUser.password_hash` does not exist; `User.password_hash` is never read by this function.
- Empty collections produce `[]`, not omitted keys.

---

## 5. Service Layer

### 5.1 Export Service

**File**: `src/services/export_service.py` (new)

This module hides which repositories are called and how their results are assembled. It owns no transaction (reads are safe without one in SQLModel/Postgres).

```python
from sqlmodel import Session
from src.models.export_schema import ExportSchema
from src.domain.export import build_export_envelope
from src.repositories import (
    device_repository,
    connection_repository,
    location_repository,
    tag_repository,
    custom_field_repository,
    diagram_repository,
    user_repository,
)


def build_full_export(session: Session) -> ExportSchema:
    """
    Calls get_all() on every repository and delegates assembly to the domain
    layer. Returns an ExportSchema ready for serialisation.
    Raises nothing — empty tables yield empty lists.
    """
    ...
```

**Note on DeviceTags**: `tag_repository` does not currently expose `get_all_device_tags()`. The service will need either:
- Option A (preferred): add `get_all_device_tags(session: Session) -> list[DeviceTag]` to `src/repositories/tag_repository.py` — a small, safe extension.
- Option B: use `select(DeviceTag)` inline within the service (violates the repository pattern).

**Feature-Engineer must implement Option A.**

### 5.2 Import Service

**File**: `src/services/import_service.py` (new)

This module hides the TRUNCATE-then-INSERT transaction strategy and the dependency order.

```python
from sqlmodel import Session, text
from src.models.export_schema import ExportSchema
from src.domain.export import validate_export_version


def import_full_snapshot(session: Session, payload: ExportSchema) -> None:
    """
    Destructively replaces all application data in a single transaction.

    Algorithm:
    1. validate_export_version(payload.version) — raises ValueError on mismatch
    2. TRUNCATE in reverse-dependency order with CASCADE:
         custom_fields, device_tags, connections, devices,
         diagram_layouts, locations, tags, users
    3. INSERT in forward-dependency order:
         users → locations → tags → devices → connections →
         device_tags → custom_fields → diagram_layouts
    4. On any constraint violation, the session rolls back automatically
       (caller wraps in try/except and re-raises as HTTP 422).

    Preconditions:
    - session is not yet committed (caller commits on success).
    - payload.version has been validated before calling.
    - imported users MUST NOT copy password_hash (ExportedUser lacks the field).
      Users are inserted with a fixed sentinel hash; they must reset passwords.
    """
    ...
```

#### Dependency-ordered TRUNCATE sequence

```sql
-- Reverse dependency order (children before parents)
TRUNCATE custom_fields      CASCADE;
TRUNCATE device_tags        CASCADE;  -- composite PK, no id col
TRUNCATE connections        CASCADE;
TRUNCATE devices            CASCADE;
TRUNCATE diagram_layouts    CASCADE;
TRUNCATE custom_fields      CASCADE;  -- already cleared, safe noop
TRUNCATE locations          CASCADE;
TRUNCATE tags               CASCADE;
TRUNCATE users              CASCADE;
```

Actual implementation must use `session.exec(text("TRUNCATE ... CASCADE"))` wrapped in the outer transaction.

#### Forward-dependency INSERT order

```
1. users           (no FK dependencies)
2. locations       (self-referencing parent_id → insert parents first)
3. tags            (no FK dependencies)
4. devices         (FK → locations)
5. connections     (FK → devices)
6. device_tags     (FK → devices, tags)
7. custom_fields   (FK → devices)
8. diagram_layouts (no FK dependencies)
```

**Location self-reference**: `Location.parent_id` is self-referential. The INSERT must order rows so parents precede children. The domain layer must expose a topological sort helper:

```python
# src/domain/export.py — additional pure function
def topological_sort_locations(
    locations: list[ExportedLocation],
) -> list[ExportedLocation]:
    """
    Returns locations sorted so every parent appears before its children.
    Raises ValueError("circular_location_reference") on a cycle.
    Pure function — no I/O.
    """
    ...
```

**User password sentinel**: Imported users have no password. Insert with `password_hash = IMPORT_SENTINEL_HASH` (a constant bcrypt hash of an unguessable 64-char random string that is generated once at module load and burned after use — effectively a locked account). Users must use password-reset flow to regain access.

```python
# src/services/import_service.py
import secrets, bcrypt
_SENTINEL = bcrypt.hashpw(secrets.token_bytes(64), bcrypt.gensalt()).decode()
```

This means imported users cannot log in until an Admin resets their password — this is the correct security default.

---

## 6. API Layer

**File**: `src/api/routers/data_transfer.py` (new)

This module hides the HTTP streaming strategy and `Content-Disposition` format.

```python
from fastapi import APIRouter, Depends, File, Query, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from src.models.types import Role
from src.domain.rbac import require_role
from src.utils.db import get_session
from src.services.export_service import build_full_export
from src.services.import_service import import_full_snapshot
from src.models.export_schema import ExportSchema

router = APIRouter(tags=["data-transfer"])

MAX_IMPORT_BYTES = 50 * 1024 * 1024  # 50 MB


@router.get(
    "/export",
    dependencies=[Depends(require_role(Role.Contributor))],
    summary="Export all data as JSON",
)
async def export_json(
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """
    Returns a streaming JSON download.
    Filename: hometower-export-YYYY-MM-DD.json
    Content-Type: application/json
    """
    ...


@router.post(
    "/import",
    dependencies=[Depends(require_role(Role.Admin))],
    status_code=204,
    summary="Destructive full import from JSON",
)
async def import_json(
    confirm: bool = Query(False),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> None:
    """
    Replaces ALL data from an uploaded JSON file.

    - confirm=true required; returns 400 otherwise.
    - File > 50 MB → 413.
    - Malformed JSON or unknown version → 400.
    - Constraint violation → 422 (full rollback).
    """
    ...
```

### Error response summary

| Condition | HTTP status | Detail |
|---|---|---|
| `confirm` not `true` | 400 | `"confirm=true is required for destructive import"` |
| File > 50 MB | 413 | `"Upload exceeds 50 MB limit"` |
| Malformed JSON | 400 | `"Invalid JSON"` |
| Unknown version | 400 | `"Unsupported export version: {v}"` |
| Pydantic validation failure | 422 | FastAPI default (field-level errors) |
| DB constraint violation | 422 | `"Import failed: {constraint detail}"` |

### Export streaming implementation note

```python
import json, io
from datetime import date

def _export_generator(data: ExportSchema):
    yield data.model_dump_json(indent=2)

filename = f"hometower-export-{date.today().isoformat()}.json"
return StreamingResponse(
    _export_generator(data),
    media_type="application/json",
    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
)
```

### Router registration

Feature-Engineer must add to `src/api/app.py`:

```python
from src.api.routers.data_transfer import router as data_transfer_router
app.include_router(data_transfer_router, prefix="/api")
```

---

## 7. UI Layer

### 7.1 Settings → Data Page

**File**: `src/ui/pages/settings_data.py` (new)

This module hides the Settings → Data layout and file-picker/confirmation UX.

```python
@ui.page("/settings/data")
async def settings_data_page(request: Request) -> None:
    """
    Renders the Settings → Data management page.
    Auth guard: Reader and above can see the page; Import button is Admin-only.
    Role is read from request.state.role.
    """
```

#### Layout specification

```
Settings → Data
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Export Data
  Generates a full JSON backup of all devices, connections,
  locations, tags, diagram layouts, and users.
  (Requires: Contributor or higher)

  [Export JSON]   ← ui.button, calls /api/export via anchor href

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Import Data        (visible to Admins only)
  ⚠ This will permanently replace ALL existing data.
  Upload a .json file previously exported from Hometower.

  [Choose file]  filename.json
  [Import JSON]  ← disabled until file selected; triggers confirmation modal

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### Export button behaviour

The Export button is a plain anchor `<a href="/api/export">` wrapped in a `ui.button` component — this avoids AJAX and lets the browser handle streaming download natively. The JWT token is forwarded via the cookie already present in same-origin requests (same port, NiceGUI + FastAPI co-process).

#### Import flow

1. `ui.upload` component (NiceGUI built-in) bound to a reactive `_file` variable.
2. "Import JSON" button enabled only when `_file is not None`.
3. On click: show `ui.dialog` confirmation modal:
   > "This will **permanently delete** all devices, connections, and diagram layouts. This cannot be undone. Type `CONFIRM` to proceed."
4. On user typing `CONFIRM` and clicking "Proceed": POST to `/api/import?confirm=true` with the file as multipart form data.
5. Show `ui.spinner` during upload. On success (HTTP 204): `ui.notify("Import complete — page will reload")` then `ui.navigate.reload()`. On error: `ui.notify(error_detail, type="negative")`.

#### Navigation integration

The existing Settings pages use `/settings/users` and `/settings/locations`. Feature-Engineer must add a "Data" link to the settings navigation wherever the other settings links appear (check `src/ui/pages/settings_users.py` for the nav pattern and replicate it).

---

### 7.2 Canvas Keyboard Shortcuts

**File**: `src/ui/components/canvas_shortcuts.py` (new)

This module hides the keyboard shortcut key-code mapping and the `activeElement` guard. It exposes a single Python function that injects the JS handler.

```python
def inject_canvas_shortcuts() -> None:
    """
    Injects the keyboard shortcut handler into the page via ui.add_body_html().
    Must be called from topology.py after render_canvas() and inject_canvas_events().
    """
```

#### Complete shortcut specification

| Key | Action | RBAC guard | JS implementation |
|---|---|---|---|
| `Delete` / `Backspace` | Delete selected node | Write — `HT_READONLY` check | Dispatch `ht:node-delete` on selected node |
| `Ctrl+D` / `Cmd+D` | Duplicate selected node | Write — `HT_READONLY` check | Dispatch `ht:node-duplicate` on selected node |
| `Ctrl+A` / `Cmd+A` | Select all nodes | Read | `window._cy.nodes().select()` |
| `Escape` | Deselect all / close detail panel | Read | `window._cy.nodes().unselect(); window._cy.edges().unselect();` then dispatch `ht:close-panel` |
| `Ctrl+Z` / `Cmd+Z` | Undo last position change | Write — `HT_READONLY` check | Restore from `_htUndoStack` (see §7.3) |
| `Ctrl+S` / `Cmd+S` | Save layout | Write — `HT_READONLY` check | `window.getCanvasJson()` then POST `/api/diagrams/{id}` |
| `F` | Fit all nodes | Read | `window._cy.fit()` |

#### `activeElement` guard (must precede all shortcuts)

```js
const tag = document.activeElement ? document.activeElement.tagName : '';
const isEditable = (
  tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' ||
  document.activeElement.isContentEditable
);
if (isEditable) return;
```

#### `Ctrl+S` browser-save suppression

```js
if ((e.ctrlKey || e.metaKey) && e.key === 's') {
  e.preventDefault();
  // ... save logic
}
```

#### `Ctrl+D` / `Cmd+D` bookmark suppression

```js
if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
  e.preventDefault();
  // ... duplicate logic
}
```

#### `Ctrl+A` / `Cmd+A` full-page select suppression

```js
if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
  e.preventDefault();
  // ... select-all logic
}
```

#### `ht:close-panel` event

Feature-Engineer must add a listener in `canvas_events.py` for `ht:close-panel` that hides the device detail panel (mirrors the existing close logic already called when a user clicks away from a node).

### 7.3 Undo State Management

**Single-level position undo.**

Cytoscape.js does not have a built-in undo stack. The existing `_htNodePositions` dict captures the *current* position of each node when it is moved (already live in `canvas.py`). The undo feature extends this to a one-deep stack:

```js
// Initialised once after cy is ready — inside _CANVAS_INIT_JS or canvas_shortcuts.py
window._htUndoStack = null;  // shape: { nodeId: string, prev: {x, y}, next: {x, y} } | null

// On node 'dragfree' (already handled in canvas.py):
window._cy.on('dragfree', 'node', function(evt) {
  const node = evt.target;
  const prev = window._htNodePositions[node.id()] || node.position();
  window._htUndoStack = { nodeId: node.id(), prev: prev, next: node.position() };
  window._htNodePositions[node.id()] = node.position();
});

// Undo handler (inside canvas_shortcuts.py JS):
if (window._htUndoStack) {
  const entry = window._htUndoStack;
  const node = window._cy.getElementById(entry.nodeId);
  if (node.length) {
    node.position(entry.prev);
    window._htNodePositions[entry.nodeId] = entry.prev;
  }
  window._htUndoStack = null;
}
```

**Scope**: Undo is position-only (drag moves). It does **not** undo node creation, deletion, or edge changes. This is explicitly documented in the UI via a tooltip: "Undo last node move (Ctrl+Z)".

**Integration**: The `dragfree` listener update (`_htUndoStack` assignment) must be added to `_CANVAS_INIT_JS` in `src/ui/components/canvas.py`. The undo restore runs inside `canvas_shortcuts.py`.

### 7.4 Toolbar Tooltip Integration

The canvas toolbar buttons (in `src/ui/components/canvas.py` or `topology.py`) must have shortcut hints added to their `tooltip` parameters. No structural changes to button layout — just add tooltip text:

| Button | Tooltip text |
|---|---|
| Save layout | "Save layout (Ctrl+S)" |
| Fit all | "Fit all nodes (F)" |
| Select all | "Select all (Ctrl+A)" |

Feature-Engineer should check `src/ui/components/canvas.py` for existing toolbar button definitions before adding tooltips.

### 7.5 Topology page integration

`canvas_shortcuts.py` exports one function: `inject_canvas_shortcuts()`. In `src/ui/pages/topology.py`, after the existing call to `inject_canvas_events()`:

```python
from src.ui.components.canvas_shortcuts import inject_canvas_shortcuts
# ...
inject_canvas_events()
inject_canvas_shortcuts()  # add this line
```

---

## 8. Security Boundaries

### 8.1 Export (`HT-012`)

- **RBAC**: `Contributor` minimum via `require_role(Role.Contributor)`. Readers cannot export.
- **No password_hash leakage**: `ExportedUser` model has no `password_hash` field. `build_export_envelope` never reads `User.password_hash`. This is structural — the type system prevents accidental inclusion.
- **Logging**: Do not log export payloads. Log only: `"Export requested by user_id={id}, record_counts={...}"`.

### 8.2 Import (`HT-013`)

- **RBAC**: `Admin` only via `require_role(Role.Admin)`. This is a destructive operation.
- **`confirm=true` required**: Prevents accidental trigger from misconfigured automation.
- **File size limit**: 50 MB enforced at the router before reading bytes. Use `await file.read(MAX_IMPORT_BYTES + 1)` and reject if `len(data) > MAX_IMPORT_BYTES` — do not stream unbounded data into memory.
- **No password_hash on import**: Even if a malicious JSON includes a `password_hash` field, `ExportedUser` drops it at Pydantic validation time.
- **Full rollback on constraint violation**: The session must not be committed if any insert raises. SQLModel/SQLAlchemy rolls back the session when an exception propagates through the `with session` context manager — the service relies on this.
- **Logging**: Log `"Import initiated by user_id={id}"` before the transaction and `"Import completed: {record_counts}"` after commit. Do not log payload contents.

### 8.3 Keyboard Shortcuts (`HT-016`)

- **`window.HT_READONLY`**: Write operations (`Delete`, `Ctrl+D`, `Ctrl+Z`, `Ctrl+S`) are silently skipped when `HT_READONLY === true`. This is already the pattern used by the context menu.
- **No new API surface**: Shortcuts dispatch the same custom DOM events (`ht:node-delete`, `ht:node-duplicate`, `ht:close-panel`) already handled by `canvas_events.py`. Security posture is unchanged.

---

## 9. Files to Create / Modify

| File | Action | Purpose |
|---|---|---|
| `src/models/export_schema.py` | **CREATE** | `ExportSchema` + 8 nested `Exported*` Pydantic models |
| `src/domain/export.py` | **CREATE** | `build_export_envelope`, `validate_export_version`, `topological_sort_locations`, `_map_*` helpers |
| `src/services/export_service.py` | **CREATE** | `build_full_export(session)` |
| `src/services/import_service.py` | **CREATE** | `import_full_snapshot(session, payload)` |
| `src/api/routers/data_transfer.py` | **CREATE** | `GET /api/export`, `POST /api/import` |
| `src/ui/pages/settings_data.py` | **CREATE** | Settings → Data page (export button, import file picker + confirmation modal) |
| `src/ui/components/canvas_shortcuts.py` | **CREATE** | `inject_canvas_shortcuts()` — JS keyboard shortcut handler |
| `src/repositories/tag_repository.py` | **MODIFY** | Add `get_all_device_tags(session: Session) -> list[DeviceTag]` |
| `src/ui/components/canvas.py` | **MODIFY** | Add `_htUndoStack` init + `dragfree` listener to `_CANVAS_INIT_JS` |
| `src/ui/pages/topology.py` | **MODIFY** | Call `inject_canvas_shortcuts()` after `inject_canvas_events()` |
| `src/api/app.py` | **MODIFY** | Register `data_transfer_router` |
| `src/ui/pages/settings_users.py` | **MODIFY** | Add "Data" navigation link alongside existing settings nav |

**Line-count check**: 
- `src/models/export_schema.py` ≈ 80 lines ✓
- `src/domain/export.py` ≈ 120 lines ✓  
- `src/services/export_service.py` ≈ 50 lines ✓
- `src/services/import_service.py` ≈ 120 lines ✓
- `src/api/routers/data_transfer.py` ≈ 90 lines ✓
- `src/ui/pages/settings_data.py` ≈ 130 lines ✓
- `src/ui/components/canvas_shortcuts.py` ≈ 100 lines ✓

All within the 250-line hard cap.

---

## 10. Test Plan

### 10.1 Unit tests — `src/domain/export.py`

**File**: `tests/unit/test_export_domain.py`

| Test | Assert |
|---|---|
| `test_build_export_envelope_sorts_by_created_at` | Devices with out-of-order `created_at` appear sorted ascending |
| `test_build_export_envelope_password_hash_absent` | `ExportedUser` instances have no `password_hash` attribute |
| `test_build_export_envelope_empty_collections` | All collection fields are `[]` when lists are empty |
| `test_validate_export_version_accepts_1_0` | No exception raised for `"1.0"` |
| `test_validate_export_version_rejects_unknown` | `ValueError` raised for `"2.0"`, `""`, `"1.1"` |
| `test_topological_sort_locations_parents_first` | Children always follow parents in output |
| `test_topological_sort_locations_cycle_raises` | `ValueError("circular_location_reference")` on cyclic data |
| `test_topological_sort_locations_single_node` | Single location with no parent returned unchanged |

### 10.2 Unit tests — `src/services/export_service.py`

**File**: `tests/unit/test_export_service.py`

Mock all repositories. Assert `build_full_export` calls each `get_all` exactly once and passes results to `build_export_envelope`.

### 10.3 Unit tests — `src/services/import_service.py`

**File**: `tests/unit/test_import_service.py`

| Test | Assert |
|---|---|
| `test_import_rejects_unknown_version` | `ValueError` propagates before any DB calls |
| `test_import_inserts_sentinel_hash` | Inserted `User.password_hash` is the sentinel, not a real password |
| `test_import_truncate_order` | Mock session captures SQL calls; TRUNCATE occurs before any INSERT |

### 10.4 Integration tests — export/import round-trip

**File**: `tests/integration/test_data_transfer.py`

| Test | Assert |
|---|---|
| `test_export_returns_json_with_correct_schema` | `GET /api/export` → 200, parseable as `ExportSchema`, `version == "1.0"` |
| `test_export_requires_contributor` | Reader role → 403 |
| `test_export_empty_db_returns_empty_arrays` | All collection fields are `[]` |
| `test_import_requires_admin` | Contributor role → 403 |
| `test_import_requires_confirm_true` | `POST /api/import` without `confirm=true` → 400 |
| `test_import_rejects_oversized_file` | 51 MB upload → 413 |
| `test_import_rejects_malformed_json` | `{"not": "valid schema"}` → 422 |
| `test_import_rejects_unknown_version` | `version: "99.0"` → 400 |
| `test_export_import_round_trip` | Export → wipe DB → Import → Export again → both exports are equal (excluding `exported_at`) |
| `test_import_rolls_back_on_constraint_violation` | Inject a duplicate UUID → 422, DB state unchanged |
| `test_import_users_have_sentinel_password` | After import, no user can authenticate with original password |

### 10.5 Canvas shortcuts — manual validation checklist

Keyboard shortcuts are JavaScript and cannot be tested with pytest. Feature-Engineer must document a manual test checklist in `tests/manual/canvas_shortcuts_checklist.md`:

- [ ] Delete/Backspace deletes selected node (with confirmation dialog appearing)
- [ ] Ctrl+D/Cmd+D duplicates selected node
- [ ] Ctrl+A selects all nodes; browser "select all" does not trigger
- [ ] Escape deselects; detail panel closes
- [ ] Ctrl+Z restores last dragged node to previous position
- [ ] Ctrl+Z does nothing when undo stack is empty
- [ ] Ctrl+S saves layout; browser save dialog does not appear
- [ ] F fits all nodes in viewport
- [ ] No shortcuts fire when focus is inside an INPUT or TEXTAREA
- [ ] All write shortcuts (Delete, Ctrl+D, Ctrl+Z, Ctrl+S) are no-ops for Reader role (`HT_READONLY = true`)
- [ ] Toolbar button tooltips show shortcut hints

---

## 11. Open Questions for Feature-Engineer

1. **Settings nav**: The current settings pages (`/settings/users`, `/settings/locations`) each render their own nav links independently. Feature-Engineer should check whether there is a shared nav component or if the link must be added to each page. If not shared, add the "Data" link to both `settings_users.py` and `settings_locations.py`.

2. **Diagram ID for Ctrl+S**: `window.getCanvasJson()` returns the JSON but the router for `PATCH /api/diagrams/{id}` requires a diagram ID. The topology page already knows the current diagram ID — Feature-Engineer must ensure it is injected into `window._htCurrentDiagramId` so the shortcut handler can use it. Verify this is already set in `src/ui/pages/topology.py`.

3. **`dragfree` listener placement**: The `_htUndoStack` augmentation to the `dragfree` listener must not duplicate the existing position-tracking logic in `_CANVAS_INIT_JS`. Feature-Engineer should read the existing `dragfree` handler carefully before modifying it.
