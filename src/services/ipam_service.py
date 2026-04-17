"""Read-only IPAM service orchestration (HT-024)."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from src.domain import ipam as ipam_domain
from src.models.ipam import (
    IpamAllocationGroupResponse,
    IpamBlockSummaryResponse,
    IpamDeviceClaimResponse,
    IpamIpCellResponse,
    IpamMostUtilizedNetworkResponse,
    IpamNetworkDetailResponse,
    IpamNetworkListResponse,
    IpamNetworkSummaryResponse,
    IpamPageStatsResponse,
)
from src.models.network import Network
from src.repositories import network_repository


def list_networks(session: Session) -> IpamNetworkListResponse:
    """Return per-network IPAM summaries plus aggregate page statistics."""
    network_pairs = network_repository.get_all_with_counts(session)
    ordered_networks = [network for network, _ in network_pairs]
    network_ids = [network.id for network in ordered_networks]
    memberships_by_network = network_repository.get_memberships_for_network_ids(
        session,
        network_ids,
    )

    items: list[IpamNetworkSummaryResponse] = []
    for network in ordered_networks:
        claims = [
            ipam_domain.IpamClaim(ip_address=membership.ip_address)
            for membership in memberships_by_network.get(network.id, [])
        ]
        summary_data = ipam_domain.build_summary(network.cidr, network.gateway, claims)
        items.append(_to_network_summary(network, summary_data))

    visualizable = [
        item for item in items if item.render_mode.name != "unsupported"
    ]
    utilized_candidates = [
        item
        for item in visualizable
        if item.utilization_pct is not None and item.used_ip_count > 0
    ]
    most_utilized = _pick_most_utilized(utilized_candidates)

    return IpamNetworkListResponse(
        summary=IpamPageStatsResponse(
            total_networks=len(items),
            visualizable_networks=len(visualizable),
            total_assigned_ips=sum(item.device_claim_count for item in items),
            total_conflicts=sum(item.conflict_ip_count for item in items),
            most_utilized_network=most_utilized,
        ),
        items=items,
    )


def get_network_detail(network_id: uuid.UUID, session: Session) -> IpamNetworkDetailResponse:
    """Return detailed IPAM rendering data for one network."""
    network = network_repository.get_by_id(session, network_id)
    if network is None:
        raise HTTPException(status_code=404, detail="Network not found")

    refs = network_repository.get_device_refs(session, network_id)
    claims = [
        ipam_domain.IpamClaim(
            ip_address=ip_address,
            device_id=device.id,
            device_name=device.name,
            device_type=device.type,
            device_status=device.status,
            mac=device.mac,
        )
        for device, ip_address in refs
    ]

    detail = ipam_domain.build_detail(network.cidr, network.gateway, claims)
    network_summary = _to_network_summary(network, detail.summary)

    return IpamNetworkDetailResponse(
        network=network_summary,
        cells=[
            IpamIpCellResponse(
                address=cell.address,
                host_index=cell.host_index,
                block_cidr=cell.block_cidr,
                status=cell.status,
                is_gateway=cell.is_gateway,
                is_reserved=cell.is_reserved,
                claim_count=cell.claim_count,
                device_claims=[_to_device_claim(claim) for claim in cell.claims],
            )
            for cell in detail.cells
        ],
        blocks=[
            IpamBlockSummaryResponse(
                block_cidr=block.block_cidr,
                first_ip=block.first_ip,
                last_ip=block.last_ip,
                usable_ip_count=block.usable_ip_count,
                used_ip_count=block.used_ip_count,
                free_ip_count=block.free_ip_count,
                conflict_ip_count=block.conflict_ip_count,
                device_claim_count=block.device_claim_count,
                utilization_pct=block.utilization_pct,
                gateway_ip=block.gateway_ip,
            )
            for block in detail.blocks
        ],
        allocations=[
            IpamAllocationGroupResponse(
                address=allocation.address,
                block_cidr=allocation.block_cidr,
                status=allocation.status,
                is_gateway=allocation.is_gateway,
                is_reserved=allocation.is_reserved,
                device_claims=[_to_device_claim(claim) for claim in allocation.claims],
            )
            for allocation in detail.allocations
        ],
    )


def _to_network_summary(
    network: Network,
    summary_data: ipam_domain.IpamSummaryData,
) -> IpamNetworkSummaryResponse:
    return IpamNetworkSummaryResponse(
        network_id=network.id,
        name=network.name,
        vlan_id=network.vlan_id,
        cidr=network.cidr,
        gateway=network.gateway,
        color=network.color,
        address_family=summary_data.address_family,
        render_mode=summary_data.render_mode,
        usable_ip_count=summary_data.usable_ip_count,
        used_ip_count=summary_data.used_ip_count,
        free_ip_count=summary_data.free_ip_count,
        conflict_ip_count=summary_data.conflict_ip_count,
        device_claim_count=summary_data.device_claim_count,
        utilization_pct=summary_data.utilization_pct,
        block_count=summary_data.block_count,
        unsupported_reason=summary_data.unsupported_reason,
    )


def _pick_most_utilized(
    candidates: list[IpamNetworkSummaryResponse],
) -> IpamMostUtilizedNetworkResponse | None:
    if not candidates:
        return None

    picked = max(
        candidates,
        key=lambda item: (
            item.utilization_pct if item.utilization_pct is not None else 0.0,
            item.used_ip_count,
            item.name,
        ),
    )
    if picked.utilization_pct is None or picked.usable_ip_count is None:
        return None

    return IpamMostUtilizedNetworkResponse(
        network_id=picked.network_id,
        name=picked.name,
        cidr=picked.cidr,
        utilization_pct=picked.utilization_pct,
        used_ip_count=picked.used_ip_count,
        usable_ip_count=picked.usable_ip_count,
    )


def _to_device_claim(claim: ipam_domain.IpamClaim) -> IpamDeviceClaimResponse:
    if claim.device_id is None or claim.device_type is None or claim.device_status is None:
        raise ValueError("IPAM detail claim is missing device identity fields")
    return IpamDeviceClaimResponse(
        device_id=claim.device_id,
        device_name=claim.device_name,
        device_type=claim.device_type,
        device_status=claim.device_status,
        mac=claim.mac,
        ip_address=claim.ip_address,
    )
