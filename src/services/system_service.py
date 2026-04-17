"""System-level queries: inventory counts, DB diagnostics, health probe."""
from typing import Optional

from sqlalchemy import func, text
from sqlmodel import Session, select

from src.models.connection import Connection
from src.models.custom_field import CustomField
from src.models.device import Device
from src.models.diagram import DiagramLayout
from src.models.location import Location
from src.models.tag import Tag
from src.models.user import User
from src.utils.logger import logger


def get_entity_counts(session: Session) -> dict[str, int]:
    """Return counts for devices, connections, locations, tags, custom_fields, diagrams."""
    return {
        "devices": int(session.exec(select(func.count()).select_from(Device)).one()),
        "connections": int(session.exec(select(func.count()).select_from(Connection)).one()),
        "locations": int(session.exec(select(func.count()).select_from(Location)).one()),
        "tags": int(session.exec(select(func.count()).select_from(Tag)).one()),
        "custom_fields": int(session.exec(select(func.count()).select_from(CustomField)).one()),
        "diagrams": int(session.exec(select(func.count()).select_from(DiagramLayout)).one()),
    }


def get_user_count(session: Session) -> int:
    """Return total user count (admin-only stat)."""
    return int(session.exec(select(func.count()).select_from(User)).one())


def get_db_diagnostics(session: Session) -> tuple[Optional[str], Optional[int]]:
    """Return (db_version, db_size_bytes). None values on non-PG or failure."""
    db_version: Optional[str] = None
    db_size_bytes: Optional[int] = None
    try:
        row = session.execute(text("SELECT version()")).fetchone()
        if row:
            db_version = str(row[0])
        size_row = session.execute(
            text("SELECT pg_database_size(current_database())")
        ).fetchone()
        if size_row:
            db_size_bytes = int(size_row[0])
    except Exception as exc:
        logger.debug("DB diagnostics unavailable (non-PG environment): {}", str(exc))
    return db_version, db_size_bytes


def check_db_connectivity(session: Session) -> bool:
    """Execute ``SELECT 1``; return True if reachable, False otherwise."""
    try:
        session.exec(text("SELECT 1"))  # type: ignore[call-overload]
        return True
    except Exception as exc:
        logger.warning("DB connectivity check failed: {error}", error=str(exc))
        return False
