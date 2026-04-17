"""Unit tests for service-layer integrity error handling on write paths."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.connection import Connection, ConnectionCreate, ConnectionUpdate
from src.models.device import Device, DeviceUpdate
from src.models.location import Location, LocationUpdate
from src.models.types import ConnectionType, DeviceType, LocationType
from src.services import connection_service, device_service, location_service


class TestDeviceServiceIntegrityHandling:
    def test_update_integrity_error_rolls_back_and_returns_409(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        device = Device(name="device-update-conflict", type=DeviceType.Server)
        session.add(device)
        session.commit()
        session.refresh(device)

        called: dict[str, bool] = {"rollback": False}
        original_rollback = session.rollback

        def fail_commit() -> None:
            raise IntegrityError("COMMIT devices", {}, Exception("simulated duplicate"))

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        monkeypatch.setattr(session, "commit", fail_commit)
        monkeypatch.setattr(session, "rollback", rollback_spy)

        with pytest.raises(HTTPException) as exc_info:
            device_service.update(
                device.id,
                DeviceUpdate(name="device-update-conflict-2", version=device.version),
                session,
            )

        assert called["rollback"] is True
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Device update conflict"


class TestConnectionServiceIntegrityHandling:
    def test_create_unmapped_integrity_error_rolls_back_and_returns_500(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = Device(name="conn-source", type=DeviceType.Server)
        target = Device(name="conn-target", type=DeviceType.Switch)
        session.add(source)
        session.add(target)
        session.commit()
        session.refresh(source)
        session.refresh(target)

        called: dict[str, bool] = {"rollback": False}
        original_rollback = session.rollback

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        monkeypatch.setattr(session, "rollback", rollback_spy)

        with patch.object(
            connection_service.connection_repository,
            "create",
            side_effect=IntegrityError(
                "INSERT connections",
                {},
                Exception("unexpected database constraint"),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                connection_service.create(
                    ConnectionCreate(
                        source_id=source.id,
                        target_id=target.id,
                        type=ConnectionType.Ethernet,
                        label="core-link",
                    ),
                    session,
                )

        assert called["rollback"] is True
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal database error"

    def test_update_integrity_error_rolls_back_and_returns_409(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = Device(name="conn-upd-source", type=DeviceType.Server)
        target = Device(name="conn-upd-target", type=DeviceType.Switch)
        session.add(source)
        session.add(target)
        session.commit()
        session.refresh(source)
        session.refresh(target)

        conn = Connection(
            source_id=source.id,
            target_id=target.id,
            type=ConnectionType.Ethernet,
            label="edge",
        )
        session.add(conn)
        session.commit()
        session.refresh(conn)

        called: dict[str, bool] = {"rollback": False}
        original_rollback = session.rollback

        def fail_commit() -> None:
            raise IntegrityError("COMMIT connections", {}, Exception("simulated duplicate"))

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        monkeypatch.setattr(session, "commit", fail_commit)
        monkeypatch.setattr(session, "rollback", rollback_spy)

        with pytest.raises(HTTPException) as exc_info:
            connection_service.update(conn.id, ConnectionUpdate(label="edge-updated"), session)

        assert called["rollback"] is True
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Connection update conflict"


class TestLocationServiceIntegrityHandling:
    def test_update_integrity_error_rolls_back_and_returns_409(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        location = Location(
            name="Rack A",
            type=LocationType.rack,
            rack="A",
            row="1",
        )
        session.add(location)
        session.commit()
        session.refresh(location)

        called: dict[str, bool] = {"rollback": False}
        original_rollback = session.rollback

        def fail_commit() -> None:
            raise IntegrityError("COMMIT locations", {}, Exception("simulated duplicate"))

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        monkeypatch.setattr(session, "commit", fail_commit)
        monkeypatch.setattr(session, "rollback", rollback_spy)

        with pytest.raises(HTTPException) as exc_info:
            location_service.update(location.id, LocationUpdate(name="Rack A2"), session)

        assert called["rollback"] is True
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Location update conflict"
