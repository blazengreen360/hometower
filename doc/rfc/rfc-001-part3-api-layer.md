# RFC-001 Part 3: API Layer Design

**Parts:** [Part 1 – System Overview](rfc-001-part1-system-overview.md) · [Part 2 – Data Model](rfc-001-part2-data-model.md) · [Part 3 (this)] · [Part 4 – Integrations](rfc-001-part4-integrations.md) · [Part 5 – Auth & Ops](rfc-001-part5-auth-ops.md)

---

## 1. Principles

1. **Pydantic validates all input** before any service call. If the request body is invalid, FastAPI returns a `422 Unprocessable Entity` automatically.
2. **Services own all business logic.** Routers are thin: validate → call service → return response.
3. **RBAC is enforced via FastAPI dependency injection** using `require_role()` from `src/domain/rbac.py`. Roles are hierarchical: Admin > Contributor > Reader.
4. **Consistent error shape** across all endpoints: `{"detail": "human-readable message"}`.
5. **Pagination** uses `page` (1-based) and `limit` (max 100) query parameters. Response includes `total`, `page`, `limit`, `items`.
6. **All IDs are UUIDs** in string format with `format: uuid` validation.

---

## 2. Route Table — All Phase 1 Endpoints

### Auth (`src/api/routers/auth.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| POST | `/api/auth/login` | Public | HT-001 |
| POST | `/api/auth/logout` | Any authenticated | HT-001 |

### Devices (`src/api/routers/devices.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/devices` | Reader | HT-002 |
| POST | `/api/devices` | Contributor | HT-002 |
| GET | `/api/devices/{device_id}` | Reader | HT-002 |
| PATCH | `/api/devices/{device_id}` | Contributor | HT-002 |
| DELETE | `/api/devices/{device_id}` | Contributor | HT-002 |
| GET | `/api/devices/search` | Reader | HT-020 |

### Connections (`src/api/routers/connections.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/connections` | Reader | HT-004 |
| POST | `/api/connections` | Contributor | HT-004 |
| GET | `/api/connections/{connection_id}` | Reader | HT-004 |
| PATCH | `/api/connections/{connection_id}` | Contributor | HT-004 |
| DELETE | `/api/connections/{connection_id}` | Contributor | HT-004 |

### Locations (`src/api/routers/locations.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/locations` | Reader | HT-005 |
| POST | `/api/locations` | Contributor | HT-005 |
| GET | `/api/locations/{location_id}` | Reader | HT-005 |
| PATCH | `/api/locations/{location_id}` | Contributor | HT-005 |
| DELETE | `/api/locations/{location_id}` | Contributor | HT-005 |

### Tags (`src/api/routers/tags.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/tags` | Reader | HT-006 |
| POST | `/api/tags` | Contributor | HT-006 |
| GET | `/api/tags/{tag_id}` | Reader | HT-006 |
| PATCH | `/api/tags/{tag_id}` | Contributor | HT-006 |
| DELETE | `/api/tags/{tag_id}` | Contributor | HT-006 |
| POST | `/api/devices/{device_id}/tags` | Contributor | HT-006 |
| DELETE | `/api/devices/{device_id}/tags/{tag_id}` | Contributor | HT-006 |

### Custom Fields (`src/api/routers/custom_fields.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/devices/{device_id}/fields` | Reader | HT-007 |
| POST | `/api/devices/{device_id}/fields` | Contributor | HT-007 |
| PATCH | `/api/devices/{device_id}/fields/{field_id}` | Contributor | HT-007 |
| DELETE | `/api/devices/{device_id}/fields/{field_id}` | Contributor | HT-007 |

### Diagram Layouts (`src/api/routers/diagrams.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/diagrams` | Reader | HT-003 |
| POST | `/api/diagrams` | Contributor | HT-003 |
| GET | `/api/diagrams/{diagram_id}` | Reader | HT-003 |
| DELETE | `/api/diagrams/{diagram_id}` | Admin | HT-003 |

> **Note:** `DELETE /api/diagrams/{diagram_id}` requires **Admin** role. Diagrams are shared team artifacts; restricting deletion to Admin prevents accidental or malicious loss by Contributor users who may lack visibility into who else depends on a saved layout.

### Users (`src/api/routers/users.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/users` | Admin | HT-019 |
| POST | `/api/users` | Admin | HT-019 |
| GET | `/api/users/{user_id}` | Admin | HT-019 |
| PATCH | `/api/users/{user_id}` | Admin | HT-019 |
| DELETE | `/api/users/{user_id}` | Admin | HT-019 |

