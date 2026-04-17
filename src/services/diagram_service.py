"""DiagramLayout service — orchestrates diagram repository operations."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.diagram import DiagramLayout, DiagramLayoutCreate, DiagramLayoutUpdate
from src.repositories import diagram_repository, topology_repository
from src.services.diagram_service_support import (
    _raise_diagram_conflict,
    _resolve_topology_id_for_create,
    _verify_diagram_ownership,
)
from src.utils.logger import logger


def create(data: DiagramLayoutCreate, owner_id: uuid.UUID, session: Session) -> DiagramLayout:
    """Persist a new diagram layout."""
    try:
        topology_id = _resolve_topology_id_for_create(owner_id, data.topology_id, session)
        layout = DiagramLayout(
            name=data.name,
            cytoscape_json=data.cytoscape_json,
            topology_id=topology_id,
        )
        result = diagram_repository.create(session, layout)
        topology = topology_repository.get_by_id(session, topology_id)
        if topology is not None:
            topology.current_diagram_id = result.id
            topology.updated_at = datetime.now(timezone.utc)
            topology_repository.update(session, topology)
        session.commit()
    except IntegrityError as exc:
        _raise_diagram_conflict(exc, session)
    logger.info("DiagramLayout created: id={} name={}", result.id, result.name)
    return result


def get_by_id(
    layout_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> DiagramLayout:
    """Return the layout or raise HTTP 404."""
    if owner_id is None:
        layout = diagram_repository.get_by_id(session, layout_id)
    else:
        layout = diagram_repository.get_by_id_for_owner(session, layout_id, owner_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    return layout


def get_all(
    session: Session,
    page: int = 1,
    limit: int = 50,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts and total count."""
    if owner_id is not None:
        return diagram_repository.get_all_for_owner(session, owner_id, page=page, limit=limit)
    return diagram_repository.get_all(session, page=page, limit=limit)


def get_by_topology(
    topology_id: uuid.UUID,
    session: Session,
    page: int = 1,
    limit: int = 50,
    owner_id: uuid.UUID | None = None,
) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts for a topology."""
    if owner_id is not None:
        _verify_diagram_ownership(owner_id, session, topology_id=topology_id)
        return diagram_repository.get_by_topology_for_owner(
            session,
            topology_id,
            owner_id,
            page=page,
            limit=limit,
        )
    return diagram_repository.get_by_topology(session, topology_id, page=page, limit=limit)


def update(
    layout_id: uuid.UUID,
    data: DiagramLayoutCreate,
    owner_id: uuid.UUID,
    session: Session,
) -> DiagramLayout:
    """Update an existing diagram layout by ID."""
    layout = diagram_repository.get_by_id_for_update(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    _verify_diagram_ownership(
        owner_id,
        session,
        topology_id=layout.topology_id,
        not_found_detail="Diagram layout not found",
    )

    if data.version is None:
        raise HTTPException(status_code=422, detail="version is required")
    if data.version != layout.version:
        raise HTTPException(
            status_code=409,
            detail="Conflict: diagram was modified by another request",
        )

    layout.name = data.name
    layout.cytoscape_json = data.cytoscape_json
    layout.version += 1
    layout.updated_at = datetime.now(timezone.utc)
    try:
        result = diagram_repository.update(session, layout)
        session.commit()
    except IntegrityError as exc:
        _raise_diagram_conflict(exc, session)
    logger.info("DiagramLayout updated: id={} name={}", result.id, result.name)
    return result


def delete(layout_id: uuid.UUID, owner_id: uuid.UUID, session: Session) -> None:
    """Delete a layout; raise HTTP 404 if not found."""
    layout = diagram_repository.get_by_id_for_update(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    _verify_diagram_ownership(
        owner_id,
        session,
        topology_id=layout.topology_id,
        not_found_detail="Diagram layout not found",
    )
    try:
        topology = None
        if layout.topology_id is not None:
            topology = topology_repository.get_by_id(session, layout.topology_id)
        diagram_repository.delete(session, layout)
        if topology is not None and topology.current_diagram_id == layout_id:
            topology.current_diagram_id = None
            topology.updated_at = datetime.now(timezone.utc)
            topology_repository.update(session, topology)
        session.commit()
    except IntegrityError as exc:
        _raise_diagram_conflict(exc, session)
    logger.info("DiagramLayout deleted: id={}", layout_id)


def update_timestamp(layout_id: uuid.UUID, session: Session) -> DiagramLayout:
    """Touch the updated_at timestamp on an existing layout."""
    layout = diagram_repository.get_by_id_for_update(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    layout.updated_at = datetime.now(timezone.utc)
    try:
        result = diagram_repository.update(session, layout)
        session.commit()
    except IntegrityError as exc:
        _raise_diagram_conflict(exc, session)
    logger.info("DiagramLayout updated_at touched: id={}", layout_id)
    return result


def partial_update(
    layout_id: uuid.UUID,
    data: DiagramLayoutUpdate,
    owner_id: uuid.UUID,
    session: Session,
) -> DiagramLayout:
    """Partially update a diagram layout — only update fields that are not None."""
    layout = diagram_repository.get_by_id_for_update(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    _verify_diagram_ownership(
        owner_id,
        session,
        topology_id=layout.topology_id,
        not_found_detail="Diagram layout not found",
    )
    if data.version != layout.version:
        raise HTTPException(
            status_code=409,
            detail="Conflict: diagram was modified by another request",
        )
    if data.name is not None:
        layout.name = data.name
    if data.cytoscape_json is not None:
        layout.cytoscape_json = data.cytoscape_json
    layout.version += 1
    layout.updated_at = datetime.now(timezone.utc)
    try:
        result = diagram_repository.update(session, layout)
        session.commit()
    except IntegrityError as exc:
        _raise_diagram_conflict(exc, session)
    updated_fields = [k for k, v in data.model_dump().items() if k != "version" and v is not None]
    logger.info("DiagramLayout partial update: id={} fields={}", result.id, updated_fields)
    return result
