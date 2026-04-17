# RFC: Search & Filter Inventory, Services Entity, App Shell
## Stories: HT-020 · HT-023 · HT-026

**Date:** 2026-04-10  
**Author:** Architect (Sonnet 4.6)  
**Status:** Ready for Implementation  
**Downstream:** Feature-Engineer (all three stories); DevOps-Engineer (migration review for HT-023); UX-Designer (shell/dashboard polish under HT-027)

---

## 0. Information-Hiding Audit

Before any boundary is accepted, each new module must name the one decision it hides:

| Module | Hidden decision |
|---|---|
| `src/ui/components/app_shell.py` | NiceGUI `ui.header()` + `ui.left_drawer()` layout API — swap NiceGUI layout primitives without touching any page file |
| `src/ui/pages/dashboard.py` | Dashboard data-aggregation strategy (httpx fan-out vs. direct service calls, sorting logic) |
| `src/domain/search.py` | Query-string tokenisation grammar — operator syntax can change without touching the repository |
| `src/domain/services.py` | Service-entity business rules (port range, dependency-cycle detection algorithm) |
| `src/repositories/service_repository.py` | SQLModel ORM mechanics for the `services` + `service_dependencies` tables |
| `src/services/service_service.py` | Transaction boundary for service CRUD and cycle-validation workflow |

---

## 1. HT-026 — App Shell

### 1.1 Overview

Every authenticated page gains a shared persistent layout: left sidebar, top header bar, breadcrumb, and a user menu. A new Dashboard page at `/` becomes the post-login landing. Login redirect changes from `/topology` to `/`.

### 1.2 Data Model Changes

None. HT-026 is UI-only.

### 1.3 API Layer — devices sort extension

The dashboard "Recent Activity" card requires `GET /api/devices?sort=-updated_at&limit=5`. Add a `sort` query parameter to the existing devices list endpoint.

**Extension to `GET /api/devices`:**

```
sort: str | None  (optional query param, default None)
```

Valid values: `name`, `-name`, `updated_at`, `-updated_at`, `created_at`, `-created_at`.  
Prefix `-` means descending. Any other value is silently ignored (falls back to default `created_at ASC`).

**Repository extension in `device_repository.get_all()`:**

Add `sort: str | None = None` parameter. Map valid sort strings to `order_by()` expressions. No change to existing call sites (backward-compatible default).

**Estimated change:** `src/api/routers/devices.py` +8 lines, `src/repositories/device_repository.py` +15 lines.

### 1.4 Domain Functions

None for HT-026.

### 1.5 Service Layer

None for HT-026.

### 1.6 UI Layer

#### 1.6.1 `src/ui/components/app_shell.py` (NEW, ~110 lines)

Exports one public symbol: `app_shell` — a synchronous context manager.

