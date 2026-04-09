"""DiagramLayout service — orchestrates diagram repository operations."""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session

from src.models.diagram import DiagramLayout, DiagramLayoutCreate
from src.repositories import diagram_repository
from src.utils.logger import logger


def create(data: DiagramLayoutCreate, session: Session) -> DiagramLayout:
    """Persist a new diagram layout."""
    layout = DiagramLayout(
        name=data.name,
        cytoscape_json=data.cytoscape_json,
    )
    result = diagram_repository.create(session, layout)
    logger.info("DiagramLayout created: id={} name={}", result.id, result.name)
    return result


def get_by_id(layout_id: uuid.UUID, session: Session) -> DiagramLayout:
    """Return the layout or raise HTTP 404."""
    layout = diagram_repository.get_by_id(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    return layout


def get_all(session: Session, page: int = 1, limit: int = 50) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts and total count."""
    return diagram_repository.get_all(session, page=page, limit=limit)


def delete(layout_id: uuid.UUID, session: Session) -> None:
    """Delete a layout; raise HTTP 404 if not found."""
    layout = diagram_repository.get_by_id(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    diagram_repository.delete(session, layout)
    logger.info("DiagramLayout deleted: id={}", layout_id)


def update_timestamp(layout_id: uuid.UUID, session: Session) -> DiagramLayout:
    """Touch the updated_at timestamp on an existing layout."""
    layout = diagram_repository.get_by_id(session, layout_id)
    if layout is None:
        raise HTTPException(status_code=404, detail="Diagram layout not found")
    layout.updated_at = datetime.now(timezone.utc)
    result = diagram_repository.create(session, layout)
    logger.info("DiagramLayout updated_at touched: id={}", layout_id)
    return result
