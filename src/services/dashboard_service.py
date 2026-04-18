"""Dashboard service — aggregate summary orchestration for HT-082."""
import uuid

from fastapi import HTTPException
from sqlmodel import Session

from src.models.dashboard_summary import DashboardSummaryResponse
from src.repositories import dashboard_repository, workspace_repository


def get_summary(
    owner_id: uuid.UUID,
    session: Session,
    workspace_id: uuid.UUID | None = None,
) -> DashboardSummaryResponse:
    """Return the dashboard aggregate summary for the current owner."""
    if workspace_id is not None:
        workspace = workspace_repository.get_by_id(session, workspace_id)
        if workspace is None or workspace.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Workspace not found")

    return dashboard_repository.get_summary(
        session,
        selected_workspace_id=workspace_id,
        owner_id=owner_id,
    )