```python
from contextlib import contextmanager
from typing import Generator
from nicegui import app as nicegui_app, ui
from src.ui.design.tokens import (COLOR_PRIMARY, COLOR_SURFACE, COLOR_SURFACE_ALT,
                                   COLOR_TEXT, COLOR_TEXT_MUTED)
from src.models.types import Role
from src.ui.components.auth_guard import get_ui_role

# Sidebar navigation items
_NAV_ITEMS: list[dict[str, str]] = [
    {"label": "Dashboard",  "route": "/",                     "icon": "dashboard"},
    {"label": "Topology",   "route": "/topology",             "icon": "account_tree"},
    {"label": "Inventory",  "route": "/inventory",            "icon": "inventory_2"},
    {"label": "Map",        "route": "/map",                  "icon": "map",          "disabled": "true"},
]
_SETTINGS_ITEMS: list[dict[str, str]] = [
    {"label": "Locations",  "route": "/settings/locations",   "icon": "location_on"},
    {"label": "Users",      "route": "/settings/users",       "icon": "people",       "admin_only": "true"},
]

@contextmanager
def app_shell(
    title: str,
    current_route: str,
    breadcrumb: list[str] | None = None,
) -> Generator[None, None, None]:
    """
    Context manager that renders header + sidebar, then yields for page content.

    Usage inside an authenticated @ui.page function:

        with app_shell("Inventory", "/inventory", breadcrumb=["Inventory"]):
            # page-specific NiceGUI elements go here
            ...

    Sidebar expansion state is persisted in `nicegui_app.storage.user["sidebar_expanded"]`
    (NiceGUI server-side per-session storage). This is functionally equivalent to
    localStorage for single-session persistence and is the correct NiceGUI idiom.
    The HT-026 story specifies localStorage; we use NiceGUI's session storage, which
    satisfies the "persists across page navigations" acceptance criterion.
    """
    _render_header(breadcrumb or [title])
    _render_sidebar(current_route)
    with ui.column().classes("flex-1 w-full"):
        yield


def _render_header(breadcrumb: list[str]) -> None:
    """Render the top header bar: logo + breadcrumb on left, user menu on right."""
    with ui.header().style(
        f"background-color:{COLOR_SURFACE}; border-bottom:1px solid #383849;"
        " padding:0 16px; height:52px; display:flex; align-items:center;"
    ):
        # Logo / home link
        ui.link("Hometower", "/").style(
            f"color:{COLOR_PRIMARY}; font-weight:700; font-size:1.1rem;"
            " text-decoration:none; margin-right:16px;"
        )
        # Breadcrumb
        if breadcrumb:
            with ui.row().classes("items-center gap-1"):
                for i, crumb in enumerate(breadcrumb):
                    if i > 0:
                        ui.label("›").style(f"color:{COLOR_TEXT_MUTED}")
                    ui.label(crumb).style(f"color:{COLOR_TEXT_MUTED}; font-size:0.875rem")
        ui.space()
        # User menu (right side)
        _render_user_menu()


def _render_user_menu() -> None:
    """Render the top-right user dropdown (email + logout)."""
    username: str = nicegui_app.storage.user.get("username", "User")
    with ui.dropdown_button(username, auto_close=True).props("flat color=grey-4"):
        ui.item("Change Password", on_click=lambda: None)  # placeholder — HT-025
        ui.separator()
        ui.item("Logout", on_click=_do_logout)


def _do_logout() -> None:
    """Clear session storage and navigate to /login."""
    nicegui_app.storage.user.clear()
    ui.navigate.to("/login")


def _render_sidebar(current_route: str) -> None:
    """Render the left navigation sidebar with collapse toggle."""
    role = get_ui_role()
    expanded: bool = nicegui_app.storage.user.get("sidebar_expanded", True)

    with ui.left_drawer(value=expanded).props(
        f"width=220 mini-width=56 {'mini' if not expanded else ''}"
    ).style(f"background-color:{COLOR_SURFACE_ALT}; border-right:1px solid #383849;") as drawer:
        # Collapse/expand toggle
        with ui.row().classes("justify-end px-2 pt-2"):
            ui.button(
                icon="chevron_left" if expanded else "chevron_right",
                on_click=lambda: _toggle_sidebar(drawer),
            ).props("flat dense round size=sm color=grey-5")

        # Primary nav items
        for item in _NAV_ITEMS:
            disabled = item.get("disabled") == "true"
            _nav_item(
                label=item["label"],
                icon=item["icon"],
                route=item["route"],
                active=(current_route == item["route"]),
                disabled=disabled,
            )

        ui.separator().classes("my-2")
        ui.label("Settings").style(
            f"color:{COLOR_TEXT_MUTED}; font-size:0.75rem; padding:4px 12px; font-weight:600;"
        )

        for item in _SETTINGS_ITEMS:
            admin_only = item.get("admin_only") == "true"
            if admin_only and role != Role.Admin:
                continue
            _nav_item(
                label=item["label"],
                icon=item["icon"],
                route=item["route"],
                active=(current_route == item["route"]),
                disabled=False,
            )


def _nav_item(label: str, icon: str, route: str, active: bool, disabled: bool) -> None:
    """Render a single sidebar navigation row."""
    active_style = f"background-color:{COLOR_PRIMARY}20; border-left:3px solid {COLOR_PRIMARY};" if active else ""
    text_color = COLOR_PRIMARY if active else COLOR_TEXT
    with ui.row().classes("items-center px-3 py-2 cursor-pointer w-full").style(
        active_style + f" color:{text_color};"
    ).on("click", lambda r=route, d=disabled: (None if d else ui.navigate.to(r))):
        ui.icon(icon).style(f"color:{text_color}; font-size:1.25rem")
        ui.label(label).style(f"font-weight:{'700' if active else '400'}; font-size:0.9rem")
        if disabled:
            ui.badge("soon", color="grey").props("rounded")


def _toggle_sidebar(drawer: ui.left_drawer) -> None:  # type: ignore[name-defined]
    """Toggle sidebar expanded/collapsed and persist preference."""
    current = nicegui_app.storage.user.get("sidebar_expanded", True)
    nicegui_app.storage.user["sidebar_expanded"] = not current
    drawer.toggle()
```

#### 1.6.2 `src/ui/pages/dashboard.py` (NEW, ~130 lines)

```python
@ui.page("/")
async def dashboard_page() -> None:
    if redirect_if_unauthenticated():
        return
    with app_shell("Dashboard", "/", breadcrumb=["Dashboard"]):
        # Dashboard body — stat cards + recent activity + quick actions
        ...
```

**Data fetching strategy:** All dashboard data is fetched via `httpx.AsyncClient` within the async page function. Make parallel requests using `asyncio.gather`:

```python
token = nicegui_app.storage.user.get("access_token", "")
headers = {"Authorization": f"Bearer {token}"}
base = settings.api_base_url

async with httpx.AsyncClient() as client:
    device_resp, conn_resp, loc_resp, tag_resp, recent_resp = await asyncio.gather(
        client.get(f"{base}/api/devices", params={"limit": 1}, headers=headers),
        client.get(f"{base}/api/connections", params={"limit": 1}, headers=headers),
        client.get(f"{base}/api/locations", headers=headers),
        client.get(f"{base}/api/tags", headers=headers),
        client.get(f"{base}/api/devices", params={"sort": "-updated_at", "limit": 5}, headers=headers),
    )
```

Counts: `device_resp.json()["total"]`, `conn_resp.json()["total"]`, `len(loc_resp.json())`, `len(tag_resp.json())`.  
Recent activity: `recent_resp.json()["items"]` (uses the sort extension from §1.3).

**Empty state:** When device count is 0, Recent Activity shows: "No devices yet — add one from Topology".

**Type breakdown:** For the device type breakdown (top 4 types), a second `GET /api/devices?limit=1000` call is made to count by type client-side. This is acceptable for v1 (<500 devices).

**Quick actions:** Plain `ui.button` navigating via `ui.navigate.to()`.

#### 1.6.3 Page modifications — wrap in `app_shell`

Each existing authenticated page gains a two-line change:
1. Import `app_shell` from `src.ui.components.app_shell`
2. Wrap the page body content in `with app_shell(title, route, breadcrumb=...)`

The `ui.query("body").style(...)` background call in each page is removed — `app_shell` will set the global page background once in `_render_header` or via a top-level `ui.query` call inside `app_shell`.

