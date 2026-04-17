# RFC: Tags, Custom Fields, and Device Detail Panel (HT-006 / HT-007 / HT-010)

**Status:** Draft  
**Date:** 2026-04-10  
**Stories:** HT-006 (Tag System), HT-007 (Custom Fields), HT-010 (Device Detail Panel)  
**Downstream:** Feature-Engineer (implementation), UX-Designer (panel layout review)

---

## 1. Overview

This RFC covers three bundled stories that form one coherent vertical slice: two data-layer features (HT-006: tags, HT-007: custom fields) whose outputs are consumed by one UI feature (HT-010: device detail panel).

**Business value:** Homelabbers need ad-hoc metadata on devices — colored tags for grouping (e.g. "production", "DMZ") and arbitrary key-value fields for data that doesn't fit the fixed schema (e.g. "Serial: XYZ", "Wattage: 45W"). The detail panel makes all device metadata editable inline without navigating away, readable across topology, inventory, and map surfaces.

### Information-hiding decisions (Parnas)

| Module | Hidden design decision |
|---|---|
| `src/models/tag.py` | Tag/DeviceTag schema and join mechanics — swap to SQLModel `Relationship` without touching any other layer |
| `src/models/custom_field.py` | Custom field row storage strategy — swap to JSONB without touching any other layer |
| `src/repositories/tag_repository.py` | Join table query mechanics — add caching or bulk ops without touching any other layer |
| `src/repositories/custom_field_repository.py` | Custom field write strategy — add audit log without touching any other layer |
| `src/ui/components/device_detail_panel.py` | NiceGUI DOM rendering and JS event binding for the panel — swap NiceGUI without touching page files |

---

## 2. Data Model Changes

### 2.1 `src/models/tag.py` (new file)

```python
"""Tag and DeviceTag SQLModel definitions (HT-006)."""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

_HEX_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TagBase(SQLModel):
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(max_length=7)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #4f46e5")
        return v


class Tag(TagBase, table=True):
    __tablename__ = "tags"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)


class TagCreate(TagBase):
    pass


class TagUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    color: Optional[str] = Field(default=None, max_length=7)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #4f46e5")
        return v


class TagResponse(TagBase):
    id: uuid.UUID
    created_at: datetime


class TagWithCountResponse(TagResponse):
    device_count: int


class DeviceTag(SQLModel, table=True):
    __tablename__ = "device_tags"

    device_id: uuid.UUID = Field(
        foreign_key="devices.id", primary_key=True, ondelete="CASCADE"
    )
    tag_id: uuid.UUID = Field(
        foreign_key="tags.id", primary_key=True, ondelete="CASCADE"
    )
```

**Notes:**
- The `LOWER(name)` unique index is enforced at the DB level (see migration 009). The model does not enforce it; the domain `normalize_tag_name` function normalizes before insertion.
- `TagUpdate` uses `Optional` for all fields — same pattern as `DeviceUpdate`.
- `DeviceTag` has no `id` — composite PK on `(device_id, tag_id)` is the identity. `ondelete="CASCADE"` on both FKs.

### 2.2 `src/models/custom_field.py` (new file)

```python
"""CustomField SQLModel definitions (HT-007)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CustomFieldBase(SQLModel):
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(default="", max_length=1024)

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) == 0:
            raise ValueError("key must be at least 1 character after stripping whitespace")
        return stripped


class CustomField(CustomFieldBase, table=True):
    __tablename__ = "custom_fields"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class CustomFieldCreate(CustomFieldBase):
    pass


class CustomFieldUpdate(SQLModel):
    key: Optional[str] = Field(default=None, min_length=1, max_length=64)
    value: Optional[str] = Field(default=None, max_length=1024)

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if len(stripped) == 0:
                raise ValueError("key must be at least 1 character after stripping")
            return stripped
        return v


class CustomFieldResponse(CustomFieldBase):
    id: uuid.UUID
    device_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

**Notes:**
- The `(device_id, LOWER(key))` composite unique index is enforced at the DB level (migration 010).
- `key` is stripped of whitespace at both the Pydantic validator level AND the domain `normalize_custom_field_key` function (belt-and-suspenders).
- `device_id` FK on `CustomField` has `ondelete="CASCADE"` — deleting a device cascades to its custom fields.

### 2.3 `src/models/device.py` (modified)

Add to `DeviceResponseEnriched` — two new fields after existing `location_name`:

```python
# Add imports at top of file:
from src.models.tag import TagResponse
from src.models.custom_field import CustomFieldResponse

