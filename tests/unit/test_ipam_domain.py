"""Unit tests for src/domain/ipam.py pure builders (HT-024)."""

import uuid

from src.domain.ipam import IpamClaim, build_detail, build_summary
from src.models.types import DeviceStatus, DeviceType, IpamCellStatus, IpamRenderMode


def _claim(ip_address: str, *, name: str = "dev") -> IpamClaim:
    return IpamClaim(
        ip_address=ip_address,
        device_id=uuid.uuid4(),
        device_name=name,
        device_type=DeviceType.Server,
        device_status=DeviceStatus.Active,
    )


class TestIpamSummary:
    def test_build_summary_classifies_grid_for_prefixlen_gte_24(self) -> None:
        summary = build_summary("10.0.10.0/24", "10.0.10.1", [])
        assert summary.render_mode == IpamRenderMode.grid

    def test_build_summary_classifies_block_summary_for_prefixlen_16_to_23(self) -> None:
        summary = build_summary("10.20.0.0/16", "10.20.0.1", [])
        assert summary.render_mode == IpamRenderMode.block_summary

    def test_build_summary_marks_ipv6_unsupported(self) -> None:
        summary = build_summary("fd00::/64", "fd00::1", [])
        assert summary.render_mode == IpamRenderMode.unsupported
        assert summary.unsupported_reason == "HT-024 visualizes IPv4 only."

    def test_build_summary_marks_ipv4_broader_than_16_unsupported(self) -> None:
        summary = build_summary("10.0.0.0/15", "10.0.0.1", [])
        assert summary.render_mode == IpamRenderMode.unsupported

    def test_used_ip_count_excludes_reserved_address_claims(self) -> None:
        summary = build_summary(
            "10.0.10.0/24",
            "10.0.10.1",
            [
                _claim("10.0.10.0", name="reserved-claim"),
                _claim("10.0.10.2", name="host-claim"),
            ],
        )
        assert summary.used_ip_count == 1
        assert summary.device_claim_count == 2


class TestIpamDetail:
    def test_build_detail_emits_256_cells_for_24_with_reserved_endpoints(self) -> None:
        detail = build_detail("10.0.10.0/24", "10.0.10.1", [])
        assert len(detail.cells) == 256
        assert detail.cells[0].address == "10.0.10.0"
        assert detail.cells[0].status == IpamCellStatus.reserved
        assert detail.cells[-1].address == "10.0.10.255"
        assert detail.cells[-1].status == IpamCellStatus.reserved

    def test_build_detail_has_no_reserved_cells_for_31(self) -> None:
        detail = build_detail("10.0.10.0/31", None, [])
        assert len(detail.cells) == 2
        assert all(not cell.is_reserved for cell in detail.cells)
        assert all(cell.status == IpamCellStatus.free for cell in detail.cells)

    def test_status_precedence_conflict_overrides_gateway_and_reserved(self) -> None:
        detail = build_detail(
            "10.0.10.0/24",
            "10.0.10.1",
            [
                _claim("10.0.10.0", name="a"),
                _claim("10.0.10.0", name="b"),
                _claim("10.0.10.1", name="c"),
                _claim("10.0.10.1", name="d"),
            ],
        )
        by_address = {cell.address: cell for cell in detail.cells}
        assert by_address["10.0.10.0"].status == IpamCellStatus.conflict
        assert by_address["10.0.10.1"].status == IpamCellStatus.conflict

    def test_block_summary_uses_parent_network_reserved_rules_not_per_bucket_254(self) -> None:
        detail = build_detail("10.20.0.0/16", "10.20.0.1", [])
        assert detail.summary.render_mode == IpamRenderMode.block_summary
        assert detail.blocks[0].block_cidr == "10.20.0.0/24"
        assert detail.blocks[0].usable_ip_count == 255
        assert detail.blocks[1].block_cidr == "10.20.1.0/24"
        assert detail.blocks[1].usable_ip_count == 256
        assert detail.blocks[-1].block_cidr == "10.20.255.0/24"
        assert detail.blocks[-1].usable_ip_count == 255

    def test_allocations_are_sorted_by_ip_address(self) -> None:
        detail = build_detail(
            "10.0.10.0/24",
            None,
            [
                _claim("10.0.10.42"),
                _claim("10.0.10.5"),
                _claim("10.0.10.10"),
            ],
        )
        assert [allocation.address for allocation in detail.allocations] == [
            "10.0.10.5",
            "10.0.10.10",
            "10.0.10.42",
        ]
