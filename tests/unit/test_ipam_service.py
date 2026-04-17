"""Unit tests for src/services/ipam_service.py."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.models.device import Device
from src.models.device_network import DeviceNetwork
from src.models.network import Network
from src.models.types import DeviceType, IpamCellStatus, IpamRenderMode
from src.repositories import network_repository
from src.services import ipam_service


def _create_device(session: Session, name: str, mac: str | None = None) -> Device:
    device = Device(name=name, type=DeviceType.Server, mac=mac)
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def _create_network(
    session: Session,
    *,
    name: str,
    cidr: str,
    gateway: str | None,
    vlan_id: int | None,
) -> Network:
    network = Network(
        name=name,
        vlan_id=vlan_id,
        cidr=cidr,
        gateway=gateway,
        color="#3b82f6",
    )
    session.add(network)
    session.commit()
    session.refresh(network)
    return network


def _attach(session: Session, device: Device, network: Network, ip_address: str) -> None:
    session.add(
        DeviceNetwork(
            device_id=device.id,
            network_id=network.id,
            ip_address=ip_address,
        )
    )
    session.commit()


class TestIpamService:
    def test_list_networks_builds_page_stats_and_most_utilized_network(
        self,
        session: Session,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        net_a = _create_network(
            session,
            name=f"Mgmt-{suffix}",
            cidr="10.0.10.0/24",
            gateway="10.0.10.1",
            vlan_id=10,
        )
        net_b = _create_network(
            session,
            name=f"Storage-{suffix}",
            cidr="10.0.20.0/24",
            gateway="10.0.20.1",
            vlan_id=20,
        )

        dev_1 = _create_device(session, f"ipam-dev-a-{suffix}")
        dev_2 = _create_device(session, f"ipam-dev-b-{suffix}")
        dev_3 = _create_device(session, f"ipam-dev-c-{suffix}")
        dev_4 = _create_device(session, f"ipam-dev-d-{suffix}")

        _attach(session, dev_1, net_a, "10.0.10.10")
        _attach(session, dev_2, net_a, "10.0.10.11")
        _attach(session, dev_3, net_a, "10.0.10.10")
        _attach(session, dev_4, net_b, "10.0.20.20")

        payload = ipam_service.list_networks(session)

        assert payload.summary.total_networks == 2
        assert payload.summary.visualizable_networks == 2
        assert payload.summary.total_assigned_ips == 4
        assert payload.summary.total_conflicts == 1
        assert payload.summary.most_utilized_network is not None
        assert payload.summary.most_utilized_network.network_id == net_a.id

        by_network_id = {item.network_id: item for item in payload.items}
        assert by_network_id[net_a.id].render_mode == IpamRenderMode.grid
        assert by_network_id[net_a.id].conflict_ip_count == 1
        assert by_network_id[net_a.id].device_claim_count == 3
        assert by_network_id[net_b.id].device_claim_count == 1

    def test_list_networks_returns_none_for_most_utilized_when_all_networks_are_empty(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network_a = _create_network(
            session,
            name=f"EmptyA-{suffix}",
            cidr="10.30.0.0/24",
            gateway="10.30.0.1",
            vlan_id=None,
        )
        network_b = _create_network(
            session,
            name=f"EmptyB-{suffix}",
            cidr="10.31.0.0/24",
            gateway="10.31.0.1",
            vlan_id=None,
        )

        monkeypatch.setattr(
            network_repository,
            "get_all_with_counts",
            lambda _session: [(network_a, 0), (network_b, 0)],
        )
        monkeypatch.setattr(
            network_repository,
            "get_memberships_for_network_ids",
            lambda _session, _network_ids: {
                network_a.id: [],
                network_b.id: [],
            },
        )

        payload = ipam_service.list_networks(session)

        assert payload.summary.total_networks == 2
        assert payload.summary.total_assigned_ips == 0
        assert payload.summary.total_conflicts == 0
        assert payload.summary.most_utilized_network is None

    def test_get_network_detail_returns_404_for_missing_network(self, session: Session) -> None:
        with pytest.raises(HTTPException) as exc_info:
            ipam_service.get_network_detail(uuid.uuid4(), session)
        assert exc_info.value.status_code == 404

    def test_get_network_detail_includes_mac_in_device_claims(self, session: Session) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            session,
            name=f"MacNet-{suffix}",
            cidr="10.40.0.0/24",
            gateway="10.40.0.1",
            vlan_id=40,
        )
        device = _create_device(
            session,
            f"mac-dev-{suffix}",
            mac="aa:bb:cc:dd:ee:ff",
        )
        _attach(session, device, network, "10.40.0.42")

        detail = ipam_service.get_network_detail(network.id, session)

        assert detail.network.render_mode == IpamRenderMode.grid
        claim = detail.allocations[0].device_claims[0]
        assert claim.mac == "aa:bb:cc:dd:ee:ff"

    def test_get_network_detail_groups_duplicate_claims_into_one_conflict_allocation(
        self,
        session: Session,
    ) -> None:
        suffix = uuid.uuid4().hex[:8]
        network = _create_network(
            session,
            name=f"ConflictNet-{suffix}",
            cidr="10.50.0.0/24",
            gateway="10.50.0.1",
            vlan_id=50,
        )
        dev_a = _create_device(session, f"dup-a-{suffix}")
        dev_b = _create_device(session, f"dup-b-{suffix}")
        _attach(session, dev_a, network, "10.50.0.77")
        _attach(session, dev_b, network, "10.50.0.77")

        detail = ipam_service.get_network_detail(network.id, session)

        assert len(detail.allocations) == 1
        assert detail.allocations[0].status == IpamCellStatus.conflict
        assert len(detail.allocations[0].device_claims) == 2
        conflict_cell = next(cell for cell in detail.cells if cell.address == "10.50.0.77")
        assert conflict_cell.status == IpamCellStatus.conflict
