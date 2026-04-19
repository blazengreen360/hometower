"""Recent dashboard activity helpers for HT-082 summary reads."""
import uuid

from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from src.domain.cytoscape import extract_device_ids
from src.models.dashboard_summary import DashboardRecentActivityItem
from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.topology_history_entry import TopologyHistoryEntry
from src.models.workspace import Workspace
from src.repositories.dashboard_device_scope_support import DeviceScope
from src.repositories.dashboard_device_scope_support import _apply_device_scope

_RECENT_ACTIVITY_LIMIT = 5


def build_recent_activity(
    session: Session,
    scope: DeviceScope,
) -> list[DashboardRecentActivityItem]:
    activity = _recent_device_activity(session, scope) + _recent_topology_activity(
        session,
        scope.selected_workspace_id,
        scope.owner_id,
    )
    activity.sort(key=lambda item: item.timestamp, reverse=True)
    return activity[:_RECENT_ACTIVITY_LIMIT]


def _current_device_routes(
    session: Session,
    selected_workspace_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> dict[uuid.UUID, str]:
    statement = (
        select(Workspace.id, Topology.id, DiagramLayout.cytoscape_json)
        .join(Topology, col(DiagramLayout.id) == col(Topology.current_diagram_id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
        .order_by(col(DiagramLayout.updated_at).desc())
    )
    if owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == owner_id)
    if selected_workspace_id is not None:
        statement = statement.where(col(Workspace.id) == selected_workspace_id)

    routes: dict[uuid.UUID, str] = {}
    for workspace_id, topology_id, cytoscape_json in session.exec(statement).all():
        if not isinstance(cytoscape_json, dict):
            continue
        for device_id in extract_device_ids(cytoscape_json):
            routes.setdefault(
                device_id,
                f"/topology?workspace_id={workspace_id}&topology_id={topology_id}&device_id={device_id}",
            )
    return routes


def _recent_device_activity(
    session: Session,
    scope: DeviceScope,
) -> list[DashboardRecentActivityItem]:
    current_routes = _current_device_routes(
        session,
        scope.selected_workspace_id,
        scope.owner_id,
    )
    rows = session.exec(
        _apply_device_scope(
            select(Device.id, Device.name, Device.version, Device.updated_at)
            .order_by(col(Device.updated_at).desc())
            .limit(_RECENT_ACTIVITY_LIMIT),
            session,
            scope,
        )
    ).all()
    return [
        DashboardRecentActivityItem(
            kind="device_created" if version <= 1 else "device_updated",
            title=name,
            subtitle="Device added" if version <= 1 else "Device updated",
            timestamp=timestamp,
            route=current_routes.get(device_id, f"/inventory/edit/{device_id}"),
        )
        for device_id, name, version, timestamp in rows
    ]


def _recent_topology_activity(
    session: Session,
    selected_workspace_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> list[DashboardRecentActivityItem]:
    statement = (
        sa_select(  # type: ignore[call-overload]
            TopologyHistoryEntry.action,
            TopologyHistoryEntry.snapshot_name,
            TopologyHistoryEntry.created_at,
            Topology.id,
            Topology.name,
            Workspace.id,
            Workspace.name,
        )
        .join(Topology, col(TopologyHistoryEntry.topology_id) == col(Topology.id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
    )
    if owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == owner_id)
    if selected_workspace_id is not None:
        statement = statement.where(col(Workspace.id) == selected_workspace_id)
    rows = session.exec(
        statement.order_by(col(TopologyHistoryEntry.created_at).desc()).limit(
            _RECENT_ACTIVITY_LIMIT
        )
    ).all()
    return [
        DashboardRecentActivityItem(
            kind=f"topology_{action}",
            title=topology_name,
            subtitle=f"{workspace_name}: {snapshot_name}",
            timestamp=created_at,
            route=f"/topology?workspace_id={workspace_id}&topology_id={topology_id}",
        )
        for action, snapshot_name, created_at, topology_id, topology_name, workspace_id, workspace_name in rows
    ]