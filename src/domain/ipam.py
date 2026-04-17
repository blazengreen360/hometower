"""Pure IPAM builders for HT-024."""
from __future__ import annotations

import ipaddress
from collections.abc import Sequence

from src.domain.ipam_calculations import (
    block_count,
    build_allocations,
    build_block_summaries,
    build_grid_cells,
    classify_network,
    gateway_int,
    group_claims,
    reserved_endpoints,
    usable_ip_count,
)
from src.domain.ipam_types import (
    IpamAllocationGroupData,
    IpamBlockData,
    IpamCellData,
    IpamClaim,
    IpamDetailData,
    IpamSummaryData,
)
from src.models.types import IpamRenderMode


def build_summary(cidr: str, gateway: str | None, claims: Sequence[IpamClaim]) -> IpamSummaryData:
    network = ipaddress.ip_network(cidr, strict=True)
    grouped = group_claims(network, claims)
    device_claim_count = sum(len(address_claims) for address_claims in grouped.values())
    conflict_ip_count = sum(1 for address_claims in grouped.values() if len(address_claims) > 1)

    address_family, render_mode, unsupported_reason = classify_network(network)
    if render_mode == IpamRenderMode.unsupported:
        return IpamSummaryData(
            address_family=address_family,
            render_mode=render_mode,
            usable_ip_count=None,
            used_ip_count=len(grouped),
            free_ip_count=None,
            conflict_ip_count=conflict_ip_count,
            device_claim_count=device_claim_count,
            utilization_pct=None,
            block_count=None,
            unsupported_reason=unsupported_reason,
        )

    reserved = reserved_endpoints(network)
    usable_ip_count_value = usable_ip_count(network)
    used_ip_count = sum(1 for address in grouped if address not in reserved)
    free_ip_count = max(usable_ip_count_value - used_ip_count, 0)
    utilization_pct = (
        round((used_ip_count / usable_ip_count_value) * 100, 2)
        if usable_ip_count_value
        else 0.0
    )
    block_count_value = block_count(network) if render_mode == IpamRenderMode.block_summary else None

    return IpamSummaryData(
        address_family=address_family,
        render_mode=render_mode,
        usable_ip_count=usable_ip_count_value,
        used_ip_count=used_ip_count,
        free_ip_count=free_ip_count,
        conflict_ip_count=conflict_ip_count,
        device_claim_count=device_claim_count,
        utilization_pct=utilization_pct,
        block_count=block_count_value,
        unsupported_reason=None,
    )


def build_detail(cidr: str, gateway: str | None, claims: Sequence[IpamClaim]) -> IpamDetailData:
    network = ipaddress.ip_network(cidr, strict=True)
    summary = build_summary(cidr, gateway, claims)
    if summary.render_mode == IpamRenderMode.unsupported:
        return IpamDetailData(summary=summary, cells=(), blocks=(), allocations=())

    grouped = group_claims(network, claims)
    reserved = reserved_endpoints(network)
    gateway_value = gateway_int(network, gateway)

    allocations = build_allocations(grouped, reserved, gateway_value)

    if summary.render_mode == IpamRenderMode.grid:
        cells: tuple[IpamCellData, ...] = build_grid_cells(
            network,
            grouped,
            reserved,
            gateway_value,
        )
        return IpamDetailData(summary=summary, cells=cells, blocks=(), allocations=allocations)

    blocks: tuple[IpamBlockData, ...] = build_block_summaries(
        network,
        grouped,
        reserved,
        gateway_value,
    )
    return IpamDetailData(summary=summary, cells=(), blocks=blocks, allocations=allocations)


__all__ = [
    "IpamAllocationGroupData",
    "IpamBlockData",
    "IpamCellData",
    "IpamClaim",
    "IpamDetailData",
    "IpamSummaryData",
    "build_detail",
    "build_summary",
]
