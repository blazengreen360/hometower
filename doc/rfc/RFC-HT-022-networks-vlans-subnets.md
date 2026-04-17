# RFC: Networks, VLANs, and Subnets

**Story:** HT-022  
**Status:** Ready for Implementation  
**Date:** 2026-04-13  
**Author:** Architect

---

## 0. Architecture Decision Summary

- Add a first-class `Network` entity plus a `DeviceNetwork` join table. `Device.ip` stays as the primary/convenience IP only; `DeviceNetwork` becomes the authoritative multi-homed view.
- Keep `DeviceType.VLAN` and `DeviceType.Subnet` deprecated, not removed, in HT-022. Do not attempt a lossy auto-conversion migration from legacy devices into networks.
- Put network semantics in `src/domain/networks.py` and `src/services/network_service.py`. Models only enforce shape, length, and color format; CIDR/VLAN/business-rule errors must return HTTP 400 from the service layer.
- Extend the existing `include=` enrichment contract on device reads instead of creating parallel read endpoints. `GET /api/devices/{id}?include=networks` and `GET /api/devices/?include=networks` are the canonical device-side reads.
- Ship minimal but complete UI for this story: Settings CRUD for networks, device-detail association management, inventory network badges, and topology sidebar/highlighting.
- Extend export/import in the same story so full snapshots preserve networks and memberships.

**Decision on legacy pseudo-network device types:**

- `DeviceType.VLAN` and `DeviceType.Subnet` remain in `src/models/types.py` and in the PostgreSQL enum.
- They remain renderable everywhere existing devices already appear.
- They are hidden from new device-creation affordances in UI creation flows.
- They are not removed from the DB enum in HT-022 because PostgreSQL enum value removal is invasive and current legacy device rows do not contain a reliable source for mandatory `cidr` data.

---

## 1. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/models/network.py` | The network schema and wire contract for network CRUD. |
| `src/models/device_network.py` | How device-to-network membership is stored and represented on the wire. |
| `src/domain/networks.py` | CIDR/IP/VLAN validation and canonicalisation rules. |
| `src/repositories/network_repository.py` | SQLModel join/query mechanics for networks plus memberships. |
| `src/services/network_service.py` | Transaction boundaries and HTTP error mapping for network workflows. |
| `src/ui/components/network_filter_panel.py` | The topology-sidebar presentation of selectable networks. |
| `src/ui/components/canvas_js_networks.py` | The client-side overlay strategy for multi-network highlights and stacked badges. |
| `src/ui/pages/settings_networks.py` | The CRUD screen flow for networks without leaking API details into other pages. |
| `src/ui/components/device_detail_networks_section.py` | The device-side membership editor UI. |

---

## 2. Data Model Changes

### 2.1 New file: `src/models/network.py`

```python
"""Network SQLModel definitions (HT-022)."""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from src.models.device_network import DeviceNetworkDeviceRef

_HEX_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NetworkBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    vlan_id: Optional[int] = Field(default=None)
    cidr: str = Field(min_length=3, max_length=64)
    gateway: Optional[str] = Field(default=None, max_length=45)
    description: Optional[str] = Field(default=None, max_length=1000)
    color: str = Field(max_length=7)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be empty or whitespace-only")
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #3b82f6")
        return v


class Network(NetworkBase, table=True):
    __tablename__ = "networks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class NetworkCreate(NetworkBase):
    pass


class NetworkUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    vlan_id: Optional[int] = Field(default=None)
    cidr: Optional[str] = Field(default=None, min_length=3, max_length=64)
    gateway: Optional[str] = Field(default=None, max_length=45)
    description: Optional[str] = Field(default=None, max_length=1000)
    color: Optional[str] = Field(default=None, max_length=7)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("name cannot be empty or whitespace-only")
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _HEX_COLOR_PATTERN.match(v):
            raise ValueError("color must be a 6-digit hex color, e.g. #3b82f6")
        return v


class NetworkResponse(NetworkBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class NetworkListResponse(NetworkResponse):
    device_count: int = 0


class NetworkResponseEnriched(NetworkResponse):
    devices: list[DeviceNetworkDeviceRef] = []
```

**Notes:**

- No `version` field on `Network`. Match `Location`, `Tag`, and `Service` semantics: last write wins.
- Do **not** put CIDR/VLAN/gateway business-rule validators in the model. Those errors must map to HTTP 400, so they belong in the service layer via `src/domain/networks.py`.

### 2.2 New file: `src/models/device_network.py`

```python
"""Device-network membership models (HT-022)."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

from src.models.types import DeviceStatus, DeviceType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeviceNetwork(SQLModel, table=True):
    __tablename__ = "device_networks"

    device_id: uuid.UUID = Field(
        foreign_key="devices.id", primary_key=True, ondelete="CASCADE"
    )
    network_id: uuid.UUID = Field(
        foreign_key="networks.id", primary_key=True, ondelete="CASCADE"
    )
    ip_address: str = Field(max_length=45)
    created_at: datetime = Field(default_factory=_utcnow)


class DeviceNetworkCreate(SQLModel):
    network_id: uuid.UUID
    ip_address: str = Field(max_length=45)


class DeviceNetworkResponse(SQLModel):
    device_id: uuid.UUID
    network_id: uuid.UUID
    ip_address: str
    created_at: datetime


class DeviceNetworkNetworkRef(SQLModel):
    network_id: uuid.UUID
    name: str
    vlan_id: int | None = None
    cidr: str
    gateway: str | None = None
    color: str
    ip_address: str


class DeviceNetworkDeviceRef(SQLModel):
    device_id: uuid.UUID
    name: str
    type: DeviceType
    status: DeviceStatus
    ip_address: str
```

