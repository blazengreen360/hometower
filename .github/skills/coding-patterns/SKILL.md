---
name: coding-patterns
description: Established code patterns for Hometower. SQLModel schema hierarchy (Base/Table/Create/Update/Response/Enriched), repository pattern (flush not commit), service pattern (domain-first, try/commit/rollback), FastAPI route pattern (RBAC on every handler), NiceGUI+JS bridge pattern, and test fixture conventions. Read this before writing any implementation code.
---

# coding-patterns

Established patterns in this codebase. Never introduce new conventions — match existing code.

## SQLModel Schema Hierarchy

Every entity: `Base → Table → Create → Update → Response → ResponseEnriched`

```python
class DeviceBase(SQLModel):                       # shared fields + validators
    name: str = Field(min_length=1, max_length=255)

class Device(DeviceBase, table=True):              # UUID PK, version, timestamps
    __tablename__ = "devices"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    version: int = Field(default=1)                # optimistic locking
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

class DeviceCreate(DeviceBase): pass               # inherits Base validators

class DeviceUpdate(SQLModel):                      # standalone — all Optional, version required
    name: Optional[str] = None
    version: int                                   # optimistic concurrency

class DeviceResponse(DeviceBase):                  # id + version + timestamps
    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime

class DeviceResponseEnriched(DeviceResponse):      # joined fields
    tags: list[TagResponse] = []
    location_name: Optional[str] = None
```

## Repository Pattern

```python
def create(session: Session, entity: Device) -> Device:
    session.add(entity)
    session.flush()        # NOT commit — service owns transaction
    session.refresh(entity)
    return entity
```

Repositories may accept an existing `Session`, but they never `commit()` or `rollback()`. Transaction ownership stays above the repository layer.

## Service Pattern

```python
def create(data: DeviceCreate, session: Session) -> Device:
    validated_ip = device_domain.validate_ip(data.ip)    # domain first
    device = Device(name=data.name, ip=validated_ip)
    try:
        result = device_repository.create(session, device)
        session.commit()                                  # service owns commit
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Conflict") from exc
    logger.info("Device created: id={} name={}", result.id, result.name)
    return result
```

Services may accept a request-scoped `Session` from routers or approved infrastructure entry points. Services own `commit()` / `rollback()` for application workflows.

## FastAPI Route Pattern

```python
@router.get("/devices/{device_id}", response_model=DeviceRead)
async def get_device(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(Role.READER)),  # NEVER omit
) -> DeviceRead:
    return device_service.get_by_id(device_id, session)
```

Routers may inject and pass a request-scoped `Session`, but they do not import repositories directly and should not own `commit()` / `rollback()` except where a temporary, explicitly documented contract migration is in progress.

## Session Boundary Contract

- `Session` creation is limited to approved infrastructure entry points such as `src/utils/db.py`, `src/api/app.py`, and `src/api/middleware/auth.py`.
- Routers may inject `Session` via `Depends(get_session)` and pass it to services.
- Services may accept `Session` and own transaction lifecycle actions.
- Repositories may accept `Session`, perform query/mutation mechanics, and never `commit()` or `rollback()`.

## NiceGUI + JS Bridge

```python
# JS string constants injected via ui.add_body_html()
VIEW_MODE_JS: str = """(function() { window.htSetViewMode = function() { ... }; })();"""

# Called from Python
await ui.run_javascript("htSetViewMode()")
```

For canvas-specific patterns, see the `canvas-bridge` skill.

## Test Fixtures

```python
# Fixtures from conftest.py: session, client, admin_token, contributor_token, reader_token
# uuid4 for unique names — prevent cross-test collisions
user = User(username=f"test_{uuid4().hex[:8]}", email=f"test_{uuid4().hex[:8]}@test.local", ...)
```
