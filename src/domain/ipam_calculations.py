"""Pure IPAM helper calculations for HT-024 domain builders."""
from __future__ import annotations

import ipaddress
from collections.abc import Sequence

from src.domain.ipam_types import (
    IpamAllocationGroupData,
    IpamBlockData,
    IpamCellData,
    IpamClaim,
)
from src.models.types import IpamAddressFamily, IpamCellStatus, IpamRenderMode

_IPV6_UNSUPPORTED_REASON = "HT-024 visualizes IPv4 only."
_IPV4_UNSUPPORTED_REASON = "HT-024 visualizes IPv4 /16 through /32 only."


def classify_network(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
) -> tuple[IpamAddressFamily, IpamRenderMode, str | None]:
    if isinstance(network, ipaddress.IPv6Network):
        return (
            IpamAddressFamily.ipv6,
            IpamRenderMode.unsupported,
            _IPV6_UNSUPPORTED_REASON,
        )

    if network.prefixlen >= 24:
        return (IpamAddressFamily.ipv4, IpamRenderMode.grid, None)
    if 16 <= network.prefixlen <= 23:
        return (IpamAddressFamily.ipv4, IpamRenderMode.block_summary, None)
    return (
        IpamAddressFamily.ipv4,
        IpamRenderMode.unsupported,
        _IPV4_UNSUPPORTED_REASON,
    )


def group_claims(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
    claims: Sequence[IpamClaim],
) -> dict[int, tuple[IpamClaim, ...]]:
    grouped: dict[int, list[IpamClaim]] = {}
    for claim in claims:
        try:
            claim_ip = ipaddress.ip_address(claim.ip_address)
        except ValueError:
            continue
        if claim_ip.version != network.version or claim_ip not in network:
            continue
        grouped.setdefault(int(claim_ip), []).append(claim)

    return {address: tuple(items) for address, items in grouped.items()}


def reserved_endpoints(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> set[int]:
    if isinstance(network, ipaddress.IPv6Network):
        return set()
    if network.prefixlen > 30:
        return set()
    return {int(network.network_address), int(network.broadcast_address)}


def usable_ip_count(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> int:
    if isinstance(network, ipaddress.IPv6Network):
        return 0
    if network.prefixlen <= 30:
        return max(network.num_addresses - 2, 0)
    return network.num_addresses


def block_count(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> int:
    start_int = int(network.network_address)
    end_int = int(network.broadcast_address)
    first_block_start = (start_int // 256) * 256
    last_block_start = (end_int // 256) * 256
    return ((last_block_start - first_block_start) // 256) + 1


def gateway_int(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
    gateway: str | None,
) -> int | None:
    if gateway is None:
        return None
    try:
        gateway_ip = ipaddress.ip_address(gateway)
    except ValueError:
        return None
    if gateway_ip.version != network.version or gateway_ip not in network:
        return None
    return int(gateway_ip)


def status_for_address(
    address_int: int,
    claims: tuple[IpamClaim, ...],
    reserved: set[int],
    gateway: int | None,
) -> tuple[IpamCellStatus, bool, bool]:
    is_gateway = gateway is not None and address_int == gateway
    is_reserved = address_int in reserved

    if len(claims) > 1:
        return (IpamCellStatus.conflict, is_gateway, is_reserved)
    if is_gateway:
        return (IpamCellStatus.gateway, True, is_reserved)
    if is_reserved:
        return (IpamCellStatus.reserved, is_gateway, True)
    if len(claims) == 1:
        return (IpamCellStatus.used, is_gateway, is_reserved)
    return (IpamCellStatus.free, is_gateway, is_reserved)


def build_allocations(
    grouped: dict[int, tuple[IpamClaim, ...]],
    reserved: set[int],
    gateway: int | None,
) -> tuple[IpamAllocationGroupData, ...]:
    allocations: list[IpamAllocationGroupData] = []
    for address_int in sorted(grouped):
        claims = grouped[address_int]
        status, is_gateway, is_reserved = status_for_address(
            address_int,
            claims,
            reserved,
            gateway,
        )
        address = str(ipaddress.ip_address(address_int))
        allocations.append(
            IpamAllocationGroupData(
                address=address,
                block_cidr=str(ipaddress.ip_network(f"{address}/24", strict=False)),
                status=status,
                is_gateway=is_gateway,
                is_reserved=is_reserved,
                claims=claims,
            )
        )
    return tuple(allocations)


def build_grid_cells(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
    grouped: dict[int, tuple[IpamClaim, ...]],
    reserved: set[int],
    gateway: int | None,
) -> tuple[IpamCellData, ...]:
    cells: list[IpamCellData] = []
    start_int = int(network.network_address)
    for raw_ip in network:
        address_int = int(raw_ip)
        claims = grouped.get(address_int, ())
        status, is_gateway, is_reserved = status_for_address(
            address_int,
            claims,
            reserved,
            gateway,
        )
        address = str(raw_ip)
        cells.append(
            IpamCellData(
                address=address,
                host_index=address_int - start_int,
                block_cidr=str(ipaddress.ip_network(f"{address}/24", strict=False)),
                status=status,
                is_gateway=is_gateway,
                is_reserved=is_reserved,
                claim_count=len(claims),
                claims=claims,
            )
        )
    return tuple(cells)


def build_block_summaries(
    network: ipaddress.IPv4Network | ipaddress.IPv6Network,
    grouped: dict[int, tuple[IpamClaim, ...]],
    reserved: set[int],
    gateway: int | None,
) -> tuple[IpamBlockData, ...]:
    blocks: list[IpamBlockData] = []
    start_int = int(network.network_address)
    end_int = int(network.broadcast_address)
    block_start = (start_int // 256) * 256
    block_end_limit = (end_int // 256) * 256

    while block_start <= block_end_limit:
        block_end = block_start + 255
        first = max(block_start, start_int)
        last = min(block_end, end_int)

        in_block = [address for address in grouped if first <= address <= last]
        used_ip_count_value = sum(1 for address in in_block if address not in reserved)
        conflict_ip_count = sum(1 for address in in_block if len(grouped[address]) > 1)
        device_claim_count = sum(len(grouped[address]) for address in in_block)

        reserved_in_block = sum(1 for value in reserved if first <= value <= last)
        usable_ip_count_value = (last - first + 1) - reserved_in_block
        free_ip_count_value = max(usable_ip_count_value - used_ip_count_value, 0)
        utilization_pct = (
            round((used_ip_count_value / usable_ip_count_value) * 100, 2)
            if usable_ip_count_value
            else 0.0
        )

        first_ip = str(ipaddress.ip_address(first))
        last_ip = str(ipaddress.ip_address(last))
        blocks.append(
            IpamBlockData(
                block_cidr=str(ipaddress.ip_network(f"{first_ip}/24", strict=False)),
                first_ip=first_ip,
                last_ip=last_ip,
                usable_ip_count=usable_ip_count_value,
                used_ip_count=used_ip_count_value,
                free_ip_count=free_ip_count_value,
                conflict_ip_count=conflict_ip_count,
                device_claim_count=device_claim_count,
                utilization_pct=utilization_pct,
                gateway_ip=(
                    str(ipaddress.ip_address(gateway))
                    if gateway is not None and first <= gateway <= last
                    else None
                ),
            )
        )

        block_start += 256

    return tuple(blocks)
