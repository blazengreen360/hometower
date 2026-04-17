"""Shared validation/error helpers for network service operations."""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.repositories import device_repository


def _is_unique_violation(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    sql_state = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
    if sql_state == "23505":
        return True

    message = str(original or exc).lower()
    return "unique" in message


def raise_network_integrity_error(
    exc: IntegrityError,
    session: Session,
    conflict_detail: str,
    fallback_detail: str,
) -> None:
    session.rollback()
    if _is_unique_violation(exc):
        raise HTTPException(status_code=409, detail=conflict_detail) from exc
    raise HTTPException(status_code=400, detail=fallback_detail) from exc


def reject_null_required_patch_fields(update_data: dict[str, object]) -> None:
    for field_name in ("name", "cidr", "color"):
        if field_name in update_data and update_data[field_name] is None:
            raise HTTPException(status_code=400, detail=f"{field_name} cannot be null")


def assert_device_exists(device_id: uuid.UUID, session: Session) -> None:
    if device_repository.get_by_id(session, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
