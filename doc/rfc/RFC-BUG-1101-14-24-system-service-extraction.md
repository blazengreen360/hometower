# RFC: Extract System & Health DB Queries into Service Layer

**Fixes**: BUG-1101-14, BUG-1101-24
**Status**: Draft

## 1. Overview

`src/api/routers/system.py` and `src/api/routers/health.py` execute SQL directly, violating the layered architecture rule that routers delegate to services. This RFC extracts all DB access into a new `src/services/system_service.py`.

## 2. New File: `src/services/system_service.py`

This module hides **the specific SQL queries used to gather system-level diagnostics** (entity counts, DB version, DB size, connectivity probe). If the ORM, query strategy, or database engine changes, only this file is affected.

```python
"""System-level queries: inventory counts, DB diagnostics, health probe."""
from typing import Optional

from sqlalchemy import func, text
from sqlmodel import Session, select

from src.models.connection import Connection
from src.models.custom_field import CustomField
from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.location import Location
from src.models.tag import Tag
from src.models.user import User
from src.utils.logger import logger


def get_entity_counts(session: Session) -> dict[str, int]:
    """Return counts for devices, connections, locations, tags, custom_fields, diagrams."""

def get_user_count(session: Session) -> int:
    """Return total user count (admin-only stat)."""

def get_db_diagnostics(session: Session) -> tuple[Optional[str], Optional[int]]:
    """Return (db_version, db_size_bytes). None values on non-PG or failure."""

def check_db_connectivity(session: Session) -> bool:
    """Execute ``SELECT 1``; return True if reachable, False otherwise."""
```

### Function Details

| Function | Queries Moved From | Returns |
|---|---|---|
| `get_entity_counts` | `system.py` lines 51-56 (6× `select(func.count())`) | `{"devices": int, "connections": int, ...}` |
| `get_user_count` | `system.py` line 59 | `int` |
| `get_db_diagnostics` | `system.py` lines 63-72 (`version()`, `pg_database_size()`) | `(Optional[str], Optional[int])` |
| `check_db_connectivity` | `health.py` lines 45-46 (`SELECT 1`) | `bool` |

## 3. Changes to `src/api/routers/system.py`

- **Remove** imports: `func`, `text`, `select`, and all model imports (`Device`, `Connection`, `Location`, `Tag`, `CustomField`, `DiagramLayout`, `User`).
- **Add** import: `from src.services.system_service import get_entity_counts, get_user_count, get_db_diagnostics`.
- **Replace** inline SQL in `get_system_stats()` with three service calls:
  ```python
  counts = get_entity_counts(session)
  users = get_user_count(session) if Role(request.state.role) == Role.Admin else None
  db_version, db_size_bytes = get_db_diagnostics(session)
  return SystemStats(**counts, users=users, db_version=db_version, db_size_bytes=db_size_bytes)
  ```
- `SystemStats` Pydantic model stays in this file (API-layer concern).

## 4. Changes to `src/api/routers/health.py`

- **Remove** imports: `text` from sqlalchemy, `Session`/`SQLModel` direct use for queries.
- **Add** import: `from src.services.system_service import check_db_connectivity`.
- **Replace** inline `SELECT 1` block with:
  ```python
  db_ok = check_db_connectivity(session)
  db_status = "connected" if db_ok else "disconnected"
  health_status = "healthy" if db_ok else "unhealthy"
  if not db_ok:
      response.status_code = 503
  ```
- `HealthResponse` model, `_start_time`, and uptime calc stay in this file.

## 5. Repository Layer

No new repository needed. The queries are cross-cutting aggregate counts and raw SQL diagnostics — they don't map to CRUD on a single entity. Placing them in `system_service.py` directly is consistent with the "one service per feature area" pattern.

## 6. Security Boundaries

No change. RBAC enforcement (`require_role(Role.Reader)`) stays in the router decorator. The admin-only user count guard stays in the router handler. The health endpoint remains public.

## 7. Files to Create/Modify

| File | Action |
|---|---|
| `src/services/system_service.py` | **Create** — 4 functions extracted from routers |
| `src/api/routers/system.py` | **Modify** — strip SQL, delegate to service |
| `src/api/routers/health.py` | **Modify** — strip DB ping, delegate to service |
| `tests/unit/test_system_service.py` | **Create** — unit tests for all 4 functions |

## 8. Validation

- `docker compose exec api pytest tests/unit/test_system_service.py -v` — new unit tests pass
- `docker compose exec api pytest` — existing system/health endpoint tests still pass
- `docker compose exec api mypy src/ --ignore-missing-imports` — zero errors
- Manual: `grep -rn "session.exec\|session.execute" src/api/routers/system.py src/api/routers/health.py` returns zero matches after refactor
