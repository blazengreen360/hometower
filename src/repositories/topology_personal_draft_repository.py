"""Topology personal draft repository for per-user autosaved editor state."""
import uuid

from sqlmodel import Session, select

from src.models.topology_personal_draft import TopologyPersonalDraft


def create(session: Session, draft: TopologyPersonalDraft) -> TopologyPersonalDraft:
    """Persist a new personal draft and return the refreshed instance."""
    session.add(draft)
    session.flush()
    session.refresh(draft)
    return draft


def update(session: Session, draft: TopologyPersonalDraft) -> TopologyPersonalDraft:
    """Persist an existing personal draft and return the refreshed instance."""
    session.add(draft)
    session.flush()
    session.refresh(draft)
    return draft


def delete(session: Session, draft: TopologyPersonalDraft) -> None:
    """Delete a personal draft row."""
    session.delete(draft)
    session.flush()


def get_by_topology_and_user(
    session: Session,
    topology_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TopologyPersonalDraft | None:
    """Return the personal draft for a topology/user pair, if present."""
    statement = select(TopologyPersonalDraft).where(
        TopologyPersonalDraft.topology_id == topology_id,
        TopologyPersonalDraft.user_id == user_id,
    )
    return session.exec(statement).first()
