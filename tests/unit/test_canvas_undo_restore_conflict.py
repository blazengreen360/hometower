"""Unit tests for canvas restore conflict mapping (BUG-002)."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.canvas_undo import (
    PublishedConnectionSnapshot,
    PublishedDeviceDeleteSnapshot,
    PublishedDeviceSnapshot,
)
from src.models.types import ConnectionType, DeviceStatus, DeviceType
from src.services import canvas_undo_service


def _snapshot_with_device(
    device_id: uuid.UUID,
    connections: list[PublishedConnectionSnapshot] | None = None,
) -> PublishedDeviceDeleteSnapshot:
    return PublishedDeviceDeleteSnapshot(
        device=PublishedDeviceSnapshot(
            id=device_id,
            name="restore-target",
            type=DeviceType.Server,
            status=DeviceStatus.Active,
            version=1,
        ),
        connections=connections or [],
        placements=[],
    )


def test_restore_maps_postgres_device_pkey_conflict_to_specific_409(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot_with_device(uuid.uuid4())

    called: dict[str, bool] = {"rollback": False}
    original_rollback = session.rollback

    def rollback_spy() -> None:
        called["rollback"] = True
        original_rollback()

    monkeypatch.setattr(session, "rollback", rollback_spy)

    with patch.object(canvas_undo_service.device_repository, "get_by_id", return_value=None), patch.object(
        canvas_undo_service.device_repository,
        "create",
        side_effect=IntegrityError(
            "INSERT devices",
            {},
            Exception('duplicate key value violates unique constraint "devices_pkey"'),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            canvas_undo_service.restore_published_device_for_canvas(snapshot, session)

    assert called["rollback"] is True
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Device ID already exists"


def test_restore_maps_postgres_connection_unique_pair_conflict_to_specific_409(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_id = uuid.uuid4()
    connection = PublishedConnectionSnapshot(
        id=uuid.uuid4(),
        source_id=device_id,
        target_id=uuid.uuid4(),
        type=ConnectionType.Ethernet,
        label="uplink",
    )
    snapshot = _snapshot_with_device(device_id, [connection])

    called: dict[str, bool] = {"rollback": False}
    original_rollback = session.rollback

    def rollback_spy() -> None:
        called["rollback"] = True
        original_rollback()

    monkeypatch.setattr(session, "rollback", rollback_spy)

    with patch.object(canvas_undo_service.device_repository, "get_by_id", return_value=None), patch.object(
        canvas_undo_service.device_repository,
        "create",
        return_value=None,
    ), patch.object(
        canvas_undo_service.connection_repository,
        "create",
        side_effect=IntegrityError(
            "INSERT connections",
            {},
            Exception('duplicate key value violates unique constraint "ix_connections_unique_pair"'),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            canvas_undo_service.restore_published_device_for_canvas(snapshot, session)

    assert called["rollback"] is True
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Connection already exists between these devices"