| Page file | Title arg | Route arg | Breadcrumb arg |
|---|---|---|---|
| `topology.py` | `"Topology"` | `"/topology"` | `["Topology"]` |
| `inventory.py` | `"Inventory"` | `"/inventory"` | `["Inventory"]` |
| `settings_locations.py` | `"Locations"` | `"/settings/locations"` | `["Settings", "Locations"]` |
| `settings_users.py` | `"Users"` | `"/settings/users"` | `["Settings", "Users"]` |
| `settings_data.py` | `"Data"` | `"/settings/data"` | `["Settings", "Data"]` |

#### 1.6.4 Login redirect

`src/ui/pages/login.py` — change the JavaScript redirect target from `/topology` to `/`:

```js
// before:  window.location.href = '/topology';
// after:   window.location.href = '/';
```

Exact line to change (in the `handle_login` JS string): replace the single occurrence of `'/topology'` with `'/'`.

#### 1.6.5 `src/main.py`

Add one import line to register the dashboard page:

```python
from src.ui.pages import dashboard  # noqa: F401 — registers / page
```

Insert after the existing `login` import.

### 1.7 Security Boundaries

- Sidebar respects RBAC: "Users" link rendered only when `role == Role.Admin`. This is a UI hint only — the actual RBAC gate lives in the `/settings/users` page and its API endpoints.
- `_do_logout` calls `nicegui_app.storage.user.clear()` to wipe the JWT from server-side session storage.
- No new secrets or tokens introduced.

---

## 2. HT-023 — Services Entity

### 2.1 Overview

New `Service` entity (per device) and `ServiceDependency` join table. Full CRUD API, cycle detection in domain layer, canvas hover tooltip, inventory service-count column.

### 2.2 Data Model Changes

#### 2.2.1 `src/models/types.py` — add two enums

```python
class ServiceProtocol(str, Enum):
    http  = "http"
    https = "https"
    tcp   = "tcp"
    udp   = "udp"
    other = "other"

class ServiceStatus(str, Enum):
    running = "running"
    stopped = "stopped"
    unknown = "unknown"
```

#### 2.2.2 `src/models/service.py` (NEW, ~90 lines)

```python
"""Service SQLModel definitions (HT-023)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from src.models.types import ServiceProtocol, ServiceStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ServiceBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    protocol: ServiceProtocol = Field(default=ServiceProtocol.other)
    url: Optional[str] = Field(default=None, max_length=2048)
    status: ServiceStatus = Field(default=ServiceStatus.unknown)
    notes: Optional[str] = Field(default=None, max_length=5000)


class Service(ServiceBase, table=True):
    __tablename__ = "services"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    protocol: Optional[ServiceProtocol] = None
    url: Optional[str] = Field(default=None, max_length=2048)
    status: Optional[ServiceStatus] = None
    notes: Optional[str] = Field(default=None, max_length=5000)


class ServiceResponse(ServiceBase):
    id: uuid.UUID
    device_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ServiceListResponse(ServiceResponse):
    """Flat list response — includes device_name for cross-device listing."""
    device_name: str


class DependencyRef(SQLModel):
    """Compact reference used in ServiceWithDependencies."""
    id: uuid.UUID
    name: str
    device_name: str


class ServiceWithDependencies(ServiceResponse):
    depends_on: list[DependencyRef] = []
    depended_by: list[DependencyRef] = []
```

#### 2.2.3 `src/models/service_dependency.py` (NEW, ~25 lines)

```python
"""ServiceDependency SQLModel (HT-023) — join table for service-to-service dependencies."""
import uuid

from sqlmodel import Field, SQLModel


class ServiceDependency(SQLModel, table=True):
    __tablename__ = "service_dependencies"

    service_id: uuid.UUID = Field(
        foreign_key="services.id", ondelete="CASCADE", primary_key=True
    )
    depends_on_id: uuid.UUID = Field(
        foreign_key="services.id", ondelete="CASCADE", primary_key=True
    )


class DependencyCreate(SQLModel):
    depends_on: uuid.UUID
```

#### 2.2.4 `src/models/device.py` — extend `DeviceResponseEnriched`

Add one optional field (backward-compatible):

```python
# In DeviceResponseEnriched, after custom_fields:
services: list["ServiceResponse"] = []
```

Add the forward-ref import: `from __future__ import annotations` at the top of `device.py`, or use a string annotation. The `ServiceResponse` type lives in `src/models/service.py`. Import it at the module level to avoid circular imports (service.py does not import device.py).

### 2.3 Migration Plan

**File:** `alembic/versions/012_create_services_and_dependencies.py`

```sql
-- Table: services
CREATE TABLE services (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id   UUID        NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    port        INTEGER     CHECK (port BETWEEN 1 AND 65535),
    protocol    VARCHAR(10) NOT NULL DEFAULT 'other'
                CHECK (protocol IN ('http','https','tcp','udp','other')),
    url         VARCHAR(2048),
    status      VARCHAR(10) NOT NULL DEFAULT 'unknown'
                CHECK (status IN ('running','stopped','unknown')),
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique constraint: case-insensitive name per device
CREATE UNIQUE INDEX uq_services_device_name
    ON services (device_id, lower(name));

-- Table: service_dependencies
CREATE TABLE service_dependencies (
    service_id    UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    depends_on_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    PRIMARY KEY (service_id, depends_on_id)
);

-- Index for reverse-lookup (depended_by queries)
CREATE INDEX ix_service_dependencies_depends_on
    ON service_dependencies (depends_on_id);
```

**DevOps-Engineer migration review required** — two new tables with CASCADE FKs.