**Notes:**

- `ip_address` is required on the join model. HT-024 owns IPAM/conflict detection; HT-022 only validates syntax and subnet membership.
- No update schema is added for memberships. HT-022 only needs create/list/delete; changing a membership IP is delete-then-create.

### 2.3 Modified file: `src/models/device.py`

```diff
@@
-from src.models.service import ServiceResponse
+from src.models.service import ServiceResponse
+from src.models.device_network import DeviceNetworkNetworkRef
@@
 class DeviceResponseEnriched(DeviceResponse):
     location_name: Optional[str] = None
     tags: list[TagResponse] = []
     custom_fields: list[CustomFieldResponse] = []
     services: list[ServiceResponse] = []
+    networks: list[DeviceNetworkNetworkRef] = []
     children: list[DeviceResponse] = []
     parent_chain: list[DeviceResponse] = []
```

### 2.4 Modified file: `src/models/export_schema.py`

```diff
@@
+class ExportedNetwork(BaseModel):
+    id: uuid.UUID
+    name: str
+    vlan_id: Optional[int] = None
+    cidr: str
+    gateway: Optional[str] = None
+    description: Optional[str] = None
+    color: str
+    created_at: datetime
+    updated_at: datetime
+
+
+class ExportedDeviceNetwork(BaseModel):
+    device_id: uuid.UUID
+    network_id: uuid.UUID
+    ip_address: str
+    created_at: datetime
@@
 class ExportSchema(BaseModel):
     version: str
     exported_at: datetime
     devices: list[ExportedDevice]
     connections: list[ExportedConnection]
     locations: list[ExportedLocation]
     tags: list[ExportedTag]
     device_tags: list[ExportedDeviceTag]
+    networks: list[ExportedNetwork] = []
+    device_networks: list[ExportedDeviceNetwork] = []
     custom_fields: list[ExportedCustomField]
     services: list[ExportedService] = []
```

**Export/import compatibility decision:** keep export version at `1.0`; new arrays default to `[]` so older snapshots continue to import.

---

## 3. Migration Plan

**Alembic migration required:** yes  
**DevOps-Engineer review required:** yes  
**Migration file:** `alembic/versions/024_create_networks_and_device_networks.py`

### 3.1 Migration operations

```python
"""024 - create networks and device_networks tables (HT-022).

Additive migration only.
No enum rewrite.
No lossy VLAN/Subnet device conversion.
"""

def upgrade() -> None:
    op.create_table(
        "networks",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("cidr", sa.String(64), nullable=False),
        sa.Column("gateway", sa.String(45), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_check_constraint(
        "ck_networks_vlan_range",
        "networks",
        "vlan_id IS NULL OR (vlan_id BETWEEN 1 AND 4094)",
    )
    op.create_index("ix_networks_name_lower", "networks", [sa.text("lower(name)")], unique=True)
    op.create_index("ix_networks_vlan_id", "networks", ["vlan_id"])

    op.create_table(
        "device_networks",
        sa.Column("device_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("network_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["network_id"], ["networks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id", "network_id"),
    )
    op.create_index("ix_device_networks_network_id", "device_networks", ["network_id"])


def downgrade() -> None:
    op.drop_index("ix_device_networks_network_id", table_name="device_networks")
    op.drop_table("device_networks")
    op.drop_index("ix_networks_vlan_id", table_name="networks")
    op.drop_index("ix_networks_name_lower", table_name="networks")
    op.drop_constraint("ck_networks_vlan_range", "networks", type_="check")
    op.drop_table("networks")
```

### 3.2 Migration decisions

- No destructive rewrite of `device_type` enum in HT-022.
- No attempt to convert existing `Device(type in {'VLAN', 'Subnet'})` rows into `Network` rows.
- Reason: current legacy rows do not carry a reliable mandatory `cidr`, and auto-conversion would be lossy and diagram-breaking.
- UI deprecation is sufficient for this story; data cleanup belongs in a later migration with explicit user-visible rules.

### 3.3 Online-safety assessment

- Safe: additive new tables only.
- Safe: no `ALTER COLUMN type_=` and no enum removal.
- Safe: no hot-table NOT NULL rewrite.
- Required verification: run `bash .claude/skills/migration-safety/scripts/check.sh alembic/versions/024_create_networks_and_device_networks.py` after the migration is written.

---

## 4. Domain Logic

**New file:** `src/domain/networks.py`

```python
def normalize_network_name(name: str) -> str:
    """Return canonical name for duplicate checks: stripped + lowercased."""


def validate_vlan_id(vlan_id: int | None) -> int | None:
    """Return vlan_id or raise ValueError('VLAN ID must be between 1 and 4094')."""


def validate_cidr(cidr: str) -> str:
    """Return canonical CIDR string or raise ValueError('Invalid CIDR notation')."""


def validate_ip_address(ip_address: str) -> str:
    """Return canonical IPv4/IPv6 string or raise ValueError('Invalid IP address format')."""


def validate_gateway(gateway: str | None, cidr: str) -> str | None:
    """Return canonical gateway or raise ValueError when invalid or outside subnet."""


def validate_ip_in_subnet(ip_address: str, cidr: str) -> None:
    """Raise ValueError(f'IP {ip} is not within subnet {cidr}') when out of range."""
```

**Implementation rules:**

- Use only the Python standard-library `ipaddress` module.
- `validate_cidr` must use `strict=True`; `10.0.10.5/24` is invalid input for this story.
- `validate_gateway` and `validate_ip_in_subnet` must reject IP family mismatches (`IPv4` IP with `IPv6` CIDR and vice versa).

