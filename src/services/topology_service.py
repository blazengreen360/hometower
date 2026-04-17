"""Topology service — orchestrates topology repository operations."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain.workspaces import validate_topology_name
from src.models.topology import (
    PaginatedTopologySummary,
    Topology,
    TopologyCreate,
    TopologyResponse,
    TopologySummary,
    TopologyUpdate,
)
from src.repositories import topology_repository, workspace_repository
from src.utils.logger import logger


def _raise_conflict(exc: IntegrityError, session: Session) -> None:
    session.rollback()
    raise HTTPException(status_code=409, detail="Topology name conflict") from exc


def _verify_workspace_ownership(
    workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session
) -> None:
    """Ensure workspace exists and is owned by the caller."""
    ws = workspace_repository.get_by_id(session, workspace_id)
    if ws is None or ws.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Workspace not found")


def create(
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: TopologyCreate,
    session: Session,
) -> Topology:
    """Create a new topology within a workspace."""
    _verify_workspace_ownership(workspace_id, owner_id, session)
    name = validate_topology_name(data.name)
    dup = topology_repository.get_by_workspace_and_name(session, workspace_id, name)
    if dup is not None:
        raise HTTPException(
            status_code=409,
            detail="A topology with this name already exists in the workspace",
        )
    topology = Topology(
        name=name, workspace_id=workspace_id, tags=data.tags
    )
    try:
        result = topology_repository.create(session, topology)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)
    logger.info("Topology created: id={} name={}", result.id, result.name)
    return result


def get_by_id(
    topology_id: uuid.UUID, owner_id: uuid.UUID, session: Session
) -> Topology:
    """Return topology if owned by caller (via workspace), else 404."""
    topology = topology_repository.get_by_id(session, topology_id)
    if topology is None:
        raise HTTPException(status_code=404, detail="Topology not found")
    ws = workspace_repository.get_by_id(session, topology.workspace_id)
    if ws is None or ws.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Topology not found")
    return topology


def get_by_workspace(
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    session: Session,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[Topology], int]:
    """Return paginated topologies for a workspace."""
    _verify_workspace_ownership(workspace_id, owner_id, session)
    return topology_repository.get_by_workspace(session, workspace_id, page, limit)


def rename(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: TopologyUpdate,
    session: Session,
) -> Topology:
    """Rename a topology and/or update tags."""
    topology = get_by_id(topology_id, owner_id, session)
    if data.name is not None:
        name = validate_topology_name(data.name)
        dup = topology_repository.get_by_workspace_and_name(
            session, topology.workspace_id, name
        )
        if dup is not None and dup.id != topology_id:
            raise HTTPException(
                status_code=409,
                detail="A topology with this name already exists in the workspace",
            )
        topology.name = name
    if data.tags is not None:
        topology.tags = data.tags
    topology.updated_at = datetime.now(timezone.utc)
    try:
        result = topology_repository.update(session, topology)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)
    logger.info("Topology updated: id={} name={}", result.id, result.name)
    return result


def update_tags(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    tags: list[str],
    session: Session,
) -> Topology:
    """Update tags on a topology."""
    topology = get_by_id(topology_id, owner_id, session)
    topology.tags = tags
    topology.updated_at = datetime.now(timezone.utc)
    try:
        result = topology_repository.update(session, topology)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)
    logger.info("Topology tags updated: id={}", result.id)
    return result


def delete(
    topology_id: uuid.UUID, owner_id: uuid.UUID, session: Session
) -> None:
    """Delete a topology (CASCADE handles views)."""
    topology = get_by_id(topology_id, owner_id, session)
    try:
        topology_repository.delete(session, topology)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)
    logger.info("Topology deleted: id={}", topology_id)


def _to_summary(t: Topology) -> TopologySummary:
    return TopologySummary(
        id=t.id,
        name=t.name,
        tags=t.tags,
        last_modified=t.updated_at,
    )


def _to_response(t: Topology) -> TopologyResponse:
    return TopologyResponse(
        id=t.id,
        name=t.name,
        tags=t.tags,
        workspace_id=t.workspace_id,
        current_diagram_id=t.current_diagram_id,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def list_summaries(
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    session: Session,
    page: int = 1,
    limit: int = 50,
) -> PaginatedTopologySummary:
    """Return paginated topology summaries."""
    _verify_workspace_ownership(workspace_id, owner_id, session)
    items, total = topology_repository.get_by_workspace(
        session, workspace_id, page, limit,
    )
    summaries = [_to_summary(t) for t in items]
    return PaginatedTopologySummary(
        items=summaries, total=total, page=page, limit=limit,
    )


def get_response(
    topology_id: uuid.UUID, owner_id: uuid.UUID, session: Session
) -> TopologyResponse:
    """Return a single topology response."""
    t = get_by_id(topology_id, owner_id, session)
    return _to_response(t)


def create_response(
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: TopologyCreate,
    session: Session,
) -> TopologyResponse:
    """Create a topology and return the response."""
    t = create(workspace_id, owner_id, data, session)
    return _to_response(t)


def rename_response(
    topology_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: TopologyUpdate,
    session: Session,
) -> TopologyResponse:
    """Rename a topology and return the response."""
    t = rename(topology_id, owner_id, data, session)
    return _to_response(t)
