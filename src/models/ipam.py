"""IPAM response models (HT-024)."""
import uuid

from sqlmodel import SQLModel

from src.models.types import (
    DeviceStatus,
    DeviceType,
    IpamAddressFamily,
    IpamCellStatus,
    IpamRenderMode,
)


class IpamDeviceClaimResponse(SQLModel):
    device_id: uuid.UUID
    device_name: str
    device_type: DeviceType
    device_status: DeviceStatus
    mac: str | None = None
    ip_address: str


class IpamMostUtilizedNetworkResponse(SQLModel):
    network_id: uuid.UUID
    name: str
    cidr: str
    utilization_pct: float
    used_ip_count: int
    usable_ip_count: int


class IpamNetworkSummaryResponse(SQLModel):
    network_id: uuid.UUID
    name: str
    vlan_id: int | None = None
    cidr: str
    gateway: str | None = None
    color: str
    address_family: IpamAddressFamily
    render_mode: IpamRenderMode
    usable_ip_count: int | None = None
    used_ip_count: int = 0
    free_ip_count: int | None = None
    conflict_ip_count: int = 0
    device_claim_count: int = 0
    utilization_pct: float | None = None
    block_count: int | None = None
    unsupported_reason: str | None = None


class IpamPageStatsResponse(SQLModel):
    total_networks: int
    visualizable_networks: int
    total_assigned_ips: int
    total_conflicts: int
    most_utilized_network: IpamMostUtilizedNetworkResponse | None = None


class IpamNetworkListResponse(SQLModel):
    summary: IpamPageStatsResponse
    items: list[IpamNetworkSummaryResponse]


class IpamIpCellResponse(SQLModel):
    address: str
    host_index: int
    block_cidr: str
    status: IpamCellStatus
    is_gateway: bool = False
    is_reserved: bool = False
    claim_count: int = 0
    device_claims: list[IpamDeviceClaimResponse] = []


class IpamBlockSummaryResponse(SQLModel):
    block_cidr: str
    first_ip: str
    last_ip: str
    usable_ip_count: int
    used_ip_count: int = 0
    free_ip_count: int = 0
    conflict_ip_count: int = 0
    device_claim_count: int = 0
    utilization_pct: float = 0.0
    gateway_ip: str | None = None


class IpamAllocationGroupResponse(SQLModel):
    address: str
    block_cidr: str
    status: IpamCellStatus
    is_gateway: bool = False
    is_reserved: bool = False
    device_claims: list[IpamDeviceClaimResponse] = []


class IpamNetworkDetailResponse(SQLModel):
    network: IpamNetworkSummaryResponse
    cells: list[IpamIpCellResponse] = []
    blocks: list[IpamBlockSummaryResponse] = []
    allocations: list[IpamAllocationGroupResponse] = []