---

## 5. Repository Layer

**New file:** `src/repositories/network_repository.py`

```python
def create(session: Session, network: Network) -> Network
def get_by_id(session: Session, network_id: uuid.UUID) -> Network | None
def get_by_name_normalized(session: Session, normalized_name: str) -> Network | None
def get_all_with_counts(session: Session) -> list[tuple[Network, int]]
def update(session: Session, network: Network) -> Network
def delete(session: Session, network: Network) -> None
def get_by_device(session: Session, device_id: uuid.UUID) -> list[tuple[Network, str]]
def get_by_device_ids(session: Session, device_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[tuple[Network, str]]]
def get_device_refs(session: Session, network_id: uuid.UUID) -> list[tuple[Device, str]]
def get_memberships_for_network(session: Session, network_id: uuid.UUID) -> list[DeviceNetwork]
def get_membership(session: Session, device_id: uuid.UUID, network_id: uuid.UUID) -> DeviceNetwork | None
def attach_to_device(session: Session, membership: DeviceNetwork) -> DeviceNetwork
def detach_from_device(session: Session, device_id: uuid.UUID, network_id: uuid.UUID) -> None
def count_devices(session: Session, network_id: uuid.UUID) -> int
def get_all_for_export(session: Session) -> list[Network]
def get_all_device_networks(session: Session) -> list[DeviceNetwork]
```

**Repository rules:**

- Use `session.flush()`, never `commit()`.
- `get_all_with_counts()` should order by `vlan_id NULLS LAST, name ASC` for operator-friendly UI ordering.
- `attach_to_device()` should do a normal insert, not upsert; duplicate membership must surface as HTTP 409.

---

## 6. Service Layer

**New file:** `src/services/network_service.py`

```python
def create(data: NetworkCreate, session: Session) -> Network
def get_all(session: Session) -> list[NetworkListResponse]
def get_by_id(network_id: uuid.UUID, session: Session) -> Network
def get_by_id_enriched(network_id: uuid.UUID, include: set[str], session: Session) -> NetworkResponseEnriched | NetworkResponse
def update(network_id: uuid.UUID, data: NetworkUpdate, session: Session) -> Network
def delete(network_id: uuid.UUID, session: Session) -> None
def get_by_device(device_id: uuid.UUID, session: Session) -> list[DeviceNetworkNetworkRef]
def attach_to_device(device_id: uuid.UUID, data: DeviceNetworkCreate, session: Session) -> DeviceNetwork
def detach_from_device(device_id: uuid.UUID, network_id: uuid.UUID, session: Session) -> None
```

### 6.1 Service rules

- `create()` and `update()` must call `normalize_network_name`, `validate_vlan_id`, `validate_cidr`, and `validate_gateway` before repository writes.
- `attach_to_device()` must:
  - 404 if device does not exist.
  - 404 if network does not exist.
  - validate IP syntax.
  - validate IP is inside the network CIDR.
  - return 409 if `(device_id, network_id)` already exists.
- `update()` must block CIDR changes that invalidate existing memberships.

### 6.2 Error mapping

| Condition | HTTP |
|---|---|
| Invalid CIDR | `400 Invalid CIDR notation` |
| Invalid VLAN range | `400 VLAN ID must be between 1 and 4094` |
| Gateway outside subnet | `400 Gateway <ip> is not within subnet <cidr>` |
| Membership IP outside subnet | `400 IP <ip> is not within subnet <cidr>` |
| Duplicate network name (case-insensitive) | `409 Network name already exists` |
| Duplicate device-network membership | `409 Device is already on this network` |
| Delete network with members | `400 Network has devices assigned - remove them first` |
| Network not found | `404 Network not found` |
| Device not found on membership operations | `404 Device not found` |

### 6.3 Modified file: `src/services/device_enrichment_service.py`

```diff
@@
-from src.repositories import (
+from src.repositories import (
     custom_field_repository,
     device_repository,
     location_repository,
+    network_repository,
     service_repository,
     tag_repository,
 )
@@
-    """Attach include=tags/custom_fields/services data using batched repository reads."""
+    """Attach include=tags/custom_fields/services/networks data using batched repository reads."""
@@
+    if "networks" in include:
+        nets_by_device = network_repository.get_by_device_ids(session, device_ids)
+        for item in items:
+            raw_nets = nets_by_device.get(item.id, [])
+            item.networks = [
+                DeviceNetworkNetworkRef(
+                    network_id=network.id,
+                    name=network.name,
+                    vlan_id=network.vlan_id,
+                    cidr=network.cidr,
+                    gateway=network.gateway,
+                    color=network.color,
+                    ip_address=ip_address,
+                )
+                for network, ip_address in raw_nets
+            ]
@@
-    """Return enriched device list. Supports include={'location', 'tags', 'custom_fields', 'services'}."""
+    """Return enriched device list. Supports include={'location', 'tags', 'custom_fields', 'services', 'networks'}."""
@@
+    if "networks" in include:
+        raw_nets = network_repository.get_by_device(session, device_id)
+        enriched.networks = [
+            DeviceNetworkNetworkRef(
+                network_id=network.id,
+                name=network.name,
+                vlan_id=network.vlan_id,
+                cidr=network.cidr,
+                gateway=network.gateway,
+                color=network.color,
+                ip_address=ip_address,
+            )
+            for network, ip_address in raw_nets
+        ]
```

---

## 7. API Layer

### 7.1 New file: `src/api/routers/networks.py`

