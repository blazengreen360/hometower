"""Unit tests for src/services/network_service.py (HT-022)."""

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.models.device import Device
from src.models.device_network import DeviceNetworkCreate
from src.models.network import NetworkCreate, NetworkUpdate
from src.models.types import DeviceType
from src.services import network_service


def _create_device(session: Session, name: str) -> Device:
    device = Device(name=name, type=DeviceType.Server)
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


class TestNetworkServiceValidation:
    def test_duplicate_case_insensitive_name_returns_409(self, session: Session) -> None:
        network_service.create(
            NetworkCreate(
                name="Management",
                vlan_id=10,
                cidr="10.0.10.0/24",
                gateway="10.0.10.1",
                description="Primary management",
                color="#3b82f6",
            ),
            session,
        )

        with pytest.raises(HTTPException) as exc_info:
            network_service.create(
                NetworkCreate(
                    name="management",
                    vlan_id=20,
                    cidr="10.0.20.0/24",
                    gateway="10.0.20.1",
                    description="Case-insensitive conflict",
                    color="#2563eb",
                ),
                session,
            )
        assert exc_info.value.status_code == 409

    def test_update_cidr_blocked_when_existing_membership_would_be_invalid(
        self,
        session: Session,
    ) -> None:
        device = _create_device(session, name=f"network-svc-dev-{uuid.uuid4().hex[:8]}")
        network = network_service.create(
            NetworkCreate(
                name=f"Storage-{uuid.uuid4().hex[:8]}",
                vlan_id=30,
                cidr="10.0.30.0/24",
                gateway="10.0.30.1",
                description="Storage network",
                color="#0ea5e9",
            ),
            session,
        )

        network_service.attach_to_device(
            device.id,
            DeviceNetworkCreate(network_id=network.id, ip_address="10.0.30.25"),
            session,
        )

        with pytest.raises(HTTPException) as exc_info:
            network_service.update(
                network.id,
                NetworkUpdate(cidr="10.0.31.0/24", gateway="10.0.31.1"),
                session,
            )
        assert exc_info.value.status_code == 400
        assert "is not within subnet" in str(exc_info.value.detail)

    def test_delete_blocked_when_members_exist(self, session: Session) -> None:
        device = _create_device(session, name=f"network-delete-dev-{uuid.uuid4().hex[:8]}")
        network = network_service.create(
            NetworkCreate(
                name=f"Guest-{uuid.uuid4().hex[:8]}",
                vlan_id=40,
                cidr="10.0.40.0/24",
                gateway="10.0.40.1",
                description="Guest network",
                color="#22c55e",
            ),
            session,
        )
        network_service.attach_to_device(
            device.id,
            DeviceNetworkCreate(network_id=network.id, ip_address="10.0.40.50"),
            session,
        )

        with pytest.raises(HTTPException) as exc_info:
            network_service.delete(network.id, session)
        assert exc_info.value.status_code == 400
        assert "devices assigned" in str(exc_info.value.detail)