Downgrade: `DROP TABLE service_dependencies; DROP TABLE services;`

### 2.4 Domain Functions

**File:** `src/domain/services.py` (NEW, ~70 lines)

```python
"""Service domain logic — pure functions, no I/O (HT-023)."""
import uuid
from typing import Optional


def validate_port(port: Optional[int]) -> Optional[int]:
    """Return port unchanged or None. Raise ValueError if outside [1, 65535]."""
    if port is None:
        return None
    if not (1 <= port <= 65535):
        raise ValueError("Port must be between 1 and 65535")
    return port


def validate_no_dependency_cycle(
    proposed_service_id: uuid.UUID,
    proposed_depends_on_id: uuid.UUID,
    all_deps: list[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """Raise ValueError('Circular dependency detected') if the proposed edge creates a cycle.

    A cycle exists when proposed_depends_on_id can reach proposed_service_id by
    following existing dependency edges (BFS on the depends_on graph).
    Self-dependency (proposed_service_id == proposed_depends_on_id) is also rejected.

    Args:
        proposed_service_id:    ID of the service that would own the dependency (A).
        proposed_depends_on_id: ID of the service A would depend on (B).
        all_deps:               All existing (service_id, depends_on_id) pairs from the DB.

    Algorithm:
        Build an adjacency map from all_deps: service → set[depends_on].
        BFS starting from proposed_depends_on_id, following depends_on edges.
        If proposed_service_id is reachable → cycle.
    """
    if proposed_service_id == proposed_depends_on_id:
        raise ValueError("Circular dependency detected")

    # Build adjacency: service_id → {depends_on_id, ...}
    graph: dict[uuid.UUID, set[uuid.UUID]] = {}
    for src, dst in all_deps:
        graph.setdefault(src, set()).add(dst)

    # BFS from proposed_depends_on_id
    visited: set[uuid.UUID] = set()
    queue: list[uuid.UUID] = [proposed_depends_on_id]
    while queue:
        node = queue.pop(0)
        if node == proposed_service_id:
            raise ValueError("Circular dependency detected")
        if node in visited:
            continue
        visited.add(node)
        queue.extend(graph.get(node, set()))
```

### 2.5 Service Layer

**File:** `src/services/service_service.py` (NEW, ~150 lines)

```python
"""Service-entity service — orchestrates domain + repository (HT-023)."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from src.domain import services as service_domain
from src.models.service import (
    DependencyRef, Service, ServiceCreate, ServiceDependency,
    ServiceListResponse, ServiceResponse, ServiceUpdate, ServiceWithDependencies,
)
from src.repositories import service_repository, device_repository
from src.utils.logger import logger


def create(device_id: uuid.UUID, data: ServiceCreate, session: Session) -> Service:
    """Validate and persist a new service on a device.

    Raises:
        HTTP 404 if device not found.
        HTTP 409 if a service with the same (case-insensitive) name exists on device.
        HTTP 422 if port is out of range (propagated from ValueError).
    """
    ...


def get_by_id(service_id: uuid.UUID, session: Session) -> Service:
    """Return service or raise HTTP 404."""
    ...


def get_by_device(device_id: uuid.UUID, session: Session) -> list[ServiceResponse]:
    """Return all services for a device as response models."""
    ...


def get_all(q: str | None, session: Session) -> list[ServiceListResponse]:
    """Return flat list of all services across all devices, with device_name.

    q: optional case-insensitive substring filter on service name.
    """
    ...


def update(
    service_id: uuid.UUID, data: ServiceUpdate, session: Session
) -> Service:
    """Apply partial update to service fields.

    If name is being changed, check uniqueness constraint for new name.
    """
    ...


def delete(service_id: uuid.UUID, session: Session) -> None:
    """Delete service. Cascade in DB removes its dependencies."""
    ...


def get_with_dependencies(
    service_id: uuid.UUID, session: Session
) -> ServiceWithDependencies:
    """Return service enriched with depends_on and depended_by lists."""
    ...


def add_dependency(
    service_id: uuid.UUID, depends_on_id: uuid.UUID, session: Session
) -> None:
    """Add a dependency edge. Validates no cycle before persisting.

    Raises:
        HTTP 400: "Circular dependency detected"
        HTTP 404: if either service does not exist
        HTTP 409: if dependency already exists
    """
    all_deps = service_repository.get_all_dependency_edges(session)
    try:
        service_domain.validate_no_dependency_cycle(service_id, depends_on_id, all_deps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ...


def remove_dependency(
    service_id: uuid.UUID, depends_on_id: uuid.UUID, session: Session
) -> None:
    """Remove a dependency edge. No-op if it does not exist."""
    ...
```

### 2.6 Repository

**File:** `src/repositories/service_repository.py` (NEW, ~120 lines)