### Export / Import (`src/api/routers/export_.py`, `import_.py`)

| Method | Path | Min Role | HT Story |
|---|---|---|---|
| GET | `/api/export/json` | Reader | HT-012 |
| POST | `/api/import/json` | Admin | HT-013 |

---

## 3. RBAC Enforcement Pattern

### Domain layer — `src/domain/rbac.py`

```python
from src.models.types import Role
from fastapi import Request, HTTPException

ROLE_HIERARCHY: dict[Role, int] = {
    Role.Admin: 3,
    Role.Contributor: 2,
    Role.Reader: 1,
}

def can_perform(user_role: Role, required_role: Role) -> bool:
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required_role]

def require_role(required: Role):
    """FastAPI dependency. Raises 403 if user lacks the required role."""
    def dependency(request: Request) -> None:
        user_role = Role(request.state.role)
        if not can_perform(user_role, required):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    return dependency
```

### Router usage

```python
# src/api/routers/devices.py
from src.domain.rbac import require_role
from src.models.types import Role

@router.post("/", dependencies=[Depends(require_role(Role.Contributor))])
async def create_device(data: DeviceCreate, session: Session = Depends(get_session)):
    return await device_service.create(data, session)
```

---

## 4. Error Handling Strategy

| Scenario | HTTP Status | Detail message |
|---|---|---|
| Invalid request body | 422 | FastAPI automatic Pydantic validation error |
| Resource not found | 404 | `"{ResourceName} not found"` |
| Insufficient role | 403 | `"Insufficient permissions"` |
| Not authenticated | 401 | `"Not authenticated"` |
| JWT expired | 401 | `"Token expired"` |
| Business rule violation | 400 | Descriptive: `"Cannot delete device with active connections"` |
| Duplicate unique field | 409 | `"{Field} already exists"` |
| Internal error | 500 | `"Internal server error"` (no stack traces in response) |

All errors use the shape: `{"detail": "string"}`.

Stack traces are logged via Loguru at `ERROR` level and never appear in API responses.

### Domain Validation Pattern

Business rule violations (400-level) must be detected by a **pure domain function**, never inline in the router handler. This keeps handlers thin and domain logic independently testable.

```python
# src/domain/devices.py
def validate_device_deletable(connection_count: int) -> None:
    """Raises ValueError if the device has active connections."""
    if connection_count > 0:
        raise ValueError("Cannot delete device with active connections")
```

```python
# src/services/device_service.py
async def delete(device_id: uuid.UUID, session: Session) -> None:
    device = device_repo.get_or_404(device_id, session)
    count = connection_repo.count_for_device(device_id, session)
    try:
        validate_device_deletable(count)          # pure domain call
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    device_repo.delete(device, session)
```

Routers never perform business rule checks directly — they delegate entirely to the service layer.

---

## 5. Search Endpoint — `GET /api/devices/search`

Query parameters:

| Param | Type | Description |
|---|---|---|
| `q` | string | Free-text search on name, os, notes (case-insensitive ILIKE) |
| `type` | DeviceType | Filter by device type |
| `location_id` | UUID | Filter by location |
| `tag` | string | Filter by tag name |
| `page` | int (default 1) | Pagination page |
| `limit` | int (default 50, max 100) | Items per page |

The domain layer (`src/domain/inventory.py`) builds the filter predicate. The repository executes it. The service assembles the response.

---

## 6. Pagination Response Shape

```python
class PaginatedResponse(SQLModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
```

All list endpoints (`GET /api/devices`, `GET /api/connections`, etc.) return this shape.

---

## 7. Router Registration — `src/api/app.py`

```python
from fastapi import FastAPI
from nicegui import ui
from src.api.routers import auth, devices, connections, locations, tags
from src.api.routers import custom_fields, diagrams, users, export_, import_, search
from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.logging import LoggingMiddleware

app = FastAPI(title="Hometower", docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

for router in [auth, devices, connections, locations, tags,
               custom_fields, diagrams, users, export_, import_, search]:
    app.include_router(router.router, prefix="/api")

# NiceGUI pages are registered in src/ui/pages/ via @ui.page decorators
ui.run_with(app, host="0.0.0.0", port=8080, title="Hometower")
```
