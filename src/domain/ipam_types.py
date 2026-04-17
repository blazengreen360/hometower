"""Pure IPAM dataclasses for HT-024 domain builders."""
from __future__ import annotations

from dataclasses import dataclass
import uuid

from src.models.types import (
    DeviceStatus,
    DeviceType,
    IpamAddressFamily,
    IpamCellStatus,
    IpamRenderMode,
)


@dataclass(frozen=True)
class IpamClaim:
    ip_address: str
    device_id: uuid.UUID | None = None
    device_name: str = ""
    device_type: DeviceType | None = None
    device_status: DeviceStatus | None = None
    mac: str | None = None


@dataclass(frozen=True)
class IpamSummaryData:
    address_family: IpamAddressFamily
    render_mode: IpamRenderMode
    usable_ip_count: int | None
    used_ip_count: int
    free_ip_count: int | None
    conflict_ip_count: int
    device_claim_count: int
    utilization_pct: float | None
    block_count: int | None
    unsupported_reason: str | None


@dataclass(frozen=True)
class IpamCellData:
    address: str
    host_index: int
    block_cidr: str
    status: IpamCellStatus
    is_gateway: bool
    is_reserved: bool
    claim_count: int
    claims: tuple[IpamClaim, ...]


@dataclass(frozen=True)
class IpamBlockData:
    block_cidr: str
    first_ip: str
    last_ip: str
    usable_ip_count: int
    used_ip_count: int
    free_ip_count: int
    conflict_ip_count: int
    device_claim_count: int
    utilization_pct: float
    gateway_ip: str | None


@dataclass(frozen=True)
class IpamAllocationGroupData:
    address: str
    block_cidr: str
    status: IpamCellStatus
    is_gateway: bool
    is_reserved: bool
    claims: tuple[IpamClaim, ...]


@dataclass(frozen=True)
class IpamDetailData:
    summary: IpamSummaryData
    cells: tuple[IpamCellData, ...]
    blocks: tuple[IpamBlockData, ...]
    allocations: tuple[IpamAllocationGroupData, ...]