| Method | Path | Request model | Response model | Required role |
|---|---|---|---|---|
| `GET` | `/api/networks/` | none | `list[NetworkListResponse]` | `Reader` |
| `POST` | `/api/networks/` | `NetworkCreate` | `NetworkResponse` | `Contributor` |
| `GET` | `/api/networks/{network_id}` | `include: str = ""` | `NetworkResponse` or `NetworkResponseEnriched` | `Reader` |
| `PATCH` | `/api/networks/{network_id}` | `NetworkUpdate` | `NetworkResponse` | `Contributor` |
| `DELETE` | `/api/networks/{network_id}` | none | `204` | `Contributor` |

`GET /api/networks/{network_id}?include=devices` is the canonical network-side read for device membership.

### 7.2 Modified file: `src/api/routers/device_sub_routes.py`

| Method | Path | Request model | Response model | Required role |
|---|---|---|---|---|
| `GET` | `/api/devices/{device_id}/networks` | none | `list[DeviceNetworkNetworkRef]` | `Reader` |
| `POST` | `/api/devices/{device_id}/networks` | `DeviceNetworkCreate` | `DeviceNetworkResponse` | `Contributor` |
| `DELETE` | `/api/devices/{device_id}/networks/{network_id}` | none | `204` | `Contributor` |

### 7.3 Modified file: `src/api/routers/devices.py`

```diff
@@
-    Pass ?include=location to enrich with location names.
+    Pass ?include=location,tags,services,networks to enrich with related data.
@@
-    """Get a device by ID. Pass ?include=tags,location to enrich the response."""
+    """Get a device by ID. Pass ?include=tags,location,services,networks to enrich the response."""
```

### 7.4 Modified file: `src/api/app.py`

```diff
@@
+from src.api.routers.networks import router as networks_router
@@
+app.include_router(networks_router, prefix="/api")
```

### 7.5 Request/response shapes

**Create network**

```http
POST /api/networks/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Management",
  "vlan_id": 10,
  "cidr": "10.0.10.0/24",
  "gateway": "10.0.10.1",
  "description": "Management traffic",
  "color": "#3b82f6"
}
```

```json
{
  "id": "<uuid>",
  "name": "Management",
  "vlan_id": 10,
  "cidr": "10.0.10.0/24",
  "gateway": "10.0.10.1",
  "description": "Management traffic",
  "color": "#3b82f6",
  "created_at": "2026-04-13T12:00:00Z",
  "updated_at": "2026-04-13T12:00:00Z"
}
```

**Attach device to network**

```http
POST /api/devices/{device_id}/networks
Authorization: Bearer <token>
Content-Type: application/json

{
  "network_id": "<uuid>",
  "ip_address": "10.0.10.5"
}
```

```json
{
  "device_id": "<uuid>",
  "network_id": "<uuid>",
  "ip_address": "10.0.10.5",
  "created_at": "2026-04-13T12:05:00Z"
}
```

**Device enriched read**

```http
GET /api/devices/{device_id}?include=networks
```

```json
{
  "id": "<device uuid>",
  "name": "core-router",
  "type": "Router",
  "ip": "10.0.10.1",
  "networks": [
    {
      "network_id": "<uuid>",
      "name": "Management",
      "vlan_id": 10,
      "cidr": "10.0.10.0/24",
      "gateway": "10.0.10.1",
      "color": "#3b82f6",
      "ip_address": "10.0.10.1"
    }
  ]
}
```

**Network enriched read**

```http
GET /api/networks/{network_id}?include=devices
```

```json
{
  "id": "<network uuid>",
  "name": "Management",
  "vlan_id": 10,
  "cidr": "10.0.10.0/24",
  "gateway": "10.0.10.1",
  "description": "Management traffic",
  "color": "#3b82f6",
  "devices": [
    {
      "device_id": "<uuid>",
      "name": "core-router",
      "type": "Router",
      "status": "Active",
      "ip_address": "10.0.10.1"
    }
  ]
}
```

---

## 8. UI Layer

### 8.1 Settings CRUD

**New file:** `src/ui/pages/settings_networks.py`

- Route: `/settings/networks`
- Guard: authenticated + `Contributor` and above
- Layout pattern: same as `settings_locations.py`
- API base: `/api/networks/` with trailing slash
- Table columns: `name`, `vlan_id`, `cidr`, `gateway`, `device_count`, `actions`
- Actions: create, edit, delete
- Delete dialog copy must mirror backend rule: if devices are assigned, deletion is blocked and the page shows the API error detail

**New file:** `src/ui/components/network_modal.py`

- Modal fields: `name`, `vlan_id`, `cidr`, `gateway`, `description`, `color`
- Validation UX: display backend error detail inline; do not duplicate CIDR logic in JS
- Color UX: show a small swatch preview next to the hex input, but keep the source of truth as the hex string

**Modified file:** `src/ui/components/sidebar.py`

```diff
@@
 _SETTINGS_ITEMS: list[dict[str, str]] = [
     {"label": "Locations", "route": "/settings/locations", "icon": "location_on"},
+    {"label": "Networks", "route": "/settings/networks", "icon": "lan"},
     {"label": "Users", "route": "/settings/users", "icon": "people", "admin_only": "true"},
```

**Modified file:** `src/main.py`

```diff
@@
+from src.ui.pages import settings_networks  # noqa: F401 - registers /settings/networks page
```

### 8.2 Device-detail association management

**New file:** `src/ui/components/device_detail_networks_section.py`

- Render current memberships as color chips with: `name`, optional `VLAN <id>`, and `ip_address`
- Editors get:
  - attach dialog with `network_id` select + `ip_address` input
  - remove button per membership
- Readers get read-only labels only

**Modified file:** `src/ui/components/device_detail_sections.py`