```python
"""Service repository (HT-023) — sole layer that holds SQLModel Session for Service ops."""
import uuid
from sqlalchemy import func
from sqlmodel import Session, select, col

from src.models.device import Device
from src.models.service import Service, ServiceDependency, ServiceListResponse


def create(session: Session, service: Service) -> Service: ...
def get_by_id(session: Session, service_id: uuid.UUID) -> Service | None: ...
def get_by_device(session: Session, device_id: uuid.UUID) -> list[Service]: ...

def get_all(session: Session, q: str | None = None) -> list[tuple[Service, str]]:
    """Return (Service, device_name) pairs, optionally filtered by name substring."""
    # LEFT JOIN services → devices. Filter: ILIKE '%q%' on service.name if q given.
    ...

def get_by_device_and_name(
    session: Session, device_id: uuid.UUID, name: str
) -> Service | None:
    """Case-insensitive name lookup within a device (uniqueness guard)."""
    # WHERE device_id = ? AND lower(name) = lower(?)
    ...

def update(session: Session, service: Service) -> Service: ...
def delete(session: Session, service: Service) -> None: ...

def add_dependency(session: Session, dep: ServiceDependency) -> ServiceDependency: ...

def get_dependency_edges_for_service(
    session: Session, service_id: uuid.UUID
) -> list[ServiceDependency]:
    """All edges WHERE service_id = service_id (what this service depends on)."""
    ...

def get_reverse_dependency_edges(
    session: Session, depends_on_id: uuid.UUID
) -> list[ServiceDependency]:
    """All edges WHERE depends_on_id = depends_on_id (what depends on this service)."""
    ...

def get_all_dependency_edges(
    session: Session,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Return all (service_id, depends_on_id) pairs — used for cycle detection."""
    rows = session.exec(
        select(ServiceDependency.service_id, ServiceDependency.depends_on_id)
    ).all()
    return [(r[0], r[1]) for r in rows]

def dependency_exists(
    session: Session, service_id: uuid.UUID, depends_on_id: uuid.UUID
) -> bool: ...

def remove_dependency(
    session: Session, service_id: uuid.UUID, depends_on_id: uuid.UUID
) -> None: ...
```

### 2.7 API Layer

**File:** `src/api/routers/services.py` (NEW, ~180 lines)

Router prefix: `/services` — registers under `/api/services/*`.

```
GET    /api/services                                     → list[ServiceListResponse]        (Reader+)
    Query params: q: str | None
GET    /api/services/{service_id}                        → ServiceResponse                  (Reader+)
    Query params: include: str (supports "dependencies" → ServiceWithDependencies)
PATCH  /api/services/{service_id}                        → ServiceResponse                  (Contributor+)
DELETE /api/services/{service_id}                        → 204 No Content                   (Contributor+)
GET    /api/services/{service_id}/dependencies           → list[DependencyRef]              (Reader+)
POST   /api/services/{service_id}/dependencies           → 201                              (Contributor+)
    Body: DependencyCreate { depends_on: uuid.UUID }
DELETE /api/services/{service_id}/dependencies/{dep_id}  → 204 No Content                   (Contributor+)
```

**File:** `src/api/routers/device_sub_routes.py` — extend with two endpoints

```
GET    /api/devices/{device_id}/services  → list[ServiceResponse]   (Reader+)
POST   /api/devices/{device_id}/services  → ServiceResponse 201      (Contributor+)
    Body: ServiceCreate
```

**Error responses:**

| Condition | HTTP | Body |
|---|---|---|
| Service not found | 404 | `{"detail": "Service not found"}` |
| Port out of range | 400 | `{"detail": "Port must be between 1 and 65535"}` |
| Duplicate name on device | 409 | `{"detail": "Service name already exists on this device"}` |
| Circular dependency | 400 | `{"detail": "Circular dependency detected"}` |
| Invalid protocol | 422 | Pydantic validation error |

**`GET /api/devices/{device_id}`** — extend existing endpoint in `devices.py`:

When `include` contains `"services"`, populate `DeviceResponseEnriched.services` from `service_repository.get_by_device()`. This is a ~8 line extension to the existing `get_all_enriched` and `get_device` handlers.

**`src/api/app.py`** — register new router:

```python
from src.api.routers.services import router as services_router
# In app setup:
app.include_router(services_router, prefix="/api")
```

### 2.8 Canvas Integration

**File:** `src/ui/components/canvas.py` (MODIFY, ~20 lines added to JS template)

Extend the Cytoscape.js event wire-up (in `_CANVAS_INIT_JS_TEMPLATE` or appended via `inject_canvas_events`) with a `mouseover` handler on nodes:

```javascript
// Client-side service tooltip cache
window._htServicesCache = {};

// Status → dot colour mapping
var HT_STATUS_COLORS = {
    running: '#a6e3a1',   // COLOR_SUCCESS
    stopped: '#f38ba8',   // COLOR_ERROR
    unknown: '#a6adc8'    // COLOR_TEXT_MUTED
};

cy.on('mouseover', 'node', function(evt) {
    var nodeId = evt.target.id();

    if (window._htServicesCache[nodeId] !== undefined) {
        _showServiceTooltip(evt, window._htServicesCache[nodeId]);
        return;
    }

    fetch('/api/devices/' + nodeId + '?include=services', {
        headers: { 'Authorization': 'Bearer ' + window._htToken }
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        window._htServicesCache[nodeId] = data.services || [];
        _showServiceTooltip(evt, window._htServicesCache[nodeId]);
    });
});

cy.on('mouseout', 'node', function() {
    var tip = document.getElementById('ht-svc-tooltip');
    if (tip) tip.remove();
});

function _showServiceTooltip(evt, services) {
    var tip = document.getElementById('ht-svc-tooltip');
    if (tip) tip.remove();
    if (!services || services.length === 0) return;

    tip = document.createElement('div');
    tip.id = 'ht-svc-tooltip';
    tip.style.cssText = 'position:fixed;z-index:9000;background:#27273a;border-radius:6px;'
        + 'padding:8px 12px;font-size:0.8rem;color:#cdd6f4;pointer-events:none;'
        + 'box-shadow:0 4px 12px rgba(0,0,0,0.5);max-width:260px;';
    tip.style.left = (evt.originalEvent.clientX + 14) + 'px';
    tip.style.top  = (evt.originalEvent.clientY - 8) + 'px';

    services.forEach(function(svc) {
        var row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:6px;padding:2px 0;';
        var dot = document.createElement('span');
        dot.style.cssText = 'width:8px;height:8px;border-radius:50%;flex-shrink:0;'
            + 'background:' + (HT_STATUS_COLORS[svc.status] || '#a6adc8') + ';';
        var label = document.createElement('span');
        label.textContent = svc.name + (svc.port ? ':' + svc.port : '');
        row.appendChild(dot);
        row.appendChild(label);
        tip.appendChild(row);
    });
    document.body.appendChild(tip);
}
```

