# RFC-001 Part 2: Data Model and Persistence

**Parts:** [Part 1 – System Overview](rfc-001-part1-system-overview.md) · [Part 2 (this)] · [Part 3 – API Layer](rfc-001-part3-api-layer.md) · [Part 4 – Integrations](rfc-001-part4-integrations.md) · [Part 5 – Auth & Ops](rfc-001-part5-auth-ops.md)

---

## 1. Enum Types — `src/models/types.py`

```python
from enum import Enum

class DeviceType(str, Enum):
    Server = "Server"
    Switch = "Switch"
    Router = "Router"
    NAS = "NAS"
    UPS = "UPS"
    SBC = "SBC"
    Workstation = "Workstation"
    VM = "VM"
    LXC = "LXC"
    Docker = "Docker"
    Application = "Application"
    VLAN = "VLAN"
    Subnet = "Subnet"

class ConnectionType(str, Enum):
    Ethernet = "Ethernet"
    WiFi = "WiFi"
    Fibre = "Fibre"
    iSCSI = "iSCSI"
    NFS = "NFS"
    VM = "VM"
    Other = "Other"

class Role(str, Enum):
    Admin = "Admin"
    Contributor = "Contributor"
    Reader = "Reader"

class LocationType(str, Enum):
    rack = "rack"
    geo = "geo"
```

---

## 2. SQLModel Definitions

### 2.1 `src/models/device.py`

```python
import re
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import INET, MACADDR
from sqlmodel import SQLModel, Field
from pydantic import field_validator

_MAC_PATTERN = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')

class DeviceBase(SQLModel):
    name: str = Field(max_length=255)
    type: DeviceType
    ip: Optional[str] = Field(default=None, sa_column=Column(INET))    # maps to PostgreSQL INET
    mac: Optional[str] = Field(default=None, sa_column=Column(MACADDR)) # maps to PostgreSQL MACADDR
    os: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)
    location_id: Optional[uuid.UUID] = Field(default=None, foreign_key="locations.id")

    @field_validator('mac')
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _MAC_PATTERN.match(v):
            raise ValueError('mac must be in format AA:BB:CC:DD:EE:FF')
        return v

class Device(DeviceBase, table=True):
    __tablename__ = "devices"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(SQLModel):
    name: Optional[str] = None
    type: Optional[DeviceType] = None
    ip: Optional[str] = None
    mac: Optional[str] = None
    os: Optional[str] = None
    notes: Optional[str] = None
    location_id: Optional[uuid.UUID] = None

class DeviceResponse(DeviceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

### 2.2 `src/models/device.py` — DeviceTag and CustomField

```python
class DeviceTag(SQLModel, table=True):
    __tablename__ = "device_tags"
    device_id: uuid.UUID = Field(foreign_key="devices.id", primary_key=True)
    tag_id: uuid.UUID = Field(foreign_key="tags.id", primary_key=True)

class CustomFieldBase(SQLModel):
    key: str = Field(max_length=100)
    value: str

class CustomField(CustomFieldBase, table=True):
    __tablename__ = "custom_fields"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CustomFieldCreate(CustomFieldBase):
    pass

class CustomFieldUpdate(SQLModel):
    value: str

class CustomFieldResponse(CustomFieldBase):
    id: uuid.UUID
    device_id: uuid.UUID
    created_at: datetime
```

### 2.3 `src/models/connection.py`

```python
class ConnectionBase(SQLModel):
    source_id: uuid.UUID = Field(foreign_key="devices.id")
    target_id: uuid.UUID = Field(foreign_key="devices.id")
    type: ConnectionType
    label: Optional[str] = Field(default=None, max_length=255)

class Connection(ConnectionBase, table=True):
    __tablename__ = "connections"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ConnectionCreate(ConnectionBase):
    pass

class ConnectionUpdate(SQLModel):
    type: Optional[ConnectionType] = None
    label: Optional[str] = None

class ConnectionResponse(ConnectionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

### 2.4 `src/models/location.py`

```python
class LocationBase(SQLModel):
    name: str = Field(max_length=255)
    type: LocationType
    lat: Optional[float] = None          # required when type == geo
    lng: Optional[float] = None          # required when type == geo
    rack: Optional[str] = Field(default=None, max_length=100)
    row: Optional[str] = Field(default=None, max_length=100)
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="locations.id")

class Location(LocationBase, table=True):
    __tablename__ = "locations"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class LocationCreate(LocationBase):
    pass

class LocationUpdate(SQLModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rack: Optional[str] = None
    row: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None

class LocationResponse(LocationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

### 2.5 `src/models/tag.py` (in `device.py` or separate)

```python
class TagBase(SQLModel):
    name: str = Field(max_length=100)
    color: str = Field(default="#6366f1", max_length=7)

class Tag(TagBase, table=True):
    __tablename__ = "tags"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TagCreate(TagBase):
    pass

class TagUpdate(SQLModel):
    name: Optional[str] = None
    color: Optional[str] = None

class TagResponse(TagBase):
    id: uuid.UUID
    created_at: datetime
```

### 2.6 `src/models/user.py`

```python
class UserBase(SQLModel):
    username: str = Field(max_length=100)
    email: str = Field(max_length=255)
    role: Role = Field(default=Role.Contributor)
    is_active: bool = Field(default=True)

class User(UserBase, table=True):
    __tablename__ = "users"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    password_hash: str = Field(max_length=255)   # bcrypt hash only, never plaintext
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(UserBase):
    password: str                                # incoming only; hashed before storage

class UserUpdate(SQLModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None               # hashed before storage
    role: Optional[Role] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):                    # password_hash NEVER included
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

### 2.7 `src/models/diagram.py`

```python
from typing import Dict, Any
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class DiagramLayoutBase(SQLModel):
    name: str = Field(max_length=255)
    cytoscape_json: Dict[str, Any] = Field(sa_column=Column(JSONB))

class DiagramLayout(DiagramLayoutBase, table=True):
    __tablename__ = "diagram_layouts"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DiagramLayoutCreate(DiagramLayoutBase):
    pass

class DiagramLayoutResponse(DiagramLayoutBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

---

## 3. Relationships and Constraints

| Constraint | Enforced By |
|---|---|
| `connection.source_id != connection.target_id` | DB CHECK + domain layer |
| `device` with active connections cannot be deleted | `DeviceService.delete()` checks before repository call |
| `location.type == geo` requires lat + lng | Domain `validate_location()` + DB CHECK constraint |
| `custom_field` key unique per device | DB UNIQUE(device_id, key) |
| `tag.name` globally unique | DB UNIQUE |
| `user.email` and `user.username` unique | DB UNIQUE |
| `tag.color` is a valid hex color (#RRGGBB) | Domain `validate_tag_color()` + DB CHECK regex |

---

## 4. Alembic Migration Strategy

- Alembic `env.py` imports all SQLModel models to let autogenerate detect all tables
- Initial migration `001_initial_schema.py` creates all tables, enums, indexes, triggers, and CHECK constraints
- `updated_at` auto-trigger is added in the migration (not expressible in SQLModel directly)
- Enum types use PostgreSQL native `CREATE TYPE ... AS ENUM`
- All UUIDs use `gen_random_uuid()` database default

### Migration Command Reference

```bash
# Apply pending migrations
docker compose exec api alembic upgrade head

# Generate migration from model changes
docker compose exec api alembic revision --autogenerate -m "add_column_x"

# Rollback one step
docker compose exec api alembic downgrade -1
```
