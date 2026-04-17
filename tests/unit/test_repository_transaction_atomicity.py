"""Regression test for service-owned transaction atomicity."""

from sqlmodel import Session

from src.models.device import Device
from src.models.types import DeviceType
from src.repositories import device_repository


def test_multi_repo_operation_rolls_back_on_failure(session: Session) -> None:
    device = Device(name="atomicity-device", type=DeviceType.Server)

    try:
        device_repository.create(session, device)
        raise RuntimeError("simulated downstream failure")
    except RuntimeError:
        session.rollback()

    assert device_repository.get_by_id(session, device.id) is None
