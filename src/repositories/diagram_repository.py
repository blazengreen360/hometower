"""DiagramLayout repository — sole layer that holds a SQLModel Session for diagram operations."""
import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from src.models.diagram import DiagramLayout


def create(session: Session, layout: DiagramLayout) -> DiagramLayout:
    """Persist a new diagram layout and return the refreshed instance."""
    session.add(layout)
    session.commit()
    session.refresh(layout)
    return layout


def get_by_id(session: Session, layout_id: uuid.UUID) -> DiagramLayout | None:
    """Return the layout with the given primary key, or None."""
    return session.get(DiagramLayout, layout_id)


def get_all(session: Session, page: int = 1, limit: int = 50) -> tuple[list[DiagramLayout], int]:
    """Return paginated diagram layouts and the total count."""
    total = int(session.exec(select(func.count()).select_from(DiagramLayout)).one())
    offset = (page - 1) * limit
    statement = (
        select(DiagramLayout)
        .order_by(col(DiagramLayout.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, total


def delete(session: Session, layout: DiagramLayout) -> None:
    """Hard-delete a diagram layout record."""
    session.delete(layout)
    session.commit()