```diff
@@
+from src.ui.components.device_detail_networks_section import render_networks_section
@@
+    "render_networks_section",
```

**Modified file:** `src/ui/components/device_detail_container.py`

```diff
@@
+from src.models.network import NetworkListResponse
@@
+async def _api_get_all_networks(token: str) -> list[NetworkListResponse]:
+    ... GET /api/networks/ ...
```

**Modified file:** `src/ui/components/device_detail_panel.py`

```diff
@@
-            token, did, include="location,tags,custom_fields,children,ancestors"
+            token, did, include="location,tags,custom_fields,children,ancestors,networks"
@@
-        all_tags = await _api_get_all_tags(token) if is_editor else []
+        all_tags = await _api_get_all_tags(token) if is_editor else []
+        all_networks = await _api_get_all_networks(token) if is_editor else []
@@
+            with ui.expansion("Networks", icon="lan", value=True).classes("w-full"):
+                with ui.element("div").props('aria-label="Device networks"').classes("w-full"):
+                    render_networks_section(
+                        did,
+                        device.networks,
+                        all_networks,
+                        token,
+                        is_editor,
+                        _on_change,
+                    )
```

**Important canvas sync rule:** after attach/detach succeeds, the refresh flow should call a JS bridge like `htUpsertNodeNetworks(deviceId, networks)` so the currently loaded Cytoscape node data updates without a full page reload.

### 8.3 Inventory integration

**Modified file:** `src/ui/pages/inventory.py`

```diff
@@
-            params: dict[str, str] = {"include": "location,tags,services", "limit": "1000"}
+            params: dict[str, str] = {"include": "location,tags,services,networks", "limit": "1000"}
```

**Modified file:** `src/ui/pages/inventory_table.py`

```diff
@@
+    {"name": "networks", "label": "Networks", "field": "networks", "sortable": False, "align": "left"},
@@
+  <q-td key="networks" :props="props">
+    <q-chip
+      v-for="network in (props.row.networks || [])"
+      :key="network.id"
+      dense
+      square
+      text-color="white"
+      :style="'background:' + network.color"
+      class="q-mr-xs q-mb-xs"
+    >{{ network.label }}</q-chip>
+    <span v-if="!props.row.networks || props.row.networks.length === 0" style="color:var(--ht-text-secondary)">-</span>
+  </q-td>
@@
+            "networks": [
+                {"id": str(n.network_id), "label": n.name, "color": n.color}
+                for n in d.networks
+            ] if d.networks else [],
```

### 8.4 Topology sidebar and canvas highlighting

**Modified file:** `src/ui/services/topology_data.py`

```diff
@@
-                    params={"page": devices_page, "limit": page_limit},
+                    params={"page": devices_page, "limit": page_limit, "include": "networks"},
@@
+                device_elem_data["network_memberships"] = [
+                    {
+                        "network_id": str(item.get("network_id", "")),
+                        "name": str(item.get("name", "")),
+                        "color": str(item.get("color", "")),
+                        "ip_address": str(item.get("ip_address", "")),
+                    }
+                    for item in device.get("networks", [])
+                    if isinstance(item, dict)
+                ]
```

Add a second helper in the same file:

```python
async def load_network_summaries(token: str) -> list[dict[str, object]]:
    """Fetch /api/networks/ for topology sidebar consumption."""
```

**New file:** `src/ui/components/network_filter_panel.py`

- Render a collapsible left-rail panel below the stencils panel.
- Show one row per network with color swatch, name, optional `VLAN <id>`, and a checkbox/toggle.
- On toggle, call `ui.run_javascript("htSetActiveNetworks(...)")`.

**New file:** `src/ui/components/canvas_js_networks.py`

Public JS entrypoints:

```javascript
window.htSetActiveNetworks = function(networkIds) { ... }
window.htUpsertNodeNetworks = function(deviceId, memberships) { ... }
```

Responsibilities:

- Maintain `window._htActiveNetworkIds`
- Add/remove `network-highlight` class on nodes with active memberships
- Set inline border/underlay colour from the first active network
- Render stacked colour dots in an absolutely positioned overlay container anchored to rendered node positions
- Re-render on `render`, `pan`, `zoom`, `add`, `remove`, and membership updates

**Modified file:** `src/ui/components/canvas.py`

```diff
@@
+from src.ui.components.canvas_js_networks import CANVAS_NETWORKS_JS
@@
-    ui.add_body_html(f"<script>{canvas_js}</script>")
+    ui.add_body_html(f"<script>{canvas_js}</script>")
+    ui.add_body_html(f"<script>{CANVAS_NETWORKS_JS}</script>")
@@
-        with ui.element("div").props('id="cy"').style(
+        with ui.element("div").props('id="cy"').style(
             "width: 100%; height: 100%; background-color: var(--ht-bg-base);"
         ):
             pass
+        ui.element("div").props('id="ht-network-badges"').style(
+            "position:absolute; inset:0; pointer-events:none; z-index:20;"
+        )
```

**Modified file:** `src/ui/components/canvas_js.py`

- Append `CANVAS_NETWORKS_JS` to the existing init bundle or inject it separately from `canvas.py`.
- On initial canvas creation, call `window.htSetActiveNetworks([])` so the overlay is initialised even before the first toggle.

**Modified file:** `src/ui/components/canvas_styles.py`

```diff
@@
+    styles.append({
+        "selector": "node.network-highlight",
+        "style": {
+            "border-width": 4,
+            "underlay-opacity": 0.18,
+            "underlay-padding": 6,
+        },
+    })
```

**Modified file:** `src/ui/pages/topology.py`

