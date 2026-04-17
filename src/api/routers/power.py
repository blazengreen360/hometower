"""Power router — summary and global settings endpoints (HT-044)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.power_settings import PowerSettingsResponse, PowerSettingsUpdate
from src.models.power_summary import PowerSummaryResponse
from src.models.types import Role
from src.services import power_service
from src.utils.db import get_session

router = APIRouter(prefix="/power", tags=["power"])


@router.get(
    "/summary",
    response_model=PowerSummaryResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_power_summary(session: Session = Depends(get_session)) -> PowerSummaryResponse:
    """Return global and per-location power totals for Reader+ users."""
    return power_service.get_summary(session)


@router.get(
    "/settings",
    response_model=PowerSettingsResponse,
    dependencies=[Depends(require_role(Role.Admin))],
)
def get_power_settings(session: Session = Depends(get_session)) -> PowerSettingsResponse:
    """Return global power settings for Admin users."""
    return power_service.get_settings(session)


@router.put(
    "/settings",
    response_model=PowerSettingsResponse,
    dependencies=[Depends(require_role(Role.Admin))],
)
def put_power_settings(
    data: PowerSettingsUpdate,
    session: Session = Depends(get_session),
) -> PowerSettingsResponse:
    """Create or update global power settings for Admin users."""
    try:
        return power_service.upsert_settings(data, session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
