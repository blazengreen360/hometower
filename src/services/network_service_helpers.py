"""Shared validation/error helpers for network service operations."""

import uuid
from typing import cast

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import networks as network_domain
from src.models.device_network import DeviceNetwork
from src.repositories import device_repository
from src.repositories import network_repository


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


def validate_network_name_update(
    network_id: uuid.UUID,
    name: str | None,
    session: Session,
) -> None:
    if name is None:
        return

    normalized = network_domain.normalize_network_name(name)
    existing = network_repository.get_by_name_normalized(session, normalized)
    if existing is not None and existing.id != network_id:
        raise HTTPException(status_code=409, detail="Network name already exists")


def validate_network_vlan_update(update_data: dict[str, object]) -> None:
    if "vlan_id" not in update_data:
        return

    try:
        update_data["vlan_id"] = network_domain.validate_vlan_id(
            cast(int | None, update_data["vlan_id"])
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def validate_network_address_patch(
    update_data: dict[str, object],
    current_cidr: str,
    current_gateway: str | None,
) -> str:
    effective_cidr = current_cidr
    try:
        if "cidr" in update_data and update_data["cidr"] is not None:
            effective_cidr = network_domain.validate_cidr(cast(str, update_data["cidr"]))
            update_data["cidr"] = effective_cidr

        if "gateway" in update_data:
            update_data["gateway"] = network_domain.validate_gateway(
                cast(str | None, update_data["gateway"]),
                effective_cidr,
            )
        else:
            network_domain.validate_gateway(current_gateway, effective_cidr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return effective_cidr


def validate_memberships_for_cidr_change(
    memberships: list[DeviceNetwork],
    cidr: str,
) -> None:
    for membership in memberships:
        try:
            network_domain.validate_ip_in_subnet(membership.ip_address, cidr)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


def assert_device_exists(
    device_id: uuid.UUID,
    session: Session,
    owner_id: uuid.UUID | None = None,
) -> None:
    if device_repository.get_by_id(session, device_id, owner_id=owner_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
