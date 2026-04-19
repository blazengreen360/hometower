"""Shared query helpers for workspace-scoped device repository reads."""
import uuid

from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session

from src.models.device import Device
from src.repositories.dashboard_device_scope_support import _current_diagram_device_ids


_SORT_EXPRESSIONS = {
    "name": lambda col: col(Device.name),
    "-name": lambda col: col(Device.name).desc(),
    "updated_at": lambda col: col(Device.updated_at),
    "-updated_at": lambda col: col(Device.updated_at).desc(),
    "created_at": lambda col: col(Device.created_at),
    "-created_at": lambda col: col(Device.created_at).desc(),
}


def get_workspace_device_ids(
    session: Session,
    workspace_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
) -> set[uuid.UUID] | None:
    if workspace_id is not None:
        return _current_diagram_device_ids(session, workspace_id, owner_id)
    if owner_id is not None and not device_owner_scope_available(session):
        return _current_diagram_device_ids(session, None, owner_id)
    return None


def device_owner_scope_available(session: Session) -> bool:
    bind = session.get_bind()
    if bind is None:
        return False
    columns = sa_inspect(bind).get_columns(Device.__tablename__)
    return any(str(column.get("name")) == "owner_id" for column in columns)


def apply_owner_scope(statement, session: Session, col, owner_id: uuid.UUID | None):
    if owner_id is not None and device_owner_scope_available(session):
        statement = statement.where(col(Device.owner_id) == owner_id)
    return statement


def apply_device_scope(statement, session: Session, col, device_ids, owner_id: uuid.UUID | None):
    statement = apply_owner_scope(statement, session, col, owner_id)
    if device_ids is not None:
        statement = statement.where(col(Device.id).in_(device_ids))
    return statement


def get_order_expression(sort: str | None, col):
    if sort in _SORT_EXPRESSIONS:
        return _SORT_EXPRESSIONS[sort](col)
    return col(Device.created_at)