# Modified class:
class DeviceResponseEnriched(DeviceResponse):
    location_name: Optional[str] = None
    tags: list[TagResponse] = []
    custom_fields: list[CustomFieldResponse] = []
```

These fields default to empty lists so all existing callers that construct `DeviceResponseEnriched` remain valid without changes. They are populated only when requested via `?include=tags` or `?include=custom_fields`.

---

## 3. Migration Plan

### Migration 009: `alembic/versions/009_create_tags_and_device_tags.py`

```python
revision: str = "009"
down_revision: str = "008"
```

**`upgrade()` steps:**
1. `op.create_table("tags", ...)` — columns: `id UUID PK default gen_random_uuid()`, `name VARCHAR(64) NOT NULL`, `color VARCHAR(7) NOT NULL`, `created_at TIMESTAMPTZ NOT NULL default now()`
2. `op.create_index("ix_tags_name_lower", "tags", [sa.text("LOWER(name)")], unique=True)` — enforces case-insensitive uniqueness
3. `op.create_table("device_tags", ...)` — columns: `device_id UUID NOT NULL FK→devices.id ON DELETE CASCADE`, `tag_id UUID NOT NULL FK→tags.id ON DELETE CASCADE`; composite PK on `(device_id, tag_id)`

**`downgrade()` steps (reverse order):**
1. Drop `device_tags` table
2. Drop index `ix_tags_name_lower`
3. Drop `tags` table

### Migration 010: `alembic/versions/010_create_custom_fields.py`

```python
revision: str = "010"
down_revision: str = "009"
```

**`upgrade()` steps:**
1. `op.create_table("custom_fields", ...)` — columns: `id UUID PK default gen_random_uuid()`, `device_id UUID NOT NULL FK→devices.id ON DELETE CASCADE`, `key VARCHAR(64) NOT NULL`, `value VARCHAR(1024) NOT NULL DEFAULT ''`, `created_at TIMESTAMPTZ NOT NULL default now()`, `updated_at TIMESTAMPTZ NOT NULL default now()`
2. `op.create_index("ix_custom_fields_device_key_lower", "custom_fields", ["device_id", sa.text("LOWER(key)")], unique=True)` — enforces per-device case-insensitive key uniqueness

**`downgrade()` steps:**
1. Drop index `ix_custom_fields_device_key_lower`
2. Drop `custom_fields` table

> **DevOps-Engineer migration review required** for both migrations before first deploy. Confirm `gen_random_uuid()` is available in the target PostgreSQL version (requires pgcrypto or PG ≥ 13 — already used in migration 007).

---

## 4. Domain Layer Additions

**File:** `src/domain/inventory.py` (modified)

All functions are pure Python with zero I/O. The only permitted import is `from src.models.types import DeviceType` (unchanged). New additions use only the stdlib (`re`, `uuid`).

### 4.1 `normalize_tag_name(name: str) -> str`

```python
def normalize_tag_name(name: str) -> str:
    """Return the canonical form of a tag name: stripped and lowercased.

    Used before DB insert to prevent case-duplicate tags. The validator
    at the model level preserves the original casing for display; the
    unique index uses LOWER(name). Normalization here is for pre-existence
    checks in the service layer.
    """
    return name.strip().lower()
```

### 4.2 `normalize_custom_field_key(key: str) -> str`

```python
def normalize_custom_field_key(key: str) -> str:
    """Return the canonical form of a custom field key: stripped and lowercased.

    Used before duplicate checks. Model stores the original casing.
    """
    return key.strip().lower()
