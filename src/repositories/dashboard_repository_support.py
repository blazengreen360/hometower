"""Helper queries and normalizers for HT-082 dashboard summary reads."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Mapping
from urllib.parse import quote

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from src.models.dashboard_summary import DashboardBreakdownCount
from src.models.dashboard_summary import DashboardPowerWidget
from src.models.dashboard_summary import DashboardRecentActivityItem
from src.models.dashboard_summary import DashboardWorkspaceOption
from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.power_settings import PowerSettings
from src.models.topology import Topology
from src.models.topology_history_entry import TopologyHistoryEntry
from src.models.types import DeviceStatus, DeviceType
from src.models.workspace import Workspace
_ALL_WORKSPACES = "All Workspaces"
_MONTHLY_HOURS = 24 * 30.44
_RECENT_ACTIVITY_LIMIT = 5
_RECENT_EDIT_WINDOW_DAYS = 7


class ScopedDeviceIds(set[uuid.UUID]):
    def __init__(
        self,
        values: set[uuid.UUID],
        selected_workspace_id: uuid.UUID | None,
    ) -> None:
        super().__init__(values)
        self.selected_workspace_id = selected_workspace_id


def list_workspaces(session: Session, owner_id: uuid.UUID | None) -> list[tuple[uuid.UUID, str]]:
    statement = select(Workspace.id, Workspace.name)
    if owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == owner_id)
    rows = session.exec(statement.order_by(col(Workspace.name))).all()
    return [(workspace_id, name) for workspace_id, name in rows]
def resolve_workspace_selection(workspaces: list[tuple[uuid.UUID, str]], selected_workspace_id: uuid.UUID | None) -> tuple[uuid.UUID | None, str]:
    names = {workspace_id: name for workspace_id, name in workspaces}
    if selected_workspace_id is not None and selected_workspace_id in names:
        return selected_workspace_id, names[selected_workspace_id]
    return None, _ALL_WORKSPACES
def scoped_device_ids(session: Session, selected_workspace_id: uuid.UUID | None, owner_id: uuid.UUID | None) -> set[uuid.UUID]:
    statement = (
        select(DiagramLayout.cytoscape_json)
        .join(Topology, col(DiagramLayout.id) == col(Topology.current_diagram_id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
    )
    if owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == owner_id)
    if selected_workspace_id is not None:
        statement = statement.where(col(Workspace.id) == selected_workspace_id)
    device_ids: set[uuid.UUID] = set()
    for cytoscape_json in session.exec(statement).all():
        device_ids.update(_extract_device_ids(cytoscape_json))
    return ScopedDeviceIds(device_ids, selected_workspace_id)
def count_devices(session: Session, device_ids: set[uuid.UUID], offline_only: bool = False) -> int:
    if not device_ids:
        return 0
    statement = select(func.count()).select_from(Device).where(col(Device.id).in_(device_ids))
    if offline_only:
        statement = statement.where(col(Device.status) == DeviceStatus.Offline)
    return int(session.exec(statement).one())
def count_topologies(session: Session, selected_workspace_id: uuid.UUID | None, owner_id: uuid.UUID | None) -> int:
    statement = (
        select(func.count())
        .select_from(Topology)
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
    )
    if owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == owner_id)
    if selected_workspace_id is not None:
        statement = statement.where(col(Workspace.id) == selected_workspace_id)
    return int(session.exec(statement).one())
def build_status_counts(session: Session, device_ids: set[uuid.UUID]) -> list[DashboardBreakdownCount]:
    if not device_ids:
        return []
    selected_workspace_id = getattr(device_ids, "selected_workspace_id", None)
    rows = session.exec(select(Device.status, func.count()).where(col(Device.id).in_(device_ids)).group_by(col(Device.status))).all()
    counts = {
        (status.value if isinstance(status, DeviceStatus) else str(status)): int(total)
        for status, total in rows
    }
    return [
        DashboardBreakdownCount(
            key=status.value,
            count=counts.get(status.value, 0),
            route=_inventory_route(selected_workspace_id, "status", status.value),
        )
        for status in DeviceStatus
        if counts.get(status.value, 0) > 0
    ]
def build_type_counts(session: Session, device_ids: set[uuid.UUID]) -> list[DashboardBreakdownCount]:
    if not device_ids:
        return []
    selected_workspace_id = getattr(device_ids, "selected_workspace_id", None)
    rows = session.exec(select(Device.type, func.count()).where(col(Device.id).in_(device_ids)).group_by(col(Device.type))).all()
    counts = {
        (device_type.value if isinstance(device_type, DeviceType) else str(device_type)): int(total)
        for device_type, total in rows
    }
    return [
        DashboardBreakdownCount(
            key=device_type.value,
            count=counts.get(device_type.value, 0),
            route=_inventory_route(selected_workspace_id, "type", device_type.value),
        )
        for device_type in DeviceType
        if counts.get(device_type.value, 0) > 0
    ]
def count_recent_edits(session: Session, device_ids: set[uuid.UUID], selected_workspace_id: uuid.UUID | None, owner_id: uuid.UUID | None) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RECENT_EDIT_WINDOW_DAYS)
    device_total = 0
    if device_ids:
        device_total = int(session.exec(select(func.count()).select_from(Device).where(col(Device.id).in_(device_ids)).where(col(Device.updated_at) >= cutoff)).one())
    statement = (
        select(func.count())
        .select_from(TopologyHistoryEntry)
        .join(Topology, col(TopologyHistoryEntry.topology_id) == col(Topology.id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
        .where(col(TopologyHistoryEntry.created_at) >= cutoff)
    )
    if owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == owner_id)
    if selected_workspace_id is not None:
        statement = statement.where(col(Workspace.id) == selected_workspace_id)
    topology_total = int(session.exec(statement).one())
    return device_total + topology_total
def build_power_widget(session: Session, device_ids: set[uuid.UUID], workspaces: list[tuple[uuid.UUID, str]], selected_workspace_id: uuid.UUID | None, selected_workspace_name: str) -> DashboardPowerWidget:
    total_watts = _sum_device_watts(session, device_ids)
    settings = session.get(PowerSettings, "global")
    estimated_monthly_cost = None
    if settings is not None and settings.cost_per_kwh is not None:
        estimated_monthly_cost = round((total_watts / 1000) * _MONTHLY_HOURS * settings.cost_per_kwh, 2)
    options = [DashboardWorkspaceOption(name=_ALL_WORKSPACES)]
    options.extend(DashboardWorkspaceOption(id=workspace_id, name=name) for workspace_id, name in workspaces)
    return DashboardPowerWidget(
        workspace_options=options,
        selected_workspace_id=selected_workspace_id,
        selected_workspace_name=selected_workspace_name,
        total_watts=total_watts,
        estimated_monthly_cost=estimated_monthly_cost,
        currency=settings.currency if settings is not None else None,
    )
def build_recent_activity(session: Session, device_ids: set[uuid.UUID], selected_workspace_id: uuid.UUID | None, owner_id: uuid.UUID | None) -> list[DashboardRecentActivityItem]:
    activity = _recent_device_activity(session, device_ids, selected_workspace_id) + _recent_topology_activity(session, selected_workspace_id, owner_id)
    activity.sort(key=lambda item: item.timestamp, reverse=True)
    return activity[:_RECENT_ACTIVITY_LIMIT]


def _inventory_route(
    selected_workspace_id: uuid.UUID | None,
    key: str,
    value: str,
) -> str:
    suffix = f"{key}={quote(value, safe='')}"
    if selected_workspace_id is None:
        return f"/inventory?{suffix}"
    return f"/inventory?workspace_id={selected_workspace_id}&{suffix}"
def _extract_device_ids(cytoscape_json: Mapping[str, object]) -> set[uuid.UUID]:
    elements = cytoscape_json.get("elements")
    nodes = elements.get("nodes") if isinstance(elements, dict) else elements
    if not isinstance(nodes, list):
        return set()
    device_ids: set[uuid.UUID] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        group = node.get("group")
        if group is not None and group != "nodes":
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        candidate = data.get("device_id", data.get("id"))
        if candidate is None:
            continue
        try:
            device_ids.add(uuid.UUID(str(candidate)))
        except ValueError:
            continue
    return device_ids
def _sum_device_watts(session: Session, device_ids: set[uuid.UUID]) -> int:
    if not device_ids:
        return 0
    rows = session.exec(select(Device.power_watts).where(col(Device.id).in_(device_ids))).all()
    return sum(watts or 0 for watts in rows)
def _recent_device_activity(session: Session, device_ids: set[uuid.UUID], selected_workspace_id: uuid.UUID | None) -> list[DashboardRecentActivityItem]:
    if not device_ids:
        return []
    rows = session.exec(select(Device.name, Device.version, Device.updated_at).where(col(Device.id).in_(device_ids)).order_by(col(Device.updated_at).desc()).limit(_RECENT_ACTIVITY_LIMIT)).all()
    return [
        DashboardRecentActivityItem(
            kind="device_created" if version <= 1 else "device_updated",
            title=name,
            subtitle="Device added" if version <= 1 else "Device updated",
            timestamp=timestamp,
            route=_inventory_route(selected_workspace_id, "search", name),
        )
        for name, version, timestamp in rows
    ]
def _recent_topology_activity(session: Session, selected_workspace_id: uuid.UUID | None, owner_id: uuid.UUID | None) -> list[DashboardRecentActivityItem]:
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
    rows = session.exec(statement.order_by(col(TopologyHistoryEntry.created_at).desc()).limit(_RECENT_ACTIVITY_LIMIT)).all()
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
