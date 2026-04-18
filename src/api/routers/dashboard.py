"""Dashboard router — aggregate summary endpoint for HT-082."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.dashboard_summary import DashboardSummaryResponse
from src.models.types import Role
from src.services import dashboard_service
from src.utils.db import get_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _owner_id(request: Request) -> uuid.UUID:
    return uuid.UUID(request.state.user_id)


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_dashboard_summary(
    request: Request,
    workspace_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
) -> DashboardSummaryResponse:
    """Return the dashboard aggregate summary for Reader+ users."""
    return dashboard_service.get_summary(
        owner_id=_owner_id(request),
        session=session,
        workspace_id=workspace_id,
    )