```

### 4.3 `validate_hex_color(color: str) -> str`

```python
import re as _re
_HEX_COLOR_RE = _re.compile(r'^#[0-9a-fA-F]{6}$')

def validate_hex_color(color: str) -> str:
    """Raise ValueError if color is not a 6-digit hex string.

    Returns the color unchanged on success. Callable from service layer
    for explicit validation before delegating to the model validator.
    """
    if not _HEX_COLOR_RE.match(color):
        raise ValueError(f"Invalid hex color: {color!r}. Expected #RRGGBB format.")
    return color
```

### 4.4 Tag filtering in `filter_devices`

The existing `filter_devices` function has a `tag_ids: set[uuid.UUID]` parameter that is currently a stub. After HT-006, implement the actual filter. The `FilterableDevice` Protocol gains a new structural attribute:

```python
import uuid
from typing import Protocol, Sequence, TypeVar

from src.models.types import DeviceType


class HasId(Protocol):
    id: uuid.UUID


class FilterableDevice(Protocol):
    name: str
    ip: str | None
    notes: str | None
    type: DeviceType
    tags: Sequence[HasId]  # NEW — populated when include=tags; empty list otherwise
```

Updated `filter_devices` tag logic (replaces the "silently ignored" comment):

```python
# Tag filter (OR within set — device must have at least one matching tag)
if tag_ids:
    device_tag_ids = {t.id for t in device.tags}
    if not device_tag_ids.intersection(tag_ids):
        continue
```

**Invariant:** A device with `tags=[]` fails the tag filter when `tag_ids` is non-empty. This is correct — if the user wants to filter by a tag, devices without any tags should not appear.

---

## 5. Repository Contracts

### 5.1 `src/repositories/tag_repository.py` (new file)

```python
def create(session: Session, tag: Tag) -> Tag: ...
def get_by_id(session: Session, tag_id: uuid.UUID) -> Tag | None: ...
def get_by_name_normalized(session: Session, normalized_name: str) -> Tag | None: ...
def get_all_with_counts(session: Session) -> list[tuple[Tag, int]]: ...
    # Returns (Tag, device_count) pairs, ordered by Tag.name ASC
    # COUNT via LEFT JOIN on device_tags grouped by tag.id
def update(session: Session, tag: Tag) -> Tag: ...
def delete(session: Session, tag: Tag) -> None: ...
    # ON DELETE CASCADE in DB handles device_tags rows
def attach_to_device(
    session: Session, device_id: uuid.UUID, tag_id: uuid.UUID
) -> None: ...
    # Idempotent: uses INSERT ... ON CONFLICT DO NOTHING on (device_id, tag_id) PK
def detach_from_device(
    session: Session, device_id: uuid.UUID, tag_id: uuid.UUID
) -> None: ...
    # No-op if association does not exist (no error)
def get_by_device(session: Session, device_id: uuid.UUID) -> list[Tag]: ...
    # JOIN device_tags ON tag.id = device_tags.tag_id WHERE device_tags.device_id = ?
    # Ordered by Tag.name ASC
```

**Key implementation note for `get_all_with_counts`:** Use SQLAlchemy `outerjoin` + `func.count(DeviceTag.tag_id)` grouped by `Tag.id`. Return `list[tuple[Tag, int]]` (not mixed dicts).

**Key implementation note for `attach_to_device`:** Use raw SQL `INSERT INTO device_tags ... ON CONFLICT (device_id, tag_id) DO NOTHING` for idempotency.

### 5.2 `src/repositories/custom_field_repository.py` (new file)

```python
def create(session: Session, cf: CustomField) -> CustomField: ...
def get_by_id(session: Session, cf_id: uuid.UUID) -> CustomField | None: ...
def get_by_device(session: Session, device_id: uuid.UUID) -> list[CustomField]: ...
    # All custom fields for a device, ordered by created_at ASC
