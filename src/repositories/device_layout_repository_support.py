"""Repository helpers for device layout lookups used by service-layer scans."""
import uuid

from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, col, select

from src.models.device import Device
from src.models.topology import Topology


def get_topology_workspace_ids(
    session: Session,
    topology_ids: set[uuid.UUID],
) -> dict[uuid.UUID, uuid.UUID]:
    if not topology_ids:
        return {}
    rows = session.exec(
        select(Topology.id, Topology.workspace_id).where(col(Topology.id).in_(topology_ids))
    ).all()
    return {topology_id: workspace_id for topology_id, workspace_id in rows}


def get_topology_names(
    session: Session,
    topology_ids: set[uuid.UUID],
) -> dict[uuid.UUID, str]:
    if not topology_ids:
        return {}
    rows = session.exec(
        select(Topology.id, Topology.name).where(col(Topology.id).in_(topology_ids))
    ).all()
    return {topology_id: name for topology_id, name in rows}


def get_visible_device_ids(
    session: Session,
    device_ids: set[uuid.UUID],
    owner_id: uuid.UUID | None,
) -> set[uuid.UUID]:
    if not device_ids:
        return set()
    if owner_id is not None:
        bind = session.get_bind()
        if bind is None:
            return set()
        columns = sa_inspect(bind).get_columns(Device.__tablename__)
        if not any(str(column.get("name")) == "owner_id" for column in columns):
            return set()
    statement = select(Device.id).where(col(Device.id).in_(device_ids))
    if owner_id is not None:
        statement = statement.where(col(Device.owner_id) == owner_id)
    return set(session.exec(statement).all())