"""Unit tests for src/ui/services/ipam_search.py."""

from __future__ import annotations

import uuid

from src.models.ipam import (
    IpamAllocationGroupResponse,
    IpamDeviceClaimResponse,
    IpamNetworkDetailResponse,
    IpamNetworkSummaryResponse,
)
from src.models.types import (
    DeviceStatus,
    DeviceType,
    IpamAddressFamily,
    IpamCellStatus,
    IpamRenderMode,
)
from src.ui.services.ipam_search import resolve_visible_matches


def _summary(network_id: uuid.UUID, *, render_mode: IpamRenderMode, cidr: str) -> IpamNetworkSummaryResponse:
    return IpamNetworkSummaryResponse(
        network_id=network_id,
        name=f"Net-{network_id.hex[:6]}",
        vlan_id=None,
        cidr=cidr,
        gateway=None,
        color="#3b82f6",
        address_family=IpamAddressFamily.ipv4,
        render_mode=render_mode,
        usable_ip_count=254,
        used_ip_count=1,
        free_ip_count=253,
        conflict_ip_count=0,
        device_claim_count=1,
        utilization_pct=0.39,
        block_count=None,
        unsupported_reason=None,
    )


def _claim(device_name: str, ip_address: str) -> IpamDeviceClaimResponse:
    return IpamDeviceClaimResponse(
        device_id=uuid.uuid4(),
        device_name=device_name,
        device_type=DeviceType.Server,
        device_status=DeviceStatus.Active,
        mac=None,
        ip_address=ip_address,
    )


def _detail(
    *,
    network_id: uuid.UUID,
    render_mode: IpamRenderMode,
    cidr: str,
    block_cidr: str,
    ip_address: str,
    device_name: str,
) -> IpamNetworkDetailResponse:
    return IpamNetworkDetailResponse(
        network=_summary(network_id, render_mode=render_mode, cidr=cidr),
        cells=[],
        blocks=[],
        allocations=[
            IpamAllocationGroupResponse(
                address=ip_address,
                block_cidr=block_cidr,
                status=IpamCellStatus.used,
                device_claims=[_claim(device_name, ip_address)],
            )
        ],
    )


class TestIpamSearch:
    def test_blank_query_returns_no_targets(self) -> None:
        network_id = uuid.uuid4()
        details = {
            str(network_id): _detail(
                network_id=network_id,
                render_mode=IpamRenderMode.grid,
                cidr="10.0.10.0/24",
                block_cidr="10.0.10.0/24",
                ip_address="10.0.10.42",
                device_name="nas-01",
            )
        }
        assert resolve_visible_matches("   ", details) == {}

    def test_device_name_query_highlights_grid_cell_ids(self) -> None:
        network_id = uuid.uuid4()
        details = {
            str(network_id): _detail(
                network_id=network_id,
                render_mode=IpamRenderMode.grid,
                cidr="10.0.10.0/24",
                block_cidr="10.0.10.0/24",
                ip_address="10.0.10.42",
                device_name="NAS-01",
            )
        }

        result = resolve_visible_matches("nas", details)

        assert str(network_id) in result
        assert len(result[str(network_id)].cell_ids) == 1
        assert result[str(network_id)].scroll_target_id == result[str(network_id)].cell_ids[0]

    def test_ipv4_query_highlights_block_id_for_block_summary_mode(self) -> None:
        network_id = uuid.uuid4()
        details = {
            str(network_id): _detail(
                network_id=network_id,
                render_mode=IpamRenderMode.block_summary,
                cidr="10.20.0.0/16",
                block_cidr="10.20.5.0/24",
                ip_address="10.20.5.77",
                device_name="vm-a",
            )
        }

        result = resolve_visible_matches("10.20.5.90", details)

        assert str(network_id) in result
        assert len(result[str(network_id)].block_ids) == 1
        assert result[str(network_id)].scroll_target_id == result[str(network_id)].block_ids[0]

    def test_ipv4_query_highlights_allocation_when_address_is_claimed_in_block_summary_mode(
        self,
    ) -> None:
        network_id = uuid.uuid4()
        details = {
            str(network_id): _detail(
                network_id=network_id,
                render_mode=IpamRenderMode.block_summary,
                cidr="10.20.0.0/16",
                block_cidr="10.20.5.0/24",
                ip_address="10.20.5.77",
                device_name="vm-a",
            )
        }

        result = resolve_visible_matches("10.20.5.77", details)

        assert result[str(network_id)].allocation_addresses == ("10.20.5.77",)

    def test_each_matching_network_retains_a_local_scroll_target(self) -> None:
        first_id = uuid.uuid4()
        second_id = uuid.uuid4()
        details = {
            str(second_id): _detail(
                network_id=second_id,
                render_mode=IpamRenderMode.grid,
                cidr="10.0.20.0/24",
                block_cidr="10.0.20.0/24",
                ip_address="10.0.20.8",
                device_name="match-device-b",
            ),
            str(first_id): _detail(
                network_id=first_id,
                render_mode=IpamRenderMode.grid,
                cidr="10.0.10.0/24",
                block_cidr="10.0.10.0/24",
                ip_address="10.0.10.8",
                device_name="match-device-a",
            ),
        }

        result = resolve_visible_matches("match-device", details)

        assert result[str(first_id)].scroll_target_id == result[str(first_id)].cell_ids[0]
        assert result[str(second_id)].scroll_target_id == result[str(second_id)].cell_ids[0]
