"""Restore-token and restore-application helpers for canvas undo operations."""

import hashlib
import json
import uuid

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import devices as device_domain
from src.models.canvas_undo import (
    DiagramPlacementSnapshot,
    DiagramVersionRef,
    PublishedDeviceDeleteSnapshot,
)
from src.models.connection import Connection
from src.models.device import Device
from src.repositories import connection_repository, device_repository, diagram_repository, topology_history_repository
from src.services.canvas_undo_service_support import _restore_node_without_owner
from src.services.canvas_undo_service_support import _utcnow
from src.utils.settings import settings

_RESTORE_TOKEN_KIND = "published_device_restore"


def _snapshot_payload_hash(snapshot: PublishedDeviceDeleteSnapshot) -> str:
    payload = snapshot.model_dump(mode="json", exclude={"restore_token"})
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _build_restore_token(
    snapshot: PublishedDeviceDeleteSnapshot,
    actor_id: uuid.UUID | None,
    device_owner_id: uuid.UUID | None,
) -> str:
    issued_at = int(_utcnow().timestamp())
    claims: dict[str, str | int] = {
        "kind": _RESTORE_TOKEN_KIND,
        "device_id": str(snapshot.device.id),
        "snapshot_sha256": _snapshot_payload_hash(snapshot),
        "iat": issued_at,
        "exp": issued_at + (settings.jwt_expire_hours * 3600),
    }
    if actor_id is not None:
        claims["sub"] = str(actor_id)
    if device_owner_id is not None:
        claims["owner_id"] = str(device_owner_id)
    return jwt.encode(claims, settings.secret_key, algorithm="HS256")


def _parse_optional_uuid_claim(raw_value: object) -> uuid.UUID | None:
    if raw_value in (None, ""):
        return None
    try:
        return uuid.UUID(str(raw_value))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid restore snapshot") from exc


def _validate_restore_token(
    snapshot: PublishedDeviceDeleteSnapshot,
    owner_id: uuid.UUID | None,
) -> uuid.UUID | None:
    raw_token = snapshot.restore_token
    if raw_token is None or not raw_token.strip():
        raise HTTPException(status_code=400, detail="Invalid restore snapshot")

    try:
        claims = jwt.decode(raw_token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=400, detail="Invalid restore snapshot") from exc

    if claims.get("kind") != _RESTORE_TOKEN_KIND:
        raise HTTPException(status_code=400, detail="Invalid restore snapshot")
    if claims.get("device_id") != str(snapshot.device.id):
        raise HTTPException(status_code=400, detail="Invalid restore snapshot")
    if claims.get("snapshot_sha256") != _snapshot_payload_hash(snapshot):
        raise HTTPException(status_code=400, detail="Invalid restore snapshot")

    token_actor_id = _parse_optional_uuid_claim(claims.get("sub"))
    if owner_id is not None and token_actor_id != owner_id:
        raise HTTPException(status_code=404, detail="Device not found")

    return _parse_optional_uuid_claim(claims.get("owner_id"))


def _assert_canvas_restore_allowed(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
    owner_id: uuid.UUID | None,
) -> uuid.UUID | None:
    snapshot_owner_id = _validate_restore_token(snapshot, owner_id)

    if (
        device_repository.get_by_id(
            session,
            snapshot.device.id,
            owner_id=owner_id,
            enforce_owner_scope=False,
        )
        is not None
    ):
        raise HTTPException(status_code=409, detail="Device ID already exists")

    return snapshot_owner_id


def _build_restored_device(
    snapshot: PublishedDeviceDeleteSnapshot,
    snapshot_owner_id: uuid.UUID | None,
) -> Device:
    return Device(
        id=snapshot.device.id,
        name=snapshot.device.name,
        type=snapshot.device.type,
        status=snapshot.device.status,
        ip=snapshot.device.ip,
        mac=snapshot.device.mac,
        os=snapshot.device.os,
        notes=snapshot.device.notes,
        power_watts=snapshot.device.power_watts,
        location_id=snapshot.device.location_id,
        parent_id=snapshot.device.parent_id,
        owner_id=snapshot_owner_id,
        version=snapshot.device.version,
    )


def _restore_snapshot_connections(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
) -> None:
    for connection_snapshot in snapshot.connections:
        restored_connection = Connection(
            id=connection_snapshot.id,
            source_id=connection_snapshot.source_id,
            target_id=connection_snapshot.target_id,
            type=connection_snapshot.type,
            label=connection_snapshot.label,
        )
        connection_repository.create(session, restored_connection)


def _restore_snapshot_placements(
    snapshot: PublishedDeviceDeleteSnapshot,
    session: Session,
    owner_id: uuid.UUID | None,
) -> list[DiagramVersionRef]:
    immutable_diagram_ids = topology_history_repository.get_immutable_diagram_ids(
        session,
        {placement.diagram_id for placement in snapshot.placements},
    )
    modified_diagrams: list[DiagramVersionRef] = []
    for placement in snapshot.placements:
        if placement.diagram_id in immutable_diagram_ids:
            continue
        modified_diagrams.append(
            _restore_snapshot_placement(placement, session, owner_id)
        )
    return modified_diagrams


def _restore_snapshot_placement(
    placement: DiagramPlacementSnapshot,
    session: Session,
    owner_id: uuid.UUID | None,
) -> DiagramVersionRef:
    if owner_id is not None:
        owner_layout = diagram_repository.get_by_id_for_owner(
            session,
            placement.diagram_id,
            owner_id,
        )
        if owner_layout is None:
            if diagram_repository.get_by_id(session, placement.diagram_id) is None:
                session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Cannot restore device placement: "
                        f"diagram {placement.diagram_id} no longer exists"
                    ),
                )
            session.rollback()
            raise HTTPException(status_code=404, detail="Diagram not found")

    layout = diagram_repository.get_by_id_for_update(session, placement.diagram_id)

    if layout is None:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot restore device placement: "
                f"diagram {placement.diagram_id} no longer exists"
            ),
        )

    cytoscape_json = layout.cytoscape_json
    if not isinstance(cytoscape_json, dict):
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot restore device placement: "
                f"diagram {placement.diagram_id} has invalid layout JSON"
            ),
        )

    restored_json, changed = device_domain.restore_device_to_cytoscape_json(
        cytoscape_json,
        _restore_node_without_owner(placement.node),
        placement.was_collapsed,
    )
    if changed:
        layout.cytoscape_json = restored_json
        layout.version += 1
        layout.updated_at = _utcnow()
        diagram_repository.update(session, layout)

    return DiagramVersionRef(diagram_id=layout.id, version=layout.version)


def _raise_restore_conflict(exc: IntegrityError, session: Session) -> None:
    session.rollback()
    message = str(exc.orig)
    normalized = message.lower()
    if "ix_connections_unique_pair" in normalized:
        detail = "Connection already exists between these devices"
    elif "devices_pkey" in normalized or "unique constraint failed: devices.id" in normalized:
        detail = "Device ID already exists"
    else:
        detail = "Canvas restore conflict"
    raise HTTPException(status_code=409, detail=detail) from exc