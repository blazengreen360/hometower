"""Visible-network IPAM search helpers for HT-024."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from collections.abc import Sequence
import ipaddress
import re

from src.models.ipam import IpamNetworkDetailResponse
from src.models.types import IpamRenderMode

_NON_ID_CHARS = re.compile(r"[^a-zA-Z0-9]+")


@dataclass(frozen=True)
class IpamSearchTargets:
    cell_ids: tuple[str, ...] = ()
    block_ids: tuple[str, ...] = ()
    allocation_addresses: tuple[str, ...] = ()
    scroll_target_id: str | None = None


def normalize_query(raw: str) -> str:
    """Return normalized free-text query for case-insensitive matching."""
    return raw.strip().lower()


def is_ipv4_query(query: str) -> bool:
    """Return True when the query is a valid IPv4 address literal."""
    try:
        ipaddress.IPv4Address(query.strip())
        return True
    except ValueError:
        return False


def build_cell_id(network_id: str, address: str) -> str:
    return f"ipam-cell-{_safe_fragment(network_id)}-{_safe_fragment(address)}"


def build_block_id(network_id: str, block_cidr: str) -> str:
    return f"ipam-block-{_safe_fragment(network_id)}-{_safe_fragment(block_cidr)}"


def build_allocation_id(network_id: str, address: str) -> str:
    return f"ipam-allocation-{_safe_fragment(network_id)}-{_safe_fragment(address)}"


def resolve_visible_matches(
    query: str,
    details_by_network: Mapping[str, IpamNetworkDetailResponse],
) -> dict[str, IpamSearchTargets]:
    """Resolve match targets for currently loaded network detail payloads."""
    normalized = normalize_query(query)
    if not normalized:
        return {}

    ipv4_query = is_ipv4_query(normalized)
    resolved: dict[str, IpamSearchTargets] = {}

    for network_key, detail in details_by_network.items():
        cell_ids: list[str] = []
        block_ids: list[str] = []
        allocation_addresses: list[str] = []
        local_scroll_target: str | None = None

        if ipv4_query:
            local_scroll_target = _resolve_ip_targets(
                normalized,
                network_key,
                detail,
                cell_ids,
                block_ids,
                allocation_addresses,
            )
        else:
            local_scroll_target = _resolve_device_targets(
                normalized,
                network_key,
                detail,
                cell_ids,
                block_ids,
                allocation_addresses,
            )

        if not cell_ids and not block_ids and not allocation_addresses:
            continue

        resolved[network_key] = IpamSearchTargets(
            cell_ids=tuple(cell_ids),
            block_ids=tuple(block_ids),
            allocation_addresses=tuple(allocation_addresses),
            scroll_target_id=local_scroll_target,
        )

    return resolved


def _resolve_device_targets(
    normalized: str,
    network_key: str,
    detail: IpamNetworkDetailResponse,
    cell_ids: list[str],
    block_ids: list[str],
    allocation_addresses: list[str],
) -> str | None:
    scroll_target: str | None = None

    for allocation in detail.allocations:
        if not _allocation_matches_device_name(allocation.device_claims, normalized):
            continue

        if detail.network.render_mode == IpamRenderMode.grid:
            cell_id = build_cell_id(network_key, allocation.address)
            if cell_id not in cell_ids:
                cell_ids.append(cell_id)
            if scroll_target is None:
                scroll_target = cell_id
            continue

        if detail.network.render_mode == IpamRenderMode.block_summary:
            block_id = build_block_id(network_key, allocation.block_cidr)
            if block_id not in block_ids:
                block_ids.append(block_id)
            if allocation.address not in allocation_addresses:
                allocation_addresses.append(allocation.address)
            if scroll_target is None:
                scroll_target = build_allocation_id(network_key, allocation.address)

    return scroll_target


def _resolve_ip_targets(
    normalized: str,
    network_key: str,
    detail: IpamNetworkDetailResponse,
    cell_ids: list[str],
    block_ids: list[str],
    allocation_addresses: list[str],
) -> str | None:
    try:
        query_ip = ipaddress.IPv4Address(normalized)
        network = ipaddress.ip_network(detail.network.cidr, strict=True)
    except ValueError:
        return None

    if query_ip not in network:
        return None

    if detail.network.render_mode == IpamRenderMode.grid:
        has_cell = any(cell.address == normalized for cell in detail.cells)
        if not has_cell:
            return None
        cell_id = build_cell_id(network_key, normalized)
        cell_ids.append(cell_id)
        return cell_id

    if detail.network.render_mode == IpamRenderMode.block_summary:
        block_cidr = str(ipaddress.ip_network(f"{normalized}/24", strict=False))
        block_id = build_block_id(network_key, block_cidr)
        block_ids.append(block_id)

        for allocation in detail.allocations:
            if allocation.address != normalized:
                continue
            allocation_addresses.append(allocation.address)
            return build_allocation_id(network_key, allocation.address)

        return block_id

    return None


def _allocation_matches_device_name(device_claims: Sequence[object], normalized: str) -> bool:
    for claim in device_claims:
        device_name = getattr(claim, "device_name", "")
        if normalized in str(device_name).lower():
            return True
    return False


def _safe_fragment(raw: str) -> str:
    return _NON_ID_CHARS.sub("-", raw).strip("-").lower()