**Structural decision:** the left rail must be visible in both view mode and edit mode.

- `render_palette()` stays edit-only.
- `render_stencils_panel()` becomes always visible.
- `render_networks_panel()` is always visible below stencils.
- `HT_READONLY` still prevents writes; dragging from the stencil panel in view mode remains harmless because the drop handler already checks `HT_READONLY`.

```diff
@@
-from src.ui.services.topology_data import load_canvas_data
+from src.ui.services.topology_data import load_canvas_data, load_network_summaries
+from src.ui.components.network_filter_panel import render_networks_panel
@@
+    networks = await load_network_summaries(token)
@@
-            palette_container = ui.element("div").style(
+            left_rail = ui.element("div").style(
                 "flex-shrink: 0; overflow-y: auto; display: flex;"
                 " flex-direction: row; max-height: 100%;"
             )
-            palette_container.set_visibility(False)
-            _refs["palette"] = palette_container
-            if role != Role.Reader:
-                with palette_container:
-                    render_palette()
-                    render_stencils_panel(stencil_devices, placed_ids)
+            with left_rail:
+                palette_container = ui.element("div")
+                palette_container.set_visibility(False)
+                _refs["palette"] = palette_container
+                if role != Role.Reader:
+                    with palette_container:
+                        render_palette()
+                render_stencils_panel(stencil_devices, placed_ids)
+                render_networks_panel(networks)
```

### 8.5 Legacy pseudo-network device-type deprecation in creation UI

**Modified files:**

- `src/ui/components/device_palette.py`
- `src/ui/components/canvas_zoom.py`
- `src/ui/pages/device_edit.py`

Rule:

- Exclude `DeviceType.VLAN` and `DeviceType.Subnet` from new-device creation affordances.
- If editing an existing legacy device on `/inventory/edit/{device_id}`, keep its current value in the select so the edit page does not force a type change.
- Do not remove legacy types from inventory filters, topology rendering, or existing records.

---

## 9. Security Boundaries

- Read operations stay `Reader+`; create/update/delete/associate stay `Contributor+`.
- The topology Networks panel is read-only UI state. It must never imply write permission.
- UI hides attach/remove controls for Readers, but API RBAC remains the real enforcement.
- Avoid logging raw `ip_address`, `gateway`, or `cidr` in success logs. Log IDs and names only.
- Export redaction rules stay unchanged for `Device.ip`; network CIDRs and membership IPs are inventory data, not auth secrets. Do not add them to logs anyway.

---

## 10. Edge Cases and Validations

| Category | Decision |
|---|---|
| Empty state | `/settings/networks` shows an empty-state message and create button. Device detail shows `No networks`. Inventory shows `-` in the Networks column. Topology panel renders with zero rows and no errors. |
| Boundary values | Accept VLAN `1` and `4094`; reject `0` and `4095+`. Accept IPv4 and IPv6 CIDRs. Reject host-address CIDRs via `strict=True`. Accept `gateway=None`. Max lengths: `name 255`, `cidr 64`, `gateway 45`, `description 1000`, `color 7`. |
| Concurrent access | `Network` uses last-write-wins like `Location`. Duplicate-name and duplicate-membership races are closed by repository lookup plus DB uniqueness/PK handling. |
| Cascade effects | Deleting a device cascades its `device_networks` rows via FK. Deleting a network through the API is blocked while memberships exist. DB cascade remains present for device deletion and import cleanup. |
| RBAC per operation | Reader: list/read networks, read device memberships, use topology highlight panel, see inventory badges. Contributor/Admin: CRUD networks and attach/detach memberships. |
| Round-trip integrity | Export/import includes `networks` and `device_networks`. Older snapshots import with empty arrays. |
| Canvas impact | Node data gains `network_memberships`. Highlight/badge JS must ignore draft nodes and tolerate nodes with zero memberships. |
| Performance at scale | Device enrichment must batch network lookups via `get_by_device_ids()`. Topology overlay redraw must use one pass over visible nodes and a single overlay container. The settings page remains cheap because network counts are small. |

**Additional update invariant:** if a network CIDR is changed and any existing membership IP falls outside the new CIDR, the update must fail with HTTP 400. This preserves model consistency.

---

