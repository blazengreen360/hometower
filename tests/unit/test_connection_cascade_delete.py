"""Regression test for connection cleanup on device deletion."""
from sqlalchemy import text
from sqlmodel import Session

from src.models.connection import Connection
from src.models.device import Device
from src.models.types import ConnectionType, DeviceType
from src.repositories import connection_repository, device_repository


def test_delete_device_cascades_connections(session: Session) -> None:
    session.exec(text("PRAGMA foreign_keys=ON"))

    source = Device(name="cascade-source", type=DeviceType.Server)
    target = Device(name="cascade-target", type=DeviceType.Switch)
    device_repository.create(session, source)
    device_repository.create(session, target)

    connection = Connection(
        source_id=source.id,
        target_id=target.id,
        type=ConnectionType.Ethernet,
    )
    connection_repository.create(session, connection)

    device_repository.delete(session, source)

    assert connection_repository.count_by_device(session, source.id) == 0
    assert connection_repository.count_by_device(session, target.id) == 0