def get_by_device_and_key_normalized(
    session: Session, device_id: uuid.UUID, normalized_key: str
) -> CustomField | None: ...
    # Used for duplicate-key detection. WHERE device_id=? AND LOWER(key)=?
def update(session: Session, cf: CustomField) -> CustomField: ...
def delete(session: Session, cf: CustomField) -> None: ...
```

### 5.3 `src/repositories/connection_repository.py` (modified)

Add new function for device-scoped connection lookup used by HT-010:

```python
def get_by_device(session: Session, device_id: uuid.UUID) -> list[Connection]: ...
    # WHERE source_id = device_id OR target_id = device_id
    # Ordered by created_at ASC
    # Uses: stmt.where(or_(Connection.source_id == device_id, Connection.target_id == device_id))
```

---

## 6. Service Layer

### 6.1 `src/services/tag_service.py` (new file)

```python
def create(data: TagCreate, session: Session) -> Tag:
    """Normalize name, validate color, check for duplicate (case-insensitive), persist."""
    # 1. normalize_tag_name → check tag_repository.get_by_name_normalized → 409 if exists
    # 2. validate_hex_color (domain) → ValueError → 422
    # 3. tag_repository.create

def get_all(session: Session) -> list[TagWithCountResponse]:
    """Return all tags with device counts."""
    # tag_repository.get_all_with_counts → build TagWithCountResponse

def get_by_id(tag_id: uuid.UUID, session: Session) -> Tag:
    """Return tag or raise HTTP 404."""

def update(tag_id: uuid.UUID, data: TagUpdate, session: Session) -> Tag:
    """Partial update; re-check case-insensitive name uniqueness if name changes."""
    # If name in update: normalize → get_by_name_normalized → 409 if different tag

def delete(tag_id: uuid.UUID, session: Session) -> None:
    """Delete tag; DB cascade removes device_tag rows."""

def attach_to_device(
    device_id: uuid.UUID, tag_id: uuid.UUID, session: Session
) -> None:
    """Idempotent attach: verify device exists (404), verify tag exists (404), attach."""

def detach_from_device(
    device_id: uuid.UUID, tag_id: uuid.UUID, session: Session
) -> None:
    """Detach tag from device. No-op if association does not exist."""

def get_by_device(device_id: uuid.UUID, session: Session) -> list[Tag]:
    """Return tags for device. Raises HTTP 404 if device not found."""
```

### 6.2 `src/services/custom_field_service.py` (new file)

```python
def create(
    device_id: uuid.UUID, data: CustomFieldCreate, session: Session
) -> CustomField:
    """Normalize key, check per-device uniqueness (409), persist."""
    # 1. normalize_custom_field_key → get_by_device_and_key_normalized → 409 if exists
    # 2. custom_field_repository.create with device_id set

def get_by_device(device_id: uuid.UUID, session: Session) -> list[CustomField]:
    """Return all custom fields for device. HTTP 404 if device not found."""

def update(
    device_id: uuid.UUID, cf_id: uuid.UUID, data: CustomFieldUpdate, session: Session
) -> CustomField:
    """Partial update; re-check key uniqueness if key changes.
    HTTP 404 if cf not found or doesn't belong to device_id."""

def delete(device_id: uuid.UUID, cf_id: uuid.UUID, session: Session) -> None:
    """Delete custom field. HTTP 404 if not found or wrong device."""
```

### 6.3 `src/services/device_service.py` (modified)

Extend `get_all_enriched` to support `"tags"` and `"custom_fields"` in the `include` set:

```python
def get_all_enriched(
    session: Session, page: int, limit: int, include: set[str]
) -> tuple[list[DeviceResponseEnriched], int]:
    # Existing: if "location" in include → get_all_with_location
    # New: if "tags" in include → for each device, call tag_repository.get_by_device
    # New: if "custom_fields" in include → for each device, call custom_field_repository.get_by_device
    # Both can be combined with location enrichment