Cache invalidation: invalidated when user navigates away (JS variable resets on page load). In-session cache is sufficient for v1.

`window._htToken` must already be stored by canvas init; verify it is set in `canvas.py`'s init template. If not, the JS template must be extended to read the token from `window._htToken` using the existing pattern (check `canvas_events.py`).

### 2.9 Inventory Integration

**File:** `src/ui/pages/inventory_helpers.py` (MODIFY, ~15 lines)

1. Add `"services"` column definition to `_INVENTORY_TABLE_COLUMNS`:
   ```python
   {"name": "services", "label": "Services", "field": "services", "sortable": False, "align": "left"}
   ```

2. In the slot template `_INVENTORY_TABLE_BODY_SLOT`, add a `<q-td key="services">` cell rendering a `<q-badge>` with the count.

3. In `build_inventory_rows()`, add `"services": f"{len(d.services)} services" if d.services else "—"` to each row dict.

**File:** `src/ui/pages/inventory.py` (MODIFY, ~5 lines)

When calling the device list API, extend `include` to include `"services"`:
```
GET /api/devices?include=location,tags,services&limit=1000
```

### 2.10 Security Boundaries

- Create/update/delete requires Contributor+; reads require Reader+ (consistent with tags, custom fields).
- `url` field max 2048 chars — prevents oversized inputs.
- Port range validated in domain layer before persistence.
- No service credentials stored — `url` is a display URL only.

---

## 3. HT-020 — Search and Filter Inventory

### 3.1 Overview

Structured search operators (`type:server ip:192.168.* tag:production`) parsed server-side. Results filtered via dynamic SQLAlchemy WHERE clauses. UI gains operator-value autocomplete.

### 3.2 Data Model Changes

None. HT-020 extends query behaviour on existing tables.

### 3.3 Domain Functions

**File:** `src/domain/search.py` (NEW, ~90 lines)

```python
"""Structured inventory search — pure query parsing functions (HT-020)."""
from dataclasses import dataclass, field


# Operators handled by this implementation.
# parent: (HT-021) and network: (HT-022) are intentionally omitted — those features
# are not shipped. If either operator appears in a query, the token is treated as
# free text (graceful fallback per acceptance criteria).
_KNOWN_OPERATORS = frozenset({"type", "tag", "ip", "os", "location", "service"})


@dataclass
class ParsedQuery:
    """Structured representation of an inventory search query.

    All list fields accumulate multiple values for the same operator (OR within
    operator, AND across operators). free_text is the remainder after operator
    extraction and is matched against name, IP, OS, notes, and location name.
    """
    free_text: str = ""
    types: list[str] = field(default_factory=list)            # type:
    tags: list[str] = field(default_factory=list)             # tag:
    ip_patterns: list[str] = field(default_factory=list)      # ip:
    os_patterns: list[str] = field(default_factory=list)      # os:
    location_patterns: list[str] = field(default_factory=list)  # location:
    service_patterns: list[str] = field(default_factory=list)  # service: (requires HT-023)

    def is_empty(self) -> bool:
        """Return True when the query would match all devices (no filtering)."""
        return (
            not self.free_text
            and not self.types
            and not self.tags
            and not self.ip_patterns
            and not self.os_patterns
            and not self.location_patterns
            and not self.service_patterns
        )


def parse_query(raw: str) -> ParsedQuery:
    """Tokenise a structured query string into a ParsedQuery.

    Tokenisation rules:
    1. Split by whitespace.
    2. Each token matching `operator:value` where operator ∈ _KNOWN_OPERATORS
       is extracted into the corresponding list.
    3. Tokens with an unknown operator prefix are appended to free_text.
    4. Tokens with no `:` are appended to free_text.
    5. Empty token values (e.g. `type:`) are ignored.

    Returns:
        ParsedQuery with all extracted operators and the free-text remainder.
    """
    result = ParsedQuery()
    free_parts: list[str] = []

    for token in raw.strip().split():
        if ":" in token:
            op, _, val = token.partition(":")
            op_lower = op.lower()
            if op_lower in _KNOWN_OPERATORS and val:
                if op_lower == "type":
                    result.types.append(val)
                elif op_lower == "tag":
                    result.tags.append(val)
                elif op_lower == "ip":
                    result.ip_patterns.append(val)
                elif op_lower == "os":
                    result.os_patterns.append(val)
                elif op_lower == "location":
                    result.location_patterns.append(val)
                elif op_lower == "service":
                    result.service_patterns.append(val)
            else:
                free_parts.append(token)  # unknown operator → free text
        else:
            free_parts.append(token)

    result.free_text = " ".join(free_parts)
    return result


def to_sql_like(pattern: str) -> str:
    """Convert a glob pattern to a SQL LIKE-compatible string.

    Escapes SQL meta-characters (% and _) in user input before replacing
    glob * with %. This prevents accidental wildcard injection.

    Example: "192.168._*" → "192.168.\_%"
    """
    escaped = pattern.replace("%", r"\%").replace("_", r"\_")
    return escaped.replace("*", "%")
```

### 3.4 Repository Extension

**File:** `src/repositories/device_repository.py` (MODIFY, ~60 lines added)

Add a new, dedicated search function:

