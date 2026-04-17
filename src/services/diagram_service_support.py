"""Internal helpers for diagram service ownership and topology resolution."""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.topology import Topology
from src.models.workspace import Workspace
from src.repositories import diagram_repository, topology_repository, workspace_repository


def _raise_diagram_conflict(exc: IntegrityError, session: Session) -> None:
    """Rollback failed diagram write and map DB integrity failures to HTTP 409."""
    session.rollback()
    raise HTTPException(status_code=409, detail="Diagram layout conflict") from exc


def _resolve_default_topology_id(owner_id: uuid.UUID, session: Session) -> uuid.UUID:
    """Resolve an owner's default topology, creating default workspace/topology if missing."""
    workspace = workspace_repository.get_by_owner_and_name(session, owner_id, "Default Workspace")
    if workspace is None:
        workspace = workspace_repository.create(
            session,
            Workspace(name="Default Workspace", owner_id=owner_id),
        )

    topology = topology_repository.get_by_workspace_and_name(
        session,
        workspace.id,
        "Default Topology",
    )
    if topology is None:
        topology = topology_repository.create(
            session,
            Topology(name="Default Topology", workspace_id=workspace.id),
        )

    return topology.id


def _resolve_topology_id_for_create(
    owner_id: uuid.UUID,
    requested_topology_id: uuid.UUID | None,
    session: Session,
) -> uuid.UUID:
    """Return an owner-bound topology id for creates, defaulting to owner's default topology."""
    if requested_topology_id is not None:
        _verify_diagram_ownership(owner_id, session, topology_id=requested_topology_id)
        return requested_topology_id
    return _resolve_default_topology_id(owner_id, session)


def _verify_diagram_ownership(
    owner_id: uuid.UUID,
    session: Session,
    *,
    layout_id: uuid.UUID | None = None,
    topology_id: uuid.UUID | None = None,
    not_found_detail: str = "Topology not found",
) -> None:
    """Ensure the diagram or topology belongs to the caller's workspace."""
    resolved_topology_id = topology_id
    if resolved_topology_id is None and layout_id is not None:
        layout = diagram_repository.get_by_id(session, layout_id)
        if layout is None:
            raise HTTPException(status_code=404, detail="Diagram layout not found")
        resolved_topology_id = layout.topology_id

    if resolved_topology_id is None:
        raise HTTPException(status_code=404, detail=not_found_detail)

    topology = topology_repository.get_by_id(session, resolved_topology_id)
    if topology is None:
        raise HTTPException(status_code=404, detail=not_found_detail)

    workspace = workspace_repository.get_by_id(session, topology.workspace_id)
    if workspace is None or workspace.owner_id != owner_id:
        raise HTTPException(status_code=404, detail=not_found_detail)