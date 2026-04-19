"""Helper queries and normalizers for HT-082 dashboard summary reads."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Mapping
from urllib.parse import quote

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.domain.cytoscape import extract_device_ids
from src.models.dashboard_summary import DashboardBreakdownCount
from src.models.dashboard_summary import DashboardPowerWidget
from src.models.dashboard_summary import DashboardWorkspaceOption
from src.models.device import Device
from src.models.power_settings import PowerSettings
from src.models.topology import Topology
from src.models.topology_history_entry import TopologyHistoryEntry
from src.models.types import DeviceStatus, DeviceType
from src.models.workspace import Workspace
from src.repositories.dashboard_device_scope_support import DeviceScope
from src.repositories.dashboard_device_scope_support import _apply_device_scope

_ALL_WORKSPACES = "All Workspaces"
_MONTHLY_HOURS = 24 * 30.44
_RECENT_EDIT_WINDOW_DAYS = 7


def list_workspaces(
    session: Session,
    owner_id: uuid.UUID | None,
) -> list[tuple[uuid.UUID, str]]:
    statement = select(Workspace.id, Workspace.name)
    if owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == owner_id)
    rows = session.exec(statement.order_by(col(Workspace.name))).all()
    return [(workspace_id, name) for workspace_id, name in rows]


def resolve_workspace_selection(
    workspaces: list[tuple[uuid.UUID, str]],
    selected_workspace_id: uuid.UUID | None,
) -> tuple[uuid.UUID | None, str]:
    names = {workspace_id: name for workspace_id, name in workspaces}
    if selected_workspace_id is not None and selected_workspace_id in names:
        return selected_workspace_id, names[selected_workspace_id]
    return None, _ALL_WORKSPACES


def count_devices(
    session: Session,
    scope: DeviceScope,
    offline_only: bool = False,
) -> int:
    statement = _apply_device_scope(select(func.count()).select_from(Device), session, scope)
    if offline_only:
        statement = statement.where(col(Device.status) == DeviceStatus.Offline)
    return int(session.exec(statement).one())


def count_topologies(
    session: Session,
    selected_workspace_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> int:
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


def build_status_counts(
    session: Session,
    scope: DeviceScope,
) -> list[DashboardBreakdownCount]:
    rows = session.exec(
        _apply_device_scope(
            select(Device.status, func.count()).group_by(col(Device.status)),
            session,
            scope,
        )
    ).all()
    counts = {
        (status.value if isinstance(status, DeviceStatus) else str(status)): int(total)
        for status, total in rows
    }
    return [
        DashboardBreakdownCount(
            key=status.value,
            count=counts.get(status.value, 0),
            route=_inventory_route(scope.selected_workspace_id, "status", status.value),
        )
        for status in DeviceStatus
        if counts.get(status.value, 0) > 0
    ]


def build_type_counts(
    session: Session,
    scope: DeviceScope,
) -> list[DashboardBreakdownCount]:
    rows = session.exec(
        _apply_device_scope(
            select(Device.type, func.count()).group_by(col(Device.type)),
            session,
            scope,
        )
    ).all()
    counts = {
        (device_type.value if isinstance(device_type, DeviceType) else str(device_type)): int(total)
        for device_type, total in rows
    }
    return [
        DashboardBreakdownCount(
            key=device_type.value,
            count=counts.get(device_type.value, 0),
            route=_inventory_route(scope.selected_workspace_id, "type", device_type.value),
        )
        for device_type in DeviceType
        if counts.get(device_type.value, 0) > 0
    ]


def count_recent_edits(session: Session, scope: DeviceScope) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RECENT_EDIT_WINDOW_DAYS)
    device_total = int(
        session.exec(
            _apply_device_scope(
                select(func.count())
                .select_from(Device)
                .where(col(Device.updated_at) >= cutoff),
                session,
                scope,
            )
        ).one()
    )
    statement = (
        select(func.count())
        .select_from(TopologyHistoryEntry)
        .join(Topology, col(TopologyHistoryEntry.topology_id) == col(Topology.id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
        .where(col(TopologyHistoryEntry.created_at) >= cutoff)
    )
    if scope.owner_id is not None:
        statement = statement.where(col(Workspace.owner_id) == scope.owner_id)
    if scope.selected_workspace_id is not None:
        statement = statement.where(col(Workspace.id) == scope.selected_workspace_id)
    return device_total + int(session.exec(statement).one())


def build_power_widget(
    session: Session,
    scope: DeviceScope,
    workspaces: list[tuple[uuid.UUID, str]],
    selected_workspace_name: str,
) -> DashboardPowerWidget:
    total_watts = _sum_device_watts(session, scope)
    settings = session.get(PowerSettings, "global")
    estimated_monthly_cost = None
    if settings is not None and settings.cost_per_kwh is not None:
        estimated_monthly_cost = round(
            (total_watts / 1000) * _MONTHLY_HOURS * settings.cost_per_kwh,
            2,
        )
    options = [DashboardWorkspaceOption(name=_ALL_WORKSPACES)]
    options.extend(
        DashboardWorkspaceOption(id=workspace_id, name=name)
        for workspace_id, name in workspaces
    )
    return DashboardPowerWidget(
        workspace_options=options,
        selected_workspace_id=scope.selected_workspace_id,
        selected_workspace_name=selected_workspace_name,
        total_watts=total_watts,
        estimated_monthly_cost=estimated_monthly_cost,
        currency=settings.currency if settings is not None else None,
    )


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
    return extract_device_ids(cytoscape_json)


def _sum_device_watts(session: Session, scope: DeviceScope) -> int:
    rows = session.exec(
        _apply_device_scope(select(Device.power_watts), session, scope)
    ).all()
    return sum(watts or 0 for watts in rows)
