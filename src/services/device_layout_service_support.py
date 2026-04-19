"""Service helpers for device placement and placed-id scans."""
import uuid

from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, col, select

from src.domain.cytoscape import extract_device_ids
from src.domain import devices as device_domain
from src.models.device import Device, DevicePlacement
from src.models.diagram import DiagramLayout
from src.models.topology import Topology
from src.models.workspace import Workspace
from src.repositories import device_layout_repository_support


def _device_owner_scope_available(session: Session) -> bool:
    bind = session.get_bind()
    if bind is None:
        return False
    columns = sa_inspect(bind).get_columns(Device.__tablename__)
    return any(str(column.get("name")) == "owner_id" for column in columns)


def _current_diagram_device_ids(
    session: Session,
    owner_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
) -> set[uuid.UUID]:
    statement = (
        select(DiagramLayout.cytoscape_json)
        .join(Topology, col(DiagramLayout.id) == col(Topology.current_diagram_id))
        .join(Workspace, col(Topology.workspace_id) == col(Workspace.id))
        .where(col(Workspace.owner_id) == owner_id)
    )
    if workspace_id is not None:
        statement = statement.where(col(Workspace.id) == workspace_id)
    device_ids: set[uuid.UUID] = set()
    for cytoscape_json in session.exec(statement).all():
        if isinstance(cytoscape_json, dict):
            device_ids.update(extract_device_ids(cytoscape_json))
    return device_ids


def _current_layouts(
    session: Session,
    owner_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
) -> list[DiagramLayout]:
    statement = (
        select(DiagramLayout)
        .join(Topology, col(DiagramLayout.id) == col(Topology.current_diagram_id))
        .order_by(col(DiagramLayout.created_at))
    )
    if owner_id is not None:
        statement = statement.join(
            Workspace,
            col(Topology.workspace_id) == col(Workspace.id),
        ).where(col(Workspace.owner_id) == owner_id)
    if workspace_id is not None:
        statement = statement.where(col(Topology.workspace_id) == workspace_id)
    return list(session.exec(statement).all())


def get_device_placements(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> list[DevicePlacement]:
    device_id_str = str(device_id)
    layouts = _current_layouts(session, owner_id=owner_id)
    topology_names = device_layout_repository_support.get_topology_names(
        session,
        {
            layout.topology_id
            for layout in layouts
            if layout.topology_id is not None
        },
    )
    placements: list[DevicePlacement] = []
    for layout in layouts:
        cj = layout.cytoscape_json
        if not isinstance(cj, dict):
            continue
        if device_domain.device_in_cytoscape_json(cj, device_id_str):
            topology_name = None
            if layout.topology_id is not None:
                topology_name = topology_names.get(layout.topology_id)
            placements.append(
                DevicePlacement(
                    view_id=layout.id,
                    view_name=layout.name,
                    topology_name=topology_name,
                )
            )
    return placements


def get_placed_device_ids(
    session: Session,
    owner_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
) -> set[uuid.UUID]:
    if owner_id is not None and not _device_owner_scope_available(session):
        return _current_diagram_device_ids(session, owner_id, workspace_id)

    layouts = _current_layouts(
        session,
        owner_id=owner_id,
        workspace_id=workspace_id,
    )
    placed: set[uuid.UUID] = set()
    for layout in layouts:
        placed.update(extract_device_ids(layout.cytoscape_json))
    return device_layout_repository_support.get_visible_device_ids(
        session,
        placed,
        owner_id,
    )