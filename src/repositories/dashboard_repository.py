"""Aggregate dashboard repository for HT-082 summary reads."""
import uuid

from sqlmodel import Session

from src.models.dashboard_summary import DashboardInventoryBreakdown
from src.models.dashboard_summary import DashboardSummaryResponse
from src.repositories.dashboard_repository_support import build_power_widget
from src.repositories.dashboard_repository_support import build_recent_activity
from src.repositories.dashboard_repository_support import build_status_counts
from src.repositories.dashboard_repository_support import build_type_counts
from src.repositories.dashboard_repository_support import count_devices
from src.repositories.dashboard_repository_support import count_recent_edits
from src.repositories.dashboard_repository_support import count_topologies
from src.repositories.dashboard_repository_support import list_workspaces
from src.repositories.dashboard_repository_support import resolve_workspace_selection


def get_summary(
    session: Session,
    selected_workspace_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> DashboardSummaryResponse:
    """Return the HT-082 dashboard summary read model."""
    workspaces = list_workspaces(session, owner_id)
    selected_workspace_id, selected_workspace_name = resolve_workspace_selection(
        workspaces,
        selected_workspace_id,
    )
    return DashboardSummaryResponse(
        devices=count_devices(session),
        workspaces=len(workspaces),
        topologies=count_topologies(session, owner_id),
        offline_devices=count_devices(session, offline_only=True),
        recent_edits=count_recent_edits(session, owner_id),
        power=build_power_widget(
            session,
            workspaces,
            selected_workspace_id,
            selected_workspace_name,
            owner_id,
        ),
        inventory_breakdown=DashboardInventoryBreakdown(
            status_counts=build_status_counts(session),
            type_counts=build_type_counts(session),
        ),
        recent_activity=build_recent_activity(session, owner_id),
    )