```

Add new function for single-device enriched fetch (for HT-010 panel initial load):

```python
def get_by_id_enriched(
    device_id: uuid.UUID, session: Session, include: set[str]
) -> DeviceResponseEnriched:
    """Return a single device enriched with requested fields.
    HTTP 404 if not found. include may contain 'location', 'tags', 'custom_fields'."""
```

---

## 7. API Endpoints

### 7.1 Tags Router — `src/api/routers/tags.py` (new file)

`router = APIRouter(prefix="/tags", tags=["tags"])`

| Method | Path | Request Body | Response | Status | RBAC |
|---|---|---|---|---|---|
| `GET` | `/api/tags` | — | `list[TagWithCountResponse]` | 200 | Reader+ |
| `POST` | `/api/tags` | `TagCreate` | `TagResponse` | 201 | Contributor+ |
| `GET` | `/api/tags/{tag_id}` | — | `TagResponse` | 200 | Reader+ |
| `PATCH` | `/api/tags/{tag_id}` | `TagUpdate` | `TagResponse` | 200 | Contributor+ |
| `DELETE` | `/api/tags/{tag_id}` | — | — | 204 | Contributor+ |

Error cases:
- `POST /api/tags` with duplicate name (case-insensitive): 409 `{"detail": "Tag name already exists"}`
- `PATCH /api/tags/{id}` with duplicate name: 409
- `GET/PATCH/DELETE` on unknown tag_id: 404

### 7.2 Tag sub-routes on Devices Router — `src/api/routers/devices.py` (modified)

| Method | Path | Request Body | Response | Status | RBAC |
|---|---|---|---|---|---|
| `GET` | `/api/devices/{id}/tags` | — | `list[TagResponse]` | 200 | Reader+ |
| `POST` | `/api/devices/{id}/tags` | `DeviceTagAttach` | — | 204 | Contributor+ |
| `DELETE` | `/api/devices/{id}/tags/{tag_id}` | — | — | 204 | Contributor+ |

`DeviceTagAttach` schema (inline in devices router, no new file needed):
```python
class DeviceTagAttach(SQLModel):
    tag_id: uuid.UUID
```

`POST` is idempotent — attaching an already-attached tag returns 204 without error.

### 7.3 Custom Field sub-routes on Devices Router — `src/api/routers/devices.py` (modified)

| Method | Path | Request Body | Response | Status | RBAC |
|---|---|---|---|---|---|
| `GET` | `/api/devices/{id}/custom-fields` | — | `list[CustomFieldResponse]` | 200 | Reader+ |
| `POST` | `/api/devices/{id}/custom-fields` | `CustomFieldCreate` | `CustomFieldResponse` | 201 | Contributor+ |
| `PATCH` | `/api/devices/{id}/custom-fields/{cf_id}` | `CustomFieldUpdate` | `CustomFieldResponse` | 200 | Contributor+ |
| `DELETE` | `/api/devices/{id}/custom-fields/{cf_id}` | — | — | 204 | Contributor+ |

Error cases:
- `POST` with duplicate key (case-insensitive, per device): 409 `{"detail": "Custom field key already exists for this device"}`
- `PATCH` with key collision: 409
- Any operation on unknown device_id: 404
- `PATCH`/`DELETE` on cf_id not belonging to device_id: 404

### 7.4 Device Connections sub-route — `src/api/routers/devices.py` (modified)

| Method | Path | Request Body | Response | Status | RBAC |
|---|---|---|---|---|---|
| `GET` | `/api/devices/{id}/connections` | — | `list[ConnectionResponse]` | 200 | Reader+ |

Returns all connections where the device is source OR target.

### 7.5 Device Get-by-ID extended — `src/api/routers/devices.py` (modified)

The existing `GET /api/devices/{device_id}` currently returns `DeviceResponse` and accepts no `include` parameter. Modify its signature:

```python
@router.get("/{device_id}", dependencies=[Depends(require_role(Role.Reader))])
async def get_device(
    device_id: uuid.UUID,
    include: str = Query(default=""),
    session: Session = Depends(get_session),
) -> DeviceResponseEnriched | DeviceResponse:
```

When `include` is empty: returns `DeviceResponse` (unchanged behavior).  
When `include=tags,custom_fields` or any subset: returns `DeviceResponseEnriched` via `device_service.get_by_id_enriched`.

### 7.6 Router Registration — `src/api/app.py` (modified)

Add after the existing `locations_router` import and registration:

```python
from src.api.routers.tags import router as tags_router
# ...
app.include_router(tags_router, prefix="/api")
```

---

## 8. Device Response Extension

### DeviceResponseEnriched field additions

```python
class DeviceResponseEnriched(DeviceResponse):
    location_name: Optional[str] = None
    tags: list[TagResponse] = []           # populated when include=tags
    custom_fields: list[CustomFieldResponse] = []  # populated when include=custom_fields
