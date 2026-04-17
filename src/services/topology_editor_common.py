"""Shared helpers for topology editor services (HT-072)."""
import json as _json
import uuid
from datetime import datetime, timezone
from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.diagram import DiagramLayout


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clone_json(payload: dict[str, object]) -> dict[str, object]:
    return _json.loads(_json.dumps(payload))


def empty_canvas_json() -> dict[str, object]:
    return {
        "elements": {"nodes": [], "edges": []},
        "zoom": 1,
        "pan": {"x": 0, "y": 0},
        "collapsedNodes": [],
    }


def has_unsaved_draft_changes(
    draft_json: dict[str, object],
    current_json: dict[str, object] | None,
) -> bool:
    baseline = current_json if current_json is not None else empty_canvas_json()
    return clone_json(draft_json) != clone_json(baseline)


def resolve_snapshot_name(requested_name: str | None) -> str:
    if requested_name is not None:
        trimmed = requested_name.strip()
        if trimmed:
            return trimmed
    return utcnow().strftime("Version %Y-%m-%d %H:%M:%S UTC")


def resolve_current_diagram(
    topology_id: uuid.UUID,
    current_diagram_id: uuid.UUID | None,
    session: Session,
    *,
    get_diagram: Callable[[Session, uuid.UUID], DiagramLayout | None],
) -> DiagramLayout | None:
    if current_diagram_id is None:
        return None
    current = get_diagram(session, current_diagram_id)
    if current is None:
        return None
    if current.topology_id != topology_id:
        return None
    return current


def raise_conflict(exc: IntegrityError, session: Session, detail: str) -> None:
    session.rollback()
    raise HTTPException(status_code=409, detail=detail) from exc
