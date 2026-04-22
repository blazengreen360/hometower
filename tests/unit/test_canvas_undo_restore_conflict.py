"""Unit tests for canvas restore conflict mapping (BUG-002)."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.canvas_undo import (
    DiagramPlacementSnapshot,
    DiagramVersionRef,
    PublishedConnectionSnapshot,
    PublishedDeviceDeleteSnapshot,
    PublishedDeviceSnapshot,
)
from src.models.types import ConnectionType, DeviceStatus, DeviceType
from src.services import canvas_undo_service
from src.services import canvas_undo_service_restore_support
from src.services.canvas_undo_service_restore_support import _build_restore_token


def _snapshot_with_device(
    device_id: uuid.UUID,
    connections: list[PublishedConnectionSnapshot] | None = None,
) -> PublishedDeviceDeleteSnapshot:
    snapshot = PublishedDeviceDeleteSnapshot(
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
    snapshot.restore_token = _build_restore_token(snapshot, None, None)
    return snapshot


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


def test_restore_snapshot_placements_skips_immutable_history_layouts(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_id = uuid.uuid4()
    immutable_diagram_id = uuid.uuid4()
    mutable_diagram_id = uuid.uuid4()
    snapshot = _snapshot_with_device(device_id)
    snapshot.placements = [
        DiagramPlacementSnapshot(
            diagram_id=immutable_diagram_id,
            node={"data": {"id": str(device_id)}},
        ),
        DiagramPlacementSnapshot(
            diagram_id=mutable_diagram_id,
            node={"data": {"id": str(device_id)}},
        ),
    ]

    restored_ids: list[uuid.UUID] = []

    def restore_spy(
        placement: DiagramPlacementSnapshot,
        restore_session: Session,
        owner_id: uuid.UUID | None,
    ) -> DiagramVersionRef:
        del restore_session, owner_id
        restored_ids.append(placement.diagram_id)
        return DiagramVersionRef(diagram_id=placement.diagram_id, version=7)

    monkeypatch.setattr(
        canvas_undo_service_restore_support.topology_history_repository,
        "get_immutable_diagram_ids",
        lambda restore_session, diagram_ids: {immutable_diagram_id},
    )
    monkeypatch.setattr(
        canvas_undo_service_restore_support,
        "_restore_snapshot_placement",
        restore_spy,
    )

    modified_diagrams = canvas_undo_service_restore_support._restore_snapshot_placements(
        snapshot,
        session,
        None,
    )

    assert restored_ids == [mutable_diagram_id]
    assert [diagram.diagram_id for diagram in modified_diagrams] == [mutable_diagram_id]
    assert [diagram.version for diagram in modified_diagrams] == [7]