```

### include set semantics (updated for device_service)

| include value | What is populated |
|---|---|
| `""` (empty) | nothing enriched |
| `"location"` | `location_name` |
| `"tags"` | `tags` list |
| `"custom_fields"` | `custom_fields` list |
| `"location,tags,custom_fields"` | all three |

The service layer fetches tags and custom_fields with per-device fan-out queries (N+1 acceptable at this scale; homelabs are small). If performance becomes a concern, Architect will design a batch-join approach under a separate RFC.

### Inventory page FilterableDevice protocol update

The `FilterableDevice` protocol in `src/domain/inventory.py` gains a `tags: Sequence[HasId]` field. `DeviceResponseEnriched.tags` satisfies this structurally since `TagResponse` has an `id: uuid.UUID` field. Existing tests pass because the protocol match is structural — existing test fixtures without `tags` need `tags: []` added.

---

## 9. UI Component Design (HT-010)

### 9.1 File structure

Two files to stay within the 250-line cap:

**`src/ui/components/device_detail_panel.py`** (~200 lines) — main panel shell  
**`src/ui/components/device_detail_sections.py`** (~200 lines) — Tags, Custom Fields, Connections sections  

The existing `src/ui/components/device_detail.py` is modified to call `render_detail_panel()` from `device_detail_panel.py` (thin redirect). Its JS-only logic is removed; Python handles state.

### 9.2 `device_detail_panel.py` structure

```
render_detail_panel(token: str, user_role: Role) -> None
  │
  ├─ panel container (role="complementary", id="device-detail-panel", display:none)
  │    ├─ header row: "Device Info" label + close button
  │    ├─ identity_section: name (inline-editable), type, IP (inline-editable), MAC, OS
  │    ├─ location_section: location_name (read-only)
  │    ├─ notes_section: notes (textarea inline-editable)
  │    ├─ tags_section → imported from device_detail_sections
  │    ├─ custom_fields_section → imported from device_detail_sections
  │    └─ connections_section → imported from device_detail_sections
  │
  └─ JS listener for ht:node-selected event → calls Python via ui.run_javascript bridge
