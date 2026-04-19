"""Device scoping helpers for HT-082 dashboard summary reads."""
import uuid
from typing import Mapping

from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, col, select

from src.domain.cytoscape import extract_device_ids
from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.workspace import Workspace
from src.repositories.device_layout_repository_support import get_visible_device_ids


class DeviceScope:
    def __init__(
        self,
        selected_workspace_id: uuid.UUID | None,
        owner_id: uuid.UUID | None,
        device_ids: set[uuid.UUID] | None = None,
    ) -> None:
        self.selected_workspace_id = selected_workspace_id
        self.owner_id = owner_id
        self.device_ids = device_ids


def _owned_devices(statement, owner_id: uuid.UUID | None):
    if owner_id is None:
        return statement
    return statement.where(col(Device.owner_id) == owner_id)


def _device_owner_column_available(session: Session) -> bool:
    bind = session.get_bind()
    if bind is None:
        return False
    columns = sa_inspect(bind).get_columns(Device.__tablename__)
    return any(str(column.get("name")) == "owner_id" for column in columns)


def _device_owner_scope_available(session: Session) -> bool:
    return _device_owner_column_available(session)


def _extract_device_ids(cytoscape_json: Mapping[str, object]) -> set[uuid.UUID]:
    return extract_device_ids(cytoscape_json)


def _current_diagram_device_ids(
    session: Session,
    selected_workspace_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> set[uuid.UUID]:
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
        if isinstance(cytoscape_json, dict):
            device_ids.update(_extract_device_ids(cytoscape_json))
    if owner_id is not None and _device_owner_column_available(session):
        return get_visible_device_ids(session, device_ids, owner_id)
    return device_ids


def build_device_scope(
    session: Session,
    selected_workspace_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> DeviceScope:
    owner_scope_available = _device_owner_scope_available(session)
    device_ids = None
    if selected_workspace_id is not None or (
        owner_id is not None and not owner_scope_available
    ):
        device_ids = _current_diagram_device_ids(
            session,
            selected_workspace_id,
            owner_id,
        )
    return DeviceScope(selected_workspace_id, owner_id, device_ids)


def _apply_device_scope(statement, session: Session, scope: DeviceScope):
    if _device_owner_scope_available(session):
        statement = _owned_devices(statement, scope.owner_id)
    if scope.device_ids is not None:
        statement = statement.where(col(Device.id).in_(scope.device_ids))
    return statement