## 11. Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `alembic/versions/024_create_networks_and_device_networks.py` | Create | Add `networks` and `device_networks` tables and indexes. |
| `src/models/network.py` | Create | Network table plus CRUD response schemas. |
| `src/models/device_network.py` | Create | Membership table plus device/network ref schemas. |
| `src/models/device.py` | Modify | Add `networks` to `DeviceResponseEnriched`. |
| `src/models/export_schema.py` | Modify | Add `ExportedNetwork`, `ExportedDeviceNetwork`, and export arrays. |
| `src/domain/networks.py` | Create | Pure network validation and canonicalisation logic. |
| `src/repositories/network_repository.py` | Create | Query and membership persistence layer. |
| `src/services/network_service.py` | Create | Orchestrate network CRUD and membership rules. |
| `src/services/device_enrichment_service.py` | Modify | Support `include=networks` batched enrichment. |
| `src/services/export_service.py` | Modify | Export networks and memberships. |
| `src/services/import_service.py` | Modify | Import networks and memberships, update table clear order and counts. |
| `src/services/import_validation.py` | Modify | Validate `device_networks` references and subnet consistency. |
| `src/api/routers/networks.py` | Create | Network CRUD and `include=devices` endpoint. |
| `src/api/routers/device_sub_routes.py` | Modify | Add device-network list/create/delete endpoints. |
| `src/api/routers/devices.py` | Modify | Document and support `include=networks`. |
| `src/api/app.py` | Modify | Register `networks_router`. |
| `src/ui/pages/settings_networks.py` | Create | Settings CRUD page for networks. |
| `src/ui/components/network_modal.py` | Create | Reusable create/edit modal for networks. |
| `src/ui/components/sidebar.py` | Modify | Add `/settings/networks` nav entry. |
| `src/main.py` | Modify | Register the new settings page. |
| `src/ui/components/device_detail_networks_section.py` | Create | Membership editor/viewer in the device detail panel. |
| `src/ui/components/device_detail_sections.py` | Modify | Export `render_networks_section`. |
| `src/ui/components/device_detail_container.py` | Modify | Add `_api_get_all_networks()`. |
| `src/ui/components/device_detail_panel.py` | Modify | Load/render device network memberships and push canvas membership updates. |
| `src/ui/pages/inventory.py` | Modify | Fetch `include=networks`. |
| `src/ui/pages/inventory_table.py` | Modify | Add Networks column with color badges. |
| `src/ui/services/topology_data.py` | Modify | Load device `include=networks` and topology network summaries. |
| `src/ui/components/network_filter_panel.py` | Create | Topology sidebar network toggles. |
| `src/ui/components/canvas_js_networks.py` | Create | Node highlight and stacked badge overlay logic. |
| `src/ui/components/canvas.py` | Modify | Inject network JS and overlay container. |
| `src/ui/components/canvas_js.py` | Modify | Initialise network overlay hooks. |
| `src/ui/components/canvas_styles.py` | Modify | Add `network-highlight` selector. |
| `src/ui/pages/topology.py` | Modify | Show left rail in both modes and render network panel. |
| `src/ui/components/device_palette.py` | Modify | Hide deprecated pseudo-network device types from new creation. |
| `src/ui/components/canvas_zoom.py` | Modify | Hide deprecated pseudo-network device types from the help modal tools. |
| `src/ui/pages/device_edit.py` | Modify | Hide deprecated pseudo-network types except when editing a legacy device. |
| `tests/conftest.py` | Modify | Register `Network` and `DeviceNetwork` tables for SQLite tests. |
| `tests/unit/test_networks_domain.py` | Create | CIDR/IP/VLAN validation boundary cases. |
| `tests/unit/test_network_service.py` | Create | Service-level CIDR-change blocking, conflict mapping, delete blocking. |
| `tests/unit/test_device_service_enrichment.py` | Modify | Assert batched network enrichment and no N+1 per-device network fetches. |
| `tests/unit/test_topology_data.py` | Modify | Verify `include=networks` topology loading and element membership payloads. |
| `tests/unit/test_inventory_helpers.py` | Modify | Verify Networks column/badge row-building. |
| `tests/integration/test_networks_api.py` | Create | Full CRUD, RBAC, include-contract, conflict, and association tests. |
| `tests/integration/test_export.py` | Modify | Assert `networks` and `device_networks` keys export correctly. |
| `tests/integration/test_import.py` | Modify | Assert import/export round-trip preserves networks and memberships. |
| `CHANGELOG.md` | Modify | Add `[Unreleased]` entry when implementation lands. |

---

## 12. Test Plan

### Unit tests

- `tests/unit/test_networks_domain.py`
  - valid IPv4 CIDR
  - valid IPv6 CIDR
  - invalid CIDR
  - VLAN lower/upper bounds
  - VLAN out-of-range
  - gateway outside subnet
  - IP outside subnet
- `tests/unit/test_network_service.py`
  - duplicate case-insensitive name returns 409
  - CIDR update blocked when existing membership IPs fall outside new subnet
  - delete blocked when memberships exist
- `tests/unit/test_device_service_enrichment.py`
  - `include=networks` uses `network_repository.get_by_device_ids()` and not per-device lookups
- `tests/unit/test_topology_data.py`
  - device fetch sends `include=networks`
  - node element data includes `network_memberships`
  - malformed network payloads are ignored safely
- `tests/unit/test_inventory_helpers.py`
  - Networks column exists
  - row builder emits network badge payloads

### Integration tests

- `tests/integration/test_networks_api.py`
  - create success
  - invalid CIDR returns 400
  - invalid VLAN returns 400
  - duplicate case-insensitive name returns 409
  - update success
  - update CIDR rejected when existing member IP no longer fits
  - delete empty network returns 204
  - delete network with members returns 400
  - attach membership success
  - attach duplicate membership returns 409
  - attach out-of-subnet IP returns 400
  - `GET /api/devices/{id}?include=networks` returns network refs
  - `GET /api/networks/{id}?include=devices` returns device refs
  - RBAC: Reader read-only, Contributor write allowed
- `tests/integration/test_export.py`
  - export includes `networks` and `device_networks` arrays
  - created network + membership appear in export payload
- `tests/integration/test_import.py`
  - import accepts older payloads without `networks` keys
  - round-trip preserves network UUIDs and device-network rows
  - dangling `device_networks` refs return 422

### Fixtures

- Reuse existing `session`, `client`, `admin_token`, `contributor_token`, `reader_token`.
- Update `tests/conftest.py` so `Network` and `DeviceNetwork` are registered before `SQLModel.metadata.create_all()`.

---

## 13. Risks and Sequencing Notes

### Recommended implementation order

1. Migration + models + repository + domain
2. Network service + routers + integration tests
3. Device enrichment + inventory column + device detail association UI
4. Topology sidebar + canvas JS overlay
5. Export/import extension + changelog + full verify gate

### Risks

