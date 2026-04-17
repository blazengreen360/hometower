"""Workspace service — orchestrates workspace repository operations."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain.workspaces import validate_workspace_name
from src.models.workspace import (
    PaginatedWorkspaceSummary,
    Workspace,
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceSummary,
    WorkspaceUpdate,
)
from src.repositories import workspace_repository
from src.utils.logger import logger


def _raise_conflict(exc: IntegrityError, session: Session) -> None:
    session.rollback()
    raise HTTPException(status_code=409, detail="Workspace name conflict") from exc


def create(
    owner_id: uuid.UUID, data: WorkspaceCreate, session: Session
) -> Workspace:
    """Create a new workspace for the given owner."""
    name = validate_workspace_name(data.name)
    existing = workspace_repository.get_by_owner_and_name(session, owner_id, name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="A workspace with this name already exists",
        )
    workspace = Workspace(name=name, owner_id=owner_id)
    try:
        result = workspace_repository.create(session, workspace)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)
    logger.info("Workspace created: id={} name={}", result.id, result.name)
    return result


def get_or_create_default(
    owner_id: uuid.UUID, session: Session
) -> Workspace:
    """Return the 'Default Workspace' for an owner, creating it if needed."""
    existing = workspace_repository.get_by_owner_and_name(
        session, owner_id, "Default Workspace"
    )
    if existing is not None:
        return existing

    workspace = Workspace(name="Default Workspace", owner_id=owner_id)
    try:
        workspace = workspace_repository.create(session, workspace)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)

    # Also create a Default Topology inside
    from src.models.topology import Topology
    from src.repositories import topology_repository

    topo = Topology(name="Default Topology", workspace_id=workspace.id)
    try:
        topology_repository.create(session, topo)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        logger.warning("Default topology creation conflict: {}", exc)

    logger.info("Default workspace created for owner_id={}", owner_id)
    return workspace


def get_by_id(
    workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session
) -> Workspace:
    """Return workspace if owned by caller, else 404."""
    workspace = workspace_repository.get_by_id(session, workspace_id)
    if workspace is None or workspace.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def get_all(
    owner_id: uuid.UUID, session: Session, page: int = 1, limit: int = 50,
    search: str | None = None,
) -> tuple[list[Workspace], int]:
    """Return paginated workspaces for an owner."""
    return workspace_repository.get_by_owner(session, owner_id, page, limit, search=search)


def rename(
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: WorkspaceUpdate,
    session: Session,
) -> Workspace:
    """Rename a workspace."""
    workspace = get_by_id(workspace_id, owner_id, session)
    if data.name is not None:
        name = validate_workspace_name(data.name)
        dup = workspace_repository.get_by_owner_and_name(session, owner_id, name)
        if dup is not None and dup.id != workspace_id:
            raise HTTPException(
                status_code=409,
                detail="A workspace with this name already exists",
            )
        workspace.name = name
    workspace.updated_at = datetime.now(timezone.utc)
    try:
        result = workspace_repository.update(session, workspace)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)
    logger.info("Workspace renamed: id={} name={}", result.id, result.name)
    return result


def delete(
    workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session
) -> None:
    """Delete a workspace (CASCADE handles topologies and views)."""
    workspace = get_by_id(workspace_id, owner_id, session)
    try:
        workspace_repository.delete(session, workspace)
        session.commit()
    except IntegrityError as exc:
        _raise_conflict(exc, session)
    logger.info("Workspace deleted: id={}", workspace_id)


def _to_summary(ws: Workspace, topology_count: int) -> WorkspaceSummary:
    return WorkspaceSummary(
        id=ws.id,
        name=ws.name,
        topology_count=topology_count,
        last_modified=ws.updated_at,
    )


def _to_response(ws: Workspace, topology_count: int) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        owner_id=ws.owner_id,
        topology_count=topology_count,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


def list_summaries(
    owner_id: uuid.UUID,
    session: Session,
    page: int = 1,
    limit: int = 50,
    search: str | None = None,
) -> PaginatedWorkspaceSummary:
    """Return paginated workspace summaries with topology counts."""
    items, total = workspace_repository.get_by_owner(
        session, owner_id, page, limit, search=search,
    )
    if total == 0 and not search:
        get_or_create_default(owner_id, session)
        items, total = workspace_repository.get_by_owner(
            session, owner_id, page, limit,
        )
    counts = workspace_repository.count_topologies_batch(
        session, [ws.id for ws in items],
    )
    summaries = [_to_summary(ws, counts.get(ws.id, 0)) for ws in items]
    return PaginatedWorkspaceSummary(
        items=summaries, total=total, page=page, limit=limit,
    )


def get_response(
    workspace_id: uuid.UUID, owner_id: uuid.UUID, session: Session
) -> WorkspaceResponse:
    """Return a single workspace response with topology count."""
    ws = get_by_id(workspace_id, owner_id, session)
    count = workspace_repository.count_topologies(session, ws.id)
    return _to_response(ws, count)


def create_response(
    owner_id: uuid.UUID, data: WorkspaceCreate, session: Session
) -> WorkspaceResponse:
    """Create a workspace and return the response with topology count."""
    ws = create(owner_id, data, session)
    count = workspace_repository.count_topologies(session, ws.id)
    return _to_response(ws, count)


def rename_response(
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    data: WorkspaceUpdate,
    session: Session,
) -> WorkspaceResponse:
    """Rename a workspace and return the response with topology count."""
    ws = rename(workspace_id, owner_id, data, session)
    count = workspace_repository.count_topologies(session, ws.id)
    return _to_response(ws, count)
