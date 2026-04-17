"""System stats router — GET /api/system/stats (HT-035)."""
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, SQLModel

from src.api.dependencies.rbac import require_role
from src.models.types import Role
from src.services.system_service import get_db_diagnostics, get_entity_counts, get_user_count
from src.utils.db import get_session

router = APIRouter(tags=["system"])


class SystemStats(SQLModel):
    devices: int
    connections: int
    locations: int
    tags: int
    custom_fields: int
    diagrams: int
    users: Optional[int] = None  # Admin-only; None for non-admins


class AdminSystemStats(SystemStats):
    db_version: Optional[str] = None
    db_size_bytes: Optional[int] = None


@router.get(
    "/system/stats",
    response_model=SystemStats | AdminSystemStats,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_system_stats(
    request: Request,
    session: Session = Depends(get_session),
) -> SystemStats | AdminSystemStats:
    """Return inventory counts and DB diagnostics.

    Requires Reader role minimum. User count is Admin-only.
    DB version and size are PostgreSQL-specific; null in non-PG environments.
    """
    counts = get_entity_counts(session)
    is_admin = Role(request.state.role) == Role.Admin
    users = get_user_count(session) if is_admin else None

    if not is_admin:
        return SystemStats(**counts, users=users)

    db_version, db_size_bytes = get_db_diagnostics(session)

    return AdminSystemStats(
        **counts,
        users=users,
        db_version=db_version,
        db_size_bytes=db_size_bytes,
    )