```python
from src.domain.search import ParsedQuery, to_sql_like
from src.models.tag import Tag
from src.models.location import Location
from src.models.service import Service  # HT-023 dependency

def search(
    session: Session,
    parsed: ParsedQuery,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[tuple[Device, str | None]], int]:
    """Filter devices using a ParsedQuery and return (Device, location_name) pairs + total.

    Filter semantics:
    - All populated fields apply as AND conditions.
    - Within types, tags, ip_patterns, os_patterns, location_patterns, service_patterns:
      multiple values use OR (any-match).
    - free_text matches ILIKE against name, ip, os, notes, and location.name (OR across fields).
    - Wildcard * in ip_patterns/os_patterns/location_patterns is converted via to_sql_like().
    - type: values are case-insensitive exact matches against Device.type enum value.
    - tag: values are case-insensitive substring matches against Tag.name.
    - service: values are case-insensitive substring matches against Service.name (HT-023).

    Returns empty ([], 0) if parsed.is_empty() — caller should use get_all_with_location() instead.
    """
```

Implementation notes for Feature-Engineer:
- Use `sqlalchemy.or_()` for within-operator OR conditions and `sqlalchemy.and_()` across operators.
- For `tag:` filtering: join `device_tags` and `tags` tables; use `func.lower(Tag.name).contains(val.lower())` or `ilike`.
- For `location:` filtering: LEFT JOIN `locations`; use `ilike` after `to_sql_like()`.
- For `service:` filtering: LEFT JOIN `services`; use `ilike` on `Service.name`.
- For `ip:` patterns: apply `to_sql_like()` and use `Device.ip.ilike(pattern)`.
- For free_text: `OR` across `Device.name`, `Device.ip`, `Device.os`, `Device.notes`, `Location.name` using `ilike('%' + free_text + '%')`.
- `escape='\\'` must be passed to all `ilike()` calls that use `to_sql_like()` output (to support the `\_` and `\%` escapes).

**Extend `get_all` signature** to accept `sort: str | None = None` (for HT-026 dashboard):

```python
def get_all(
    session: Session,
    page: int = 1,
    limit: int = 50,
    sort: str | None = None,
) -> tuple[list[Device], int]:
```

Valid sort values and their expressions:

| Value | expression |
|---|---|
| `name` | `Device.name.asc()` |
| `-name` | `Device.name.desc()` |
| `updated_at` | `Device.updated_at.asc()` |
| `-updated_at` | `Device.updated_at.desc()` |
| `created_at` | `Device.created_at.asc()` |
| `-created_at` | `Device.created_at.desc()` |
| `None` or unknown | `Device.created_at.asc()` (existing default) |

### 3.5 Service Layer Extension

**File:** `src/services/device_service.py` (MODIFY, ~20 lines)

Extend `get_all_enriched` to accept `q: str | None = None`. When `q` is provided and non-empty:
1. Call `parse_query(q)` from `src.domain.search`
2. If `parsed.is_empty()`, fall back to existing `get_all_with_location`
3. Otherwise call `device_repository.search(session, parsed, page, limit)`

```python
def get_all_enriched(
    session: Session,
    page: int,
    limit: int,
    include: set[str],
    q: str | None = None,
    sort: str | None = None,
) -> tuple[list[DeviceResponseEnriched], int]:
```

### 3.6 API Layer Extension

**File:** `src/api/routers/devices.py` (MODIFY, ~10 lines)

Add query parameters to `list_devices`:

```python
q: str | None = Query(default=None, max_length=500, description="Structured search query"),
sort: str | None = Query(default=None, description="Sort field, prefix '-' for descending"),
```

Pass `q` and `sort` to `device_service.get_all_enriched(...)`.

`max_length=500` on `q` provides a hard input bound at the HTTP layer.

### 3.7 UI Layer

**File:** `src/ui/pages/inventory.py` (MODIFY, ~30 lines)

1. The existing `ui.input("Search")` gains an `on_value_change` handler.
2. When the input value ends with a known operator prefix followed by `:` (regex `(type|tag|ip|os|location|service):$`), render a `ui.menu` anchored to the input showing autocomplete suggestions.
3. Autocomplete values:
   - `type:` → `DeviceType` enum values (from `src.models.types.DeviceType`)
   - `tag:` → fetched once from `GET /api/tags` on first focus
   - All others → no autocomplete (free-form)
4. After a suggestion is selected, the input is updated to include the full `operator:value` token.
5. Search execution (API call) is triggered 300 ms after the last keystroke (debounced) or on Enter.

**Change to `_apply_filters` / search trigger:**

Currently the inventory page filters client-side in `filter_devices`. After HT-020, the search bar submits `q` server-side when the query contains an operator (detected by the presence of `:`); pure free-text falls through to the existing client-side `filter_devices` for backward compatibility.

Alternatively (simpler and cleaner): always send `q` server-side. The `parse_query()` function gracefully handles pure free-text (no operators). Recommended approach: route all searches through the server-side `q` parameter and remove client-side text filtering. `filter_devices()` in `src/domain/inventory.py` retains the type and tag chip filtering (which is still client-side).

### 3.8 Security Boundaries

- `q` parameter is bounded to 500 chars at the HTTP layer.
- `to_sql_like()` escapes `%` and `_` before converting `*` — no SQL injection possible via wildcard patterns (SQLAlchemy parameterised queries handle the rest).
- Free-text ILIKE uses parameterised literals, not string interpolation.

---

## 4. Validation

### 4.1 Tests to Write