- **Legacy enum cleanup is intentionally deferred.** Removing `VLAN` and `Subnet` from the PostgreSQL enum is a separate migration because enum removal is not a safe additive change.
- **Topology view-mode left rail changes are larger than they look.** The page currently hides the whole left rail outside edit mode. HT-022 must keep the network filter visible in both modes without re-enabling write actions.
- **Canvas multi-colour badges should use an overlay layer, not Cytoscape-only border tricks.** Pure style selectors are not enough for stacked indicators.
- **CIDR updates can invalidate existing memberships.** That failure path must be implemented before the update endpoint ships, or the model will drift into invalid states.
- **Do not skip export/import updates.** This repo already treats full-snapshot export as canonical; omitting networks would create immediate data-loss-on-backup.

---

## 14. Implementation Plan: RFC-HT-022 Networks, VLANs, and Subnets

### 1. Data model

- `src/models/network.py` - add `NetworkBase`, `Network`, `NetworkCreate`, `NetworkUpdate`, `NetworkResponse`, `NetworkListResponse`, `NetworkResponseEnriched`
- `src/models/device_network.py` - add join table plus `DeviceNetworkCreate`, `DeviceNetworkResponse`, `DeviceNetworkNetworkRef`, `DeviceNetworkDeviceRef`
- `src/models/device.py` - add `networks` to `DeviceResponseEnriched`
- `src/models/export_schema.py` - add `ExportedNetwork`, `ExportedDeviceNetwork`, and the two top-level arrays

### 2. Migration

- Alembic revision: `024_create_networks_and_device_networks.py`
- Ops: `create_table(networks)`, `create_check_constraint(vlan range)`, `create_index(lower(name), unique=True)`, `create_index(vlan_id)`, `create_table(device_networks)`, `create_index(network_id)`
- Backfill strategy: none in HT-022; legacy `DeviceType.VLAN` / `Subnet` data stays untouched
- Rollback path: drop `device_networks` first, then `networks`
- Online-safe: yes, additive tables only

### 3. Repository

- `src/repositories/network_repository.py` - add CRUD, batched device lookups, membership lookups, export helpers
- `session.flush()`, never `commit()`

### 4. Domain (pure)

- `src/domain/networks.py` - add `normalize_network_name`, `validate_vlan_id`, `validate_cidr`, `validate_ip_address`, `validate_gateway`, `validate_ip_in_subnet`

### 5. Service

- `src/services/network_service.py` - validate via domain, call repository, `session.commit()`, map duplicates to `409`, business-rule failures to `400`, log IDs/names only
- `src/services/device_enrichment_service.py` - add batched `include=networks` handling
- `src/services/export_service.py`, `src/services/import_service.py`, `src/services/import_validation.py` - add network snapshot support

### 6. API routes

- `src/api/routers/networks.py` - add network CRUD:
  - `GET /api/networks/` - `list[NetworkListResponse]` - `Reader`
  - `POST /api/networks/` - `NetworkResponse` - `Contributor`
  - `GET /api/networks/{network_id}` - `NetworkResponse | NetworkResponseEnriched` - `Reader`
  - `PATCH /api/networks/{network_id}` - `NetworkResponse` - `Contributor`
  - `DELETE /api/networks/{network_id}` - `204` - `Contributor`
- `src/api/routers/device_sub_routes.py` - add membership routes:
  - `GET /api/devices/{device_id}/networks` - `list[DeviceNetworkNetworkRef]` - `Reader`
  - `POST /api/devices/{device_id}/networks` - `DeviceNetworkResponse` - `Contributor`
  - `DELETE /api/devices/{device_id}/networks/{network_id}` - `204` - `Contributor`
- `src/api/routers/devices.py` - extend `include=networks`
- `src/api/app.py` - register `networks_router`

### 7. UI

- `src/ui/pages/settings_networks.py` - add CRUD page
- `src/ui/components/network_modal.py` - add create/edit modal
- `src/ui/components/sidebar.py` - add Networks settings nav
- `src/ui/components/device_detail_networks_section.py` - add membership editor
- `src/ui/components/device_detail_panel.py` and helpers - fetch/render/update memberships
- `src/ui/pages/inventory.py` and `src/ui/pages/inventory_table.py` - add network badges column
- `src/ui/services/topology_data.py` - include network membership data in node payloads
- `src/ui/components/network_filter_panel.py` - add topology sidebar filter panel
- `src/ui/components/canvas_js_networks.py`, `src/ui/components/canvas.py`, `src/ui/components/canvas_styles.py`, `src/ui/pages/topology.py` - add highlight + stacked badge overlay
- `src/ui/components/device_palette.py`, `src/ui/components/canvas_zoom.py`, `src/ui/pages/device_edit.py` - hide deprecated pseudo-network device types from creation flows

### 8. Tests

- `tests/unit/test_networks_domain.py` - boundary and invalid-value cases
- `tests/unit/test_network_service.py` - delete/update conflict rules
- `tests/unit/test_device_service_enrichment.py` - batch enrichment
- `tests/unit/test_topology_data.py` - network membership payload wiring
- `tests/unit/test_inventory_helpers.py` - network badge rows/columns
- `tests/integration/test_networks_api.py` - happy path, 400, 403, 404, 409, include-contract
- `tests/integration/test_export.py`, `tests/integration/test_import.py` - snapshot integrity
- `tests/conftest.py` - register new models

### 9. Docs

- `CHANGELOG.md` - add `[Unreleased]` entry
- Story file: none - acceptance criteria are already sufficient

### 10. Verification

- `docker compose exec api pytest`
- `docker compose exec api mypy src/ --ignore-missing-imports`
- `docker compose build`
- `bash .claude/skills/migration-safety/scripts/check.sh alembic/versions/024_create_networks_and_device_networks.py`
