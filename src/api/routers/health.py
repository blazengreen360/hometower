"""Health check router — GET /api/health.

Returns service status, version, database connectivity, and uptime.
This endpoint is public (no JWT required).
"""
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session, SQLModel

from src.__version__ import __version__
from src.models.user import User
from src.services.system_service import check_db_connectivity
from src.utils.auth import JWTError, decode_jwt
from src.utils.db import get_session

router = APIRouter(tags=["health"])

# Module-level start time — recorded once at import
_start_time: float = time.time()


class PublicHealthResponse(SQLModel):
    status: Literal["healthy", "unhealthy"]


class HealthResponse(PublicHealthResponse):
    status: Literal["healthy", "unhealthy"]
    version: str
    database: Literal["connected", "disconnected"]
    uptime_seconds: float


def _get_authenticated_user(request: Request, session: Session) -> User | None:
    """Mirror auth middleware semantics for the excluded health route."""
    token = request.cookies.get("ht_access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header.removeprefix("Bearer ")

    try:
        payload = decode_jwt(token)
        user_id = uuid.UUID(str(payload["sub"]))
        token_version = int(payload["version"])
    except (JWTError, KeyError, TypeError, ValueError):
        return None

    user = session.get(User, user_id)
    if user is None or user.token_version != token_version or not user.is_active:
        return None
    return user


@router.get("/health", response_model=PublicHealthResponse | HealthResponse)
def health_check(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> PublicHealthResponse | HealthResponse:
    """Return service health, database connectivity, and uptime.

    HTTP 200 when healthy, HTTP 503 when the database is unreachable.
    No authentication required.
    """
    uptime = round(time.time() - _start_time, 3)

    db_ok = check_db_connectivity(session)
    db_status: Literal["connected", "disconnected"] = "connected" if db_ok else "disconnected"
    health_status: Literal["healthy", "unhealthy"] = "healthy" if db_ok else "unhealthy"
    if not db_ok:
        response.status_code = 503
        return PublicHealthResponse(status=health_status)

    if _get_authenticated_user(request, session) is None:
        return PublicHealthResponse(status=health_status)

    return HealthResponse(
        status=health_status,
        version=__version__,
        database=db_status,
        uptime_seconds=uptime,
    )