| Test file | What it validates |
|---|---|
| `tests/unit/test_search_domain.py` | `parse_query()` — operator extraction, free-text fallback, unknown operators, multi-value OR, empty input, `is_empty()` |
| `tests/unit/test_search_domain.py` | `to_sql_like()` — `*` → `%`, `%` escape, `_` escape, combined |
| `tests/unit/test_services_domain.py` | `validate_port()` — boundary values 0, 1, 65535, 65536, None |
| `tests/unit/test_services_domain.py` | `validate_no_dependency_cycle()` — no cycle, direct cycle (A→B→A), transitive cycle (A→B→C→A), self, empty graph |
| `tests/unit/test_app_shell.py` | `app_shell()` context manager renders header + drawer (NiceGUI test client) |
| `tests/integration/test_services_api.py` | Full CRUD, 409 on duplicate name, 400 on bad port, cycle detection via API |
| `tests/integration/test_search_api.py` | `GET /api/devices?q=type:server`, wildcard IP, multi-operator AND, unknown operator fallback |
| `tests/integration/test_dashboard_api.py` | `GET /api/devices?sort=-updated_at&limit=5` returns correct order |

### 4.2 Quality Gate

```bash
docker compose exec api pytest                               # all tests pass
docker compose exec api mypy src/ --ignore-missing-imports   # zero type errors
docker compose build                                         # images build clean
```

---

## 5. Files to Create / Modify

### New Files

| File | Story | Estimated Lines |
|---|---|---|
| `src/ui/components/app_shell.py` | HT-026 | ~110 |
| `src/ui/pages/dashboard.py` | HT-026 | ~130 |
| `src/models/service.py` | HT-023 | ~90 |
| `src/models/service_dependency.py` | HT-023 | ~25 |
| `src/domain/services.py` | HT-023 | ~70 |
| `src/domain/search.py` | HT-020 | ~90 |
| `src/repositories/service_repository.py` | HT-023 | ~120 |
| `src/services/service_service.py` | HT-023 | ~150 |
| `src/api/routers/services.py` | HT-023 | ~180 |
| `alembic/versions/012_create_services_and_dependencies.py` | HT-023 | ~50 |
| `tests/unit/test_search_domain.py` | HT-020 | ~90 |
| `tests/unit/test_services_domain.py` | HT-023 | ~80 |
| `tests/integration/test_services_api.py` | HT-023 | ~150 |
| `tests/integration/test_search_api.py` | HT-020 | ~80 |
| `tests/integration/test_dashboard_api.py` | HT-026 | ~40 |

### Modified Files

| File | Story | Nature of Change |
|---|---|---|
| `src/models/types.py` | HT-023 | Add `ServiceProtocol`, `ServiceStatus` enums (+12 lines) |
| `src/models/device.py` | HT-023 | Add `services: list[ServiceResponse]` to `DeviceResponseEnriched` (+3 lines) |
| `src/repositories/device_repository.py` | HT-020/026 | Add `search()` function, extend `get_all()` with `sort` param (+75 lines) |
| `src/services/device_service.py` | HT-020/026 | Extend `get_all_enriched()` with `q`, `sort` params (+20 lines) |
| `src/api/routers/devices.py` | HT-020/026 | Add `q`, `sort` query params to list endpoint (+10 lines) |
| `src/api/routers/device_sub_routes.py` | HT-023 | Add `GET/POST /devices/{id}/services` (+45 lines) |
| `src/api/app.py` | HT-023 | Register `services_router` (+2 lines) |
| `src/main.py` | HT-026 | Register `dashboard` page (+1 line) |
| `src/ui/pages/login.py` | HT-026 | Change redirect target `/topology` → `/` (+0 net, 1 line changed) |
| `src/ui/pages/topology.py` | HT-026 | Wrap body in `app_shell`, remove standalone `ui.query` style call (+5 lines net) |
| `src/ui/pages/inventory.py` | HT-020/026 | Wrap in `app_shell`; add `q` param, operator autocomplete (~+35 lines) |
| `src/ui/pages/settings_locations.py` | HT-026 | Wrap in `app_shell` (+5 lines net) |
| `src/ui/pages/settings_users.py` | HT-026 | Wrap in `app_shell` (+5 lines net) |
| `src/ui/pages/settings_data.py` | HT-026 | Wrap in `app_shell` (+5 lines net) |
| `src/ui/pages/inventory_helpers.py` | HT-023 | Add Services column and row mapping (+15 lines) |
| `src/ui/components/canvas.py` | HT-023 | Add service tooltip JS to canvas init template (+40 lines) |

---

## 6. Implementation Order

The Feature-Engineer should implement in this dependency order:

1. **HT-023 enums + models** (`types.py`, `service.py`, `service_dependency.py`) — no dependencies
2. **HT-023 migration** — requires models
3. **HT-023 domain** (`services.py`) — pure, no deps
4. **HT-020 domain** (`search.py`) — pure, no deps
5. **HT-023 repository** — requires models + migration
6. **HT-023 service layer** — requires domain + repository
7. **HT-023 API routers** — requires service layer; register in `app.py`
8. **HT-020 repository extension** — requires search domain
9. **HT-020 service + API extension** — requires repository extension
10. **HT-026 `app_shell` component** — no external deps
11. **HT-026 dashboard page** — requires `app_shell`, all API endpoints working
12. **HT-026 page wrapping** — requires `app_shell`; update login redirect
13. **HT-023 canvas tooltip** — requires HT-023 API working
14. **HT-023 inventory column** — requires HT-023 API working
15. **HT-020 inventory UI** — requires HT-020 API working

Steps 1–4 and 5–7 within a story can be done in sequence per story; stories are otherwise independent and can be parallelised if multiple engineers are available.