```

**State:** panel holds a `state: dict` with `device_id`, `device` (DeviceResponseEnriched), and `is_editor: bool` derived from `user_role`.

**Panel activation flow:**
1. `ht:node-selected` DOM event fires with `{id, label, device_type, ip, mac, os, notes}`
2. JS bridge calls Python async handler `_on_node_selected(device_id: str)`
3. Handler calls `GET /api/devices/{id}?include=tags,custom_fields` with the stored JWT
4. Panel shows via `panel_container.set_visibility(True)` and populates sections

**Inline edit pattern (for name, ip, mac, os, notes):**
- Each field renders as a `ui.label` with a pencil icon button (Contributor only)
- Click pencil → replace label with `ui.input` pre-filled with current value, confirm/cancel icons
- Confirm → `PATCH /api/devices/{id}` with changed field, update local state, re-render label
- Cancel → restore label without API call
- Reader role: pencil icon is not rendered (not hidden — absent)

**Panel RBAC:**
```python
is_editor: bool = user_role in {Role.Admin, Role.Contributor}
```
Passed down to all section renderers; controls whether add/edit/delete buttons are rendered.

### 9.3 `device_detail_sections.py` structure

```python
def render_tags_section(
    device_id: uuid.UUID,
    tags: list[TagResponse],
    all_tags: list[TagResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    """Chips row; Contributor sees an 'Add tag' dropdown and × on each chip."""
    # Each tag: ui.chip with background=tag.color, text-color auto-contrast
    # is_editor: × button calls DELETE /api/devices/{id}/tags/{tag_id}
    # is_editor: 'Add tag' select calls POST /api/devices/{id}/tags

def render_custom_fields_section(
    device_id: uuid.UUID,
    fields: list[CustomFieldResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    """Key-value table with inline edit; Contributor sees edit/delete per row and 'Add field' form."""
    # Each row: key label : value label + edit pencil + delete trash (is_editor only)
    # 'Add field' row: key input + value input + submit (is_editor only)
    # Edit → inline replace with inputs, PATCH /api/devices/{id}/custom-fields/{cf_id}
    # Delete → DELETE /api/devices/{id}/custom-fields/{cf_id}

def render_connections_section(
    device_id: uuid.UUID,
    connections: list[ConnectionResponse],
    token: str,
) -> None:
    """List of connection entries; each shows neighbor device name as a link."""
    # Connections loaded via GET /api/devices/{id}/connections called from panel init
    # Each entry: [type icon] ↔ [neighbor name] → ui.link to /topology?device_id={neighbor}
    # Determine neighbor: if conn.source_id == device_id → neighbor is conn.target_id
```

**`on_change` callback:** passed to tags/fields sections; re-fetches device and re-renders the section. Keeps the panel state in sync without a full page reload.

### 9.4 Accessibility requirements

- Panel container: `role="complementary"` (landmark)  
- Tags area: `aria-label="Device tags"`  
- Custom fields area: `aria-label="Custom fields"`  
- Inline edit inputs: `aria-label="Edit {field_name}"`  
- Connections area: `aria-label="Connections"`  
- Status updates (tag added/removed, field saved): `aria-live="polite"` region  
- Keyboard: all interactive elements reachable via Tab; close button is first focusable element in panel; inline edit Escape cancels

Implementation: NiceGUI `.props("role=complementary")` and `.props("aria-label='...'")` applied to container elements. Aria-live region implemented as a hidden `ui.label` with `.props("aria-live='polite'")`; its text is set transiently on mutations.

### 9.5 Inventory page updates — `src/ui/pages/inventory.py` (modified)

The tags column in `_build_rows` currently returns `"—"` stub. After HT-006:

```python
# In _build_rows:
"tags": ", ".join(t["name"] for t in d.tags) if d.tags else "—",
```

The URL for `_load_devices` adds `tags` to the include param:
```python
params={"include": "location,tags", "limit": "1000"}
```

The `DeviceResponseEnriched` now has `tags: list[TagResponse]` which must be populated for tag filtering in `filter_devices` to work.

Tag chip filter bar (currently type-only) gains tag chips — rendered after the type chips using the `all_tags` fetched from `GET /api/tags`. This is a separate call at page load. `state["tag_ids"]` is already wired into `filter_devices`.

---

## 10. Files to Create/Modify

### New files

| File | Purpose |
|---|---|
| `src/models/tag.py` | Tag, DeviceTag, TagCreate, TagUpdate, TagResponse, TagWithCountResponse, DeviceTagAttach |
| `src/models/custom_field.py` | CustomField, CustomFieldCreate, CustomFieldUpdate, CustomFieldResponse |
| `src/repositories/tag_repository.py` | Tag and DeviceTag DB queries |
| `src/repositories/custom_field_repository.py` | CustomField DB queries |
| `src/services/tag_service.py` | Tag CRUD and device-tag attach/detach orchestration |
| `src/services/custom_field_service.py` | Custom field CRUD orchestration |
| `src/api/routers/tags.py` | CRUD endpoints for `GET/POST/PATCH/DELETE /api/tags` |
| `src/ui/components/device_detail_panel.py` | Full NiceGUI device detail panel |
| `src/ui/components/device_detail_sections.py` | Tags, Custom Fields, Connections section renderers |
| `alembic/versions/009_create_tags_and_device_tags.py` | Migration: tags + device_tags tables |
| `alembic/versions/010_create_custom_fields.py` | Migration: custom_fields table |

### Modified files

| File | Change |
|---|---|
| `src/models/device.py` | Add `tags` and `custom_fields` fields to `DeviceResponseEnriched`; add imports of `TagResponse`, `CustomFieldResponse` |
| `src/domain/inventory.py` | Add `normalize_tag_name`, `normalize_custom_field_key`, `validate_hex_color`; extend `FilterableDevice` protocol with `tags`; implement tag filter in `filter_devices` |
| `src/services/device_service.py` | Extend `get_all_enriched` for tags/custom_fields; add `get_by_id_enriched` |
| `src/repositories/connection_repository.py` | Add `get_by_device(session, device_id)` |
| `src/api/routers/devices.py` | Add HT-006/007 sub-routes; extend `GET /{device_id}` with `include`; register `DeviceTagAttach` |
| `src/api/app.py` | Import and register `tags_router` |
| `src/ui/components/device_detail.py` | Replace JS-only implementation with thin call to `device_detail_panel.render_detail_panel()` |
| `src/ui/pages/inventory.py` | Add tag chips to filter bar; populate tags in `_build_rows`; extend `_load_devices` include param |

---

## 11. Validation

| Test file | What it validates |
|---|---|
| `tests/unit/test_inventory_domain.py` (new) | `normalize_tag_name`, `normalize_custom_field_key`, `validate_hex_color`, tag filter in `filter_devices` |
| `tests/unit/test_tag_model.py` (new) | `TagBase` color validator, `CustomFieldBase` key validator |
| `tests/unit/test_tag_service.py` (new) | duplicate-name 409, attach idempotency, detach no-op |
| `tests/unit/test_custom_field_service.py` (new) | per-device key uniqueness 409, wrong-device 404 |
| `tests/integration/test_tags.py` (new) | Full CRUD + attach/detach round-trip against DB |
| `tests/integration/test_custom_fields.py` (new) | Full CRUD round-trip against DB |
| `tests/integration/test_devices.py` (existing, modified) | `GET /api/devices/{id}?include=tags,custom_fields` returns enriched response |

**Fitness functions:**
- `normalize_tag_name("  Production  ") == "production"` — domain test
- `normalize_custom_field_key("  Serial Number  ") == "serial number"` — domain test
- `validate_hex_color("#GGGGGG")` raises `ValueError` — domain test
- `attach_to_device` called twice with same IDs results in exactly one row in device_tags — integration test
- `filter_devices` with `tag_ids={some_id}` on a device with `tags=[]` returns empty list — domain test
- `DELETE /api/tags/{id}` cascades: device_tags rows are removed, `GET /api/devices/{id}/tags` returns `[]` — integration test
- `DELETE /api/devices/{id}` cascades: custom_fields rows are removed — integration test

---

## 12. Security Boundaries

- All write operations require Contributor or Admin role — enforced via `Depends(require_role(Role.Contributor))` per the existing pattern in `src/api/middleware/auth.py`
- Tag names, colors, custom field keys and values are rendered in the NiceGUI UI through NiceGUI's own text-setting mechanisms (not raw innerHTML injection) — no XSS surface
- Device detail panel loads device data by UUID; panel does not accept arbitrary device data from untrusted JS events — the `ht:node-selected` JS event provides only the `device_id`, the Python handler re-fetches from the API with the stored server-side token
- Custom field `value` is stored as plain VARCHAR — no eval, no template rendering
- Tag `color` is validated to `^#[0-9a-fA-F]{6}$` before storage — cannot be used to inject CSS `expression()` or `url()` payloads; applied only as inline `background-color` in chip rendering
