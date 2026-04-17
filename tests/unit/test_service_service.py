"""Unit tests for src/services/service_service.py."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.models.device import Device
from src.models.service import Service, ServiceUpdate
from src.models.types import DeviceType
from src.services import service_service


class TestUpdateService:
    def test_update_name_race_integrity_error_returns_409(self, session: Session) -> None:
        device = Device(name="svc-race-device", type=DeviceType.Server)
        session.add(device)
        session.commit()
        session.refresh(device)

        existing = Service(device_id=device.id, name="svc-a")
        target = Service(device_id=device.id, name="svc-b")
        session.add(existing)
        session.add(target)
        session.commit()
        session.refresh(target)

        with patch.object(
            service_service.service_repository,
            "get_by_device_and_name",
            return_value=None,
        ), patch.object(
            service_service.service_repository,
            "update",
            side_effect=IntegrityError(
                "UPDATE services", {}, Exception("uq_services_device_name")
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                service_service.update(target.id, ServiceUpdate(name="svc-a"), session)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Service already exists on this device"


class TestDependencyErrorHandling:
    def test_add_dependency_unmapped_integrity_error_returns_500(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        device = Device(name="svc-dep-device", type=DeviceType.Server)
        session.add(device)
        session.commit()
        session.refresh(device)

        svc_a = Service(device_id=device.id, name="svc-a")
        svc_b = Service(device_id=device.id, name="svc-b")
        session.add(svc_a)
        session.add(svc_b)
        session.commit()
        session.refresh(svc_a)
        session.refresh(svc_b)

        called: dict[str, bool] = {"rollback": False}
        original_rollback = session.rollback

        def rollback_spy() -> None:
            called["rollback"] = True
            original_rollback()

        monkeypatch.setattr(session, "rollback", rollback_spy)

        with patch.object(
            service_service.service_repository,
            "add_dependency",
            side_effect=IntegrityError("INSERT service_dependencies", {}, Exception("unknown constraint")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                service_service.add_dependency(svc_a.id, svc_b.id, session)

        assert called["rollback"] is True
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal database error"

    def test_remove_dependency_missing_edge_returns_404_and_does_not_log_removed(
        self, session: Session
    ) -> None:
        device = Device(name="svc-rm-device", type=DeviceType.Server)
        session.add(device)
        session.commit()
        session.refresh(device)

        svc_a = Service(device_id=device.id, name="svc-rm-a")
        svc_b = Service(device_id=device.id, name="svc-rm-b")
        session.add(svc_a)
        session.add(svc_b)
        session.commit()
        session.refresh(svc_a)
        session.refresh(svc_b)

        with patch.object(service_service.logger, "info") as info_spy:
            with pytest.raises(HTTPException) as exc_info:
                service_service.remove_dependency(svc_a.id, svc_b.id, session)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Dependency not found"
        info_spy.assert_not_called()
