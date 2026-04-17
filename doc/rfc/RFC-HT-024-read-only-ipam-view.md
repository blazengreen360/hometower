# RFC: Read-Only IPAM View

**Story:** HT-024  
**Status:** Ready for Implementation  
**Date:** 2026-04-14  
**Author:** Architect

---

## 1. Overview

HT-024 adds a read-only IP address management page at `/ipam` on top of the shipped `Network` + `DeviceNetwork` model from HT-022. The page shows aggregate page statistics, per-network utilization summaries, lazy-loaded expandable IP detail, duplicate-IP conflict detection, and click-through navigation from used addresses to `/topology?device_id={id}`.

This story does **not** change persistence. Existing `Network`, `DeviceNetwork`, and `Device` rows already contain the required source data. HT-024 therefore adds a dedicated read-only IPAM stack rather than extending the existing network CRUD stack with visualization concerns. In particular:

- Do **not** add IPAM aggregation to `src/services/network_service.py`. That file already owns CRUD + membership write orchestration and is close to the file-size budget.
- Do **not** add new tables, columns, constraints, or migrations.
- Do create a separate `src/domain/ipam.py`, `src/models/ipam.py`, `src/services/ipam_service.py`, `src/api/routers/ipam.py`, and `/ipam` UI modules.

Critical implementation path:

1. Add IPAM enums/read models and pure domain builders.
2. Add repository batch helper, dedicated IPAM service, and read-only API router.
3. Build the `/ipam` page with lazy detail loading, client-side visible-network search, and topology navigation.
4. Lock the behavior with unit/integration/page-execution tests and update `CHANGELOG.md`.

---

## 2. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/models/types.py` | The shared enum vocabulary for IPAM response states and render modes. |
| `src/models/ipam.py` | The HTTP response contract for IPAM summary/detail payloads independent of persistence models. |
| `src/domain/ipam.py` | The IPv4 allocation/status rules, conflict detection, and `/24` block roll-up decision. |
| `src/repositories/network_repository.py` | The SQLModel query shape for batch membership lookup across networks. |
| `src/services/ipam_service.py` | Read-only orchestration from repository rows into IPAM response models. |
| `src/api/routers/ipam.py` | The public HTTP contract for IPAM reads without mixing them into network CRUD routes. |
| `src/ui/services/ipam_data.py` | How the `/ipam` page fetches and caches summary/detail payloads. |
| `src/ui/services/ipam_search.py` | How a free-text search term is resolved into visible cell/block highlights. |
| `src/ui/components/ipam_stats_row.py` | The aggregate-stat card rendering for the IPAM header. |
| `src/ui/components/ipam_grid.py` | The compact IPv4 cell-grid rendering for `/24` and more specific networks. |
| `src/ui/components/ipam_block_summary.py` | The grouped `/24` block-summary rendering for larger IPv4 networks. |
| `src/ui/pages/ipam.py` | Page-level state coordination: auth, lazy expansion, search, and navigation wiring. |

---

## 3. Data Model Changes

Persistence schema change: **none**  
Alembic migration required: **no**  
DevOps-Engineer migration review required: **no**

`Network`, `DeviceNetwork`, and `Device` remain the authoritative source models. HT-024 adds only read models and shared enums.

### 3.1 Modified file: `src/models/types.py`

Add new shared enums to the existing central enum file instead of scattering IPAM-specific enums across feature files.

```diff
@@
 class ServiceStatus(str, Enum):
     running = "running"
     stopped = "stopped"
     unknown = "unknown"
+
+
+class IpamAddressFamily(str, Enum):
+    ipv4 = "ipv4"
+    ipv6 = "ipv6"
+
+
+class IpamRenderMode(str, Enum):
+    grid = "grid"
+    block_summary = "block_summary"
+    unsupported = "unsupported"
+
+
+class IpamCellStatus(str, Enum):
+    free = "free"
+    used = "used"
+    gateway = "gateway"
+    conflict = "conflict"
+    reserved = "reserved"
```

### 3.2 New file: `src/models/ipam.py`

```python
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
```

### 3.3 Exact summary-route response shape

`GET /api/ipam/networks`

```json
{
  "summary": {
    "total_networks": 4,
    "visualizable_networks": 3,
    "total_assigned_ips": 38,
    "total_conflicts": 1,
    "most_utilized_network": {
      "network_id": "7ce883af-4e19-4f0f-b4d8-c6f57252d2f8",
      "name": "Management",
      "cidr": "10.0.10.0/24",
      "utilization_pct": 9.06,
      "used_ip_count": 23,
      "usable_ip_count": 254
    }
  },
  "items": [
    {
      "network_id": "7ce883af-4e19-4f0f-b4d8-c6f57252d2f8",
      "name": "Management",
      "vlan_id": 10,
      "cidr": "10.0.10.0/24",
      "gateway": "10.0.10.1",
      "color": "#3b82f6",
      "address_family": "ipv4",
      "render_mode": "grid",
      "usable_ip_count": 254,
      "used_ip_count": 23,
      "free_ip_count": 231,
      "conflict_ip_count": 1,
      "device_claim_count": 24,
      "utilization_pct": 9.06,
      "block_count": null,
      "unsupported_reason": null
    },
    {
      "network_id": "9dc65844-8188-465c-98b5-64c12c409d82",
      "name": "Backbone",
      "vlan_id": null,
      "cidr": "10.20.0.0/16",
      "gateway": "10.20.0.1",
      "color": "#22d3ee",
      "address_family": "ipv4",
      "render_mode": "block_summary",
      "usable_ip_count": 65534,
      "used_ip_count": 401,
      "free_ip_count": 65133,
      "conflict_ip_count": 0,
      "device_claim_count": 401,
      "utilization_pct": 0.61,
      "block_count": 256,
      "unsupported_reason": null
    },
    {
      "network_id": "b6c7a4fb-03c6-4211-b7a0-5f5d62fc93e2",
      "name": "IPv6 Lab",
      "vlan_id": null,
      "cidr": "fd00::/64",
      "gateway": "fd00::1",
      "color": "#8b5cf6",
      "address_family": "ipv6",
      "render_mode": "unsupported",
      "usable_ip_count": null,
      "used_ip_count": 0,
      "free_ip_count": null,
      "conflict_ip_count": 0,
      "device_claim_count": 0,
      "utilization_pct": null,
      "block_count": null,
      "unsupported_reason": "HT-024 visualizes IPv4 only."
    }
  ]
}
```

### 3.4 Exact detail-route response shape

`GET /api/ipam/networks/{network_id}`

Grid-mode example (`/24`, `/25`, `/26`, ... `/32`):

```json
{
  "network": {
    "network_id": "7ce883af-4e19-4f0f-b4d8-c6f57252d2f8",
    "name": "Management",
    "vlan_id": 10,
    "cidr": "10.0.10.0/24",
    "gateway": "10.0.10.1",
    "color": "#3b82f6",
    "address_family": "ipv4",
    "render_mode": "grid",
    "usable_ip_count": 254,
    "used_ip_count": 23,
    "free_ip_count": 231,
    "conflict_ip_count": 1,
    "device_claim_count": 24,
    "utilization_pct": 9.06,
    "block_count": null,
    "unsupported_reason": null
  },
  "cells": [
    {
      "address": "10.0.10.0",
      "host_index": 0,
      "block_cidr": "10.0.10.0/24",
      "status": "reserved",
      "is_gateway": false,
      "is_reserved": true,
      "claim_count": 0,
      "device_claims": []
    },
    {
      "address": "10.0.10.1",
      "host_index": 1,
      "block_cidr": "10.0.10.0/24",
      "status": "gateway",
      "is_gateway": true,
      "is_reserved": false,
      "claim_count": 0,
      "device_claims": []
    },
    {
      "address": "10.0.10.42",
      "host_index": 42,
      "block_cidr": "10.0.10.0/24",
      "status": "used",
      "is_gateway": false,
      "is_reserved": false,
      "claim_count": 1,
      "device_claims": [
        {
          "device_id": "6abaf558-5c6d-4ca5-84d0-1bde8d32c97f",
          "device_name": "nas-01",
          "device_type": "NAS",
          "device_status": "Active",
          "mac": "aa:bb:cc:dd:ee:ff",
          "ip_address": "10.0.10.42"
        }
      ]
    },
    {
      "address": "10.0.10.77",
      "host_index": 77,
      "block_cidr": "10.0.10.0/24",
      "status": "conflict",
      "is_gateway": false,
      "is_reserved": false,
      "claim_count": 2,
      "device_claims": [
        {
          "device_id": "6ff10eb5-8890-4e6d-81fd-b31c5d24ad4d",
          "device_name": "vm-a",
          "device_type": "VM",
          "device_status": "Active",
          "mac": null,
          "ip_address": "10.0.10.77"
        },
        {
          "device_id": "3a39cce8-fa9d-4f2c-9f72-6b9841f4555c",
          "device_name": "vm-b",
          "device_type": "VM",
          "device_status": "Active",
          "mac": null,
          "ip_address": "10.0.10.77"
        }
      ]
    }
  ],
  "blocks": [],
  "allocations": [
    {
      "address": "10.0.10.42",
      "block_cidr": "10.0.10.0/24",
      "status": "used",
      "is_gateway": false,
      "is_reserved": false,
      "device_claims": [
        {
          "device_id": "6abaf558-5c6d-4ca5-84d0-1bde8d32c97f",
          "device_name": "nas-01",
          "device_type": "NAS",
          "device_status": "Active",
          "mac": "aa:bb:cc:dd:ee:ff",
          "ip_address": "10.0.10.42"
        }
      ]
    }
  ]
}
```

Block-summary example (`/23` through `/16`): same `network` object, empty `cells`, one `blocks` row per `/24` bucket, and `allocations` populated only for claimed addresses.

Unsupported example (IPv6 or IPv4 broader than `/16`): `cells=[]`, `blocks=[]`, `allocations=[]`, and `network.render_mode="unsupported"`.

---

## 4. Domain Logic

Create `src/domain/ipam.py`. Keep all status classification, conflict detection, and `/24` roll-up logic pure and fully testable.

### 4.1 Exact domain interfaces

```python
"""Pure IPAM builders for HT-024."""
from dataclasses import dataclass
import ipaddress
import uuid
from collections.abc import Sequence

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


def build_summary(cidr: str, gateway: str | None, claims: Sequence[IpamClaim]) -> IpamSummaryData:
    ...


def build_detail(cidr: str, gateway: str | None, claims: Sequence[IpamClaim]) -> IpamDetailData:
    ...
```

### 4.2 Required rules and invariants

1. `build_summary()` and `build_detail()` must accept canonical CIDR strings and canonical IP strings. The service layer is responsible for passing normalized values from persisted data.
2. Render-mode classification:
   - IPv4 with prefix length `>= 24` -> `IpamRenderMode.grid`
   - IPv4 with prefix length between `16` and `23` inclusive -> `IpamRenderMode.block_summary`
   - IPv4 broader than `/16` -> `IpamRenderMode.unsupported`
   - IPv6 -> `IpamRenderMode.unsupported`
3. Unsupported networks do **not** raise. They return summary data with `unsupported_reason` and empty detail arrays.
4. Status precedence for each address is fixed and must be identical in summary/detail computation:
   - `conflict` if two or more claims exist for the same address
   - `gateway` if the address equals the network gateway and there is no conflict
   - `reserved` if the address is the IPv4 network or broadcast address and there is no conflict or gateway override
   - `used` if exactly one claim exists and none of the above apply
   - `free` otherwise
5. Reserved-address detection must follow actual IPv4 semantics:
   - Prefix length `<= 30`: the network and broadcast addresses are reserved
   - `/31` and `/32`: no reserved addresses are emitted
6. `used_ip_count` means distinct claimed **usable** addresses. Claims on reserved addresses remain visible in detail but do **not** increase `used_ip_count` or `utilization_pct`.
7. `device_claim_count` means raw `DeviceNetwork` rows. A duplicate IP conflict with two devices increments `device_claim_count` by `2` and `conflict_ip_count` by `1`.
8. `utilization_pct` is `(used_ip_count / usable_ip_count) * 100`, rounded to two decimal places, or `None` when the network is unsupported.
9. Grid mode must emit every address in ascending IP order, including reserved addresses. Example: `/24` emits `256` `cells`, not `254`.
10. Block-summary mode must bucket addresses by `/24` for display, but `usable_ip_count` per block must be computed against the parent network, not by pretending each `/24` bucket is an actual subnet. For a `/16`, the first and last buckets have `255` usable addresses and the middle buckets have `256`.
11. `allocations` contains one row per distinct claimed address, sorted by ascending IP. It exists in both grid and block-summary detail responses so UI search can use one uniform data shape.
12. Search normalization is **not** a domain concern. Keep it in a UI-layer helper.

---

## 5. Service Layer

Create a dedicated `src/services/ipam_service.py`. Do **not** extend `src/services/network_service.py`.

Rationale:

- `network_service.py` already owns network CRUD and membership writes.
- HT-024 is read-only and aggregation-heavy rather than transaction-heavy.
- Mixing both concerns would make one service file own two different design decisions and push it past the file-cap guardrail.

### 5.1 Exact service interfaces

```python
"""Read-only IPAM service orchestration (HT-024)."""
import uuid

from fastapi import HTTPException
from sqlmodel import Session

from src.domain import ipam as ipam_domain
from src.models.ipam import IpamNetworkDetailResponse, IpamNetworkListResponse
from src.repositories import network_repository


def list_networks(session: Session) -> IpamNetworkListResponse:
    ...


def get_network_detail(network_id: uuid.UUID, session: Session) -> IpamNetworkDetailResponse:
    ...
```

### 5.2 Required orchestration behavior

`list_networks(session)`:

1. Call `network_repository.get_all_with_counts(session)` for the canonical network ordering already used elsewhere.
2. Call a new batch helper on `network_repository` to fetch all memberships grouped by `network_id` in one query.
3. For each network, build summary data via `ipam_domain.build_summary()`.
4. Build `IpamNetworkSummaryResponse` rows.
5. Aggregate page stats:
   - `total_networks = len(items)`
   - `visualizable_networks = count(render_mode != unsupported)`
   - `total_assigned_ips = sum(device_claim_count)`
   - `total_conflicts = sum(conflict_ip_count)`
   - `most_utilized_network = max(utilization_pct)` among visualizable networks with `used_ip_count > 0`; return `None` when all visualizable networks have zero assignments
6. Tie-break `most_utilized_network` deterministically by `(utilization_pct, used_ip_count, name)`.

`get_network_detail(network_id, session)`:

1. Read the network with `network_repository.get_by_id(session, network_id)`.
2. Raise `HTTPException(status_code=404, detail="Network not found")` when absent.
3. Reuse `network_repository.get_device_refs(session, network_id)` to fetch `Device` rows plus claimed IPs.
4. Convert repository rows into domain `IpamClaim` values including `device.name`, `device.type`, `device.status`, and `device.mac`.
5. Call `ipam_domain.build_detail()`.
6. Map the domain output to `IpamNetworkDetailResponse`.

Transaction rule: no `session.commit()` and no rollback paths are needed because HT-024 adds only reads.

### 5.3 Repository change in existing file: `src/repositories/network_repository.py`

Do **not** create `ipam_repository.py`. The persistence concern is still `Network` + `DeviceNetwork`, so the existing repository remains the correct boundary.

Add this batch helper:

```diff
@@
 def get_memberships_for_network(
     session: Session, network_id: uuid.UUID
 ) -> list[DeviceNetwork]:
     """Return all device-network rows for a network."""
     stmt = select(DeviceNetwork).where(DeviceNetwork.network_id == network_id)
     return list(session.exec(stmt).all())
+
+
+def get_memberships_for_network_ids(
+    session: Session,
+    network_ids: list[uuid.UUID],
+) -> dict[uuid.UUID, list[DeviceNetwork]]:
+    """Return grouped membership rows for the provided network ids."""
+    if not network_ids:
+        return {}
+
+    grouped: dict[uuid.UUID, list[DeviceNetwork]] = {
+        network_id: [] for network_id in network_ids
+    }
+    stmt = (
+        select(DeviceNetwork)
+        .where(col(DeviceNetwork.network_id).in_(network_ids))
+        .order_by(col(DeviceNetwork.network_id), col(DeviceNetwork.ip_address))
+    )
+    for membership in session.exec(stmt).all():
+        grouped[membership.network_id].append(membership)
+    return grouped
```

---

## 6. API Layer

Create a dedicated router: `src/api/routers/ipam.py`.

Why a new router instead of extending `src/api/routers/networks.py`:

- `networks.py` currently hides CRUD for the persistent network resource.
- IPAM is a derived read model, not CRUD on `Network`.
- A separate `/ipam` router avoids path-shape ambiguity under the existing `/{network_id}` route and keeps response models focused.

### 6.1 Exact route signatures

```python
"""IPAM router — read-only derived views over Network + DeviceNetwork."""
import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.ipam import IpamNetworkDetailResponse, IpamNetworkListResponse
from src.models.types import Role
from src.services import ipam_service
from src.utils.db import get_session

router = APIRouter(prefix="/ipam", tags=["ipam"])


@router.get(
    "/networks",
    response_model=IpamNetworkListResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_ipam_networks(
    session: Session = Depends(get_session),
) -> IpamNetworkListResponse:
    return ipam_service.list_networks(session)


@router.get(
    "/networks/{network_id}",
    response_model=IpamNetworkDetailResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_ipam_network_detail(
    network_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> IpamNetworkDetailResponse:
    return ipam_service.get_network_detail(network_id, session)
```

### 6.2 API contract table

| Method | Path | response_model | Required role |
|---|---|---|---|
| `GET` | `/api/ipam/networks` | `IpamNetworkListResponse` | `Reader` |
| `GET` | `/api/ipam/networks/{network_id}` | `IpamNetworkDetailResponse` | `Reader` |

### 6.3 Modified file: `src/api/app.py`

```diff
@@
 from src.api.routers.health import router as health_router
+from src.api.routers.ipam import router as ipam_router
 from src.api.routers.locations import router as locations_router
 from src.api.routers.networks import router as networks_router
@@
 app.include_router(health_router, prefix="/api")
+app.include_router(ipam_router, prefix="/api")
 app.include_router(locations_router, prefix="/api")
 app.include_router(networks_router, prefix="/api")
```

---

## 7. UI Layer

HT-024 adds a new authenticated page at `/ipam`. The page is read-only and Reader-accessible.

### 7.1 Page and component split

Create these files:

- `src/ui/pages/ipam.py`
  - Owns auth check, page state, summary fetch, lazy detail fetch, search text, and scroll-to-match behavior.
- `src/ui/components/ipam_stats_row.py`
  - Renders the four aggregate header cards from `IpamPageStatsResponse`.
- `src/ui/components/ipam_grid.py`
  - Renders compact clickable address cells for `render_mode="grid"`.
- `src/ui/components/ipam_block_summary.py`
  - Renders `/24` bucket cards for `render_mode="block_summary"`.
- `src/ui/services/ipam_data.py`
  - Fetches `/api/ipam/networks` and `/api/ipam/networks/{id}` and validates them into `src/models/ipam.py` response models.
- `src/ui/services/ipam_search.py`
  - Pure UI helper for visible-network search resolution.

### 7.2 Exact page flow

`src/ui/pages/ipam.py`:

1. `redirect_if_unauthenticated(current_path="/ipam")`; no role redirect because `Reader` is allowed.
2. Fetch summary data once on page load via `load_ipam_summary(token)`.
3. Render:
   - page title row: `IPAM` + a small `Read-only` badge
   - search input: placeholder `Search by IP or device name...`, debounce `200`
   - `ipam_stats_row` from summary payload
   - one `ui.expansion(...)` per network summary item
4. Expansion behavior:
   - first expand -> fetch detail via `load_ipam_detail(token, network_id)`
   - subsequent expands -> use cached detail held in page state
   - do not auto-refresh cached detail during the page session
5. Expansion header content per network:
   - network name
   - VLAN chip when present
   - CIDR text
   - utilization bar using `used_ip_count / usable_ip_count`
   - `X conflicts` badge when `conflict_ip_count > 0`
   - render-mode badge when `block_summary` or `unsupported`
6. Expansion body:
   - `grid` -> `render_ipam_grid(detail, search_targets, on_open_device)`
   - `block_summary` -> `render_ipam_block_summary(detail, search_targets, on_open_device)`
   - `unsupported` -> neutral info row with `unsupported_reason`
7. Cell click behavior:
   - if an address has exactly one `device_claim`, navigate to `/topology?device_id={id}`
   - if a cell is `conflict`, render per-device chips/buttons inside the tooltip or inline match area; each button navigates to the selected device's topology focus
   - free, gateway-only, and reserved-only cells do not navigate

### 7.3 Search behavior

Search remains client-side and only operates across **visible networks**, meaning networks whose detail payload has already been loaded by expansion.

Create `src/ui/services/ipam_search.py` with these exact interfaces:

```python
from dataclasses import dataclass
from collections.abc import Mapping

from src.models.ipam import IpamNetworkDetailResponse


@dataclass(frozen=True)
class IpamSearchTargets:
    cell_ids: tuple[str, ...] = ()
    block_ids: tuple[str, ...] = ()
    allocation_addresses: tuple[str, ...] = ()
    scroll_target_id: str | None = None


def normalize_query(raw: str) -> str:
    ...


def is_ipv4_query(query: str) -> bool:
    ...


def resolve_visible_matches(
    query: str,
    details_by_network: Mapping[str, IpamNetworkDetailResponse],
) -> dict[str, IpamSearchTargets]:
    ...
```

Required behavior:

1. Blank query -> clear all highlights.
2. Device-name query:
   - search case-insensitively against `device_claims[].device_name`
   - grid mode: highlight exact address cells
   - block-summary mode: highlight the containing block card and the matching allocation row(s)
3. IPv4 query:
   - grid mode: highlight the exact cell if present in the loaded detail payload
   - block-summary mode: highlight the containing `/24` block card even when the queried address is free; if the address is claimed, also highlight the matching allocation row
4. The first match in page order becomes `scroll_target_id`; page code calls `scrollIntoView()` via `ui.run_javascript()`.
5. Search does **not** auto-expand collapsed rows. That would silently change the visible scope and create N+1 requests during typing.

### 7.4 Performance strategy

1. Page load makes exactly one summary request: `GET /api/ipam/networks`.
2. Detail requests are lazy and per-network: only on first expansion.
3. Grid mode is capped at IPv4 prefix length `>= 24`, so the largest cell payload is `256` addresses.
4. Block-summary mode is capped at `/23` through `/16`, so the largest rendered block count is `256` `/24` buckets.
5. IPv4 networks broader than `/16` and all IPv6 networks return `render_mode="unsupported"`; they still appear in the summary list but do not attempt high-cardinality rendering.
6. Search never re-hits the API while typing. It operates on cached detail payloads only.
7. `allocations` exists in every detail payload specifically so large-network search does not require enumerating free addresses.

### 7.5 Design tokens

Modify `src/ui/design/tokens.py` by adding theme keys for IPAM cell states. `src/ui/design/theme_engine.py` already converts every `THEMES` key to `--ht-*`, so no theme-engine code change is required.

```diff
@@ "dark": {
         "success":           "#4ade80",
         "warning":           "#fbbf24",
         "error":             "#f87171",
+        "ipam_used":         "#4ade80",
+        "ipam_free":         "#475569",
+        "ipam_gateway":      "#38bdf8",
+        "ipam_conflict":     "#f87171",
+        "ipam_reserved":     "#fbbf24",
@@ "light": {
         "success":           "#16a34a",
         "warning":           "#d97706",
         "error":             "#dc2626",
+        "ipam_used":         "#16a34a",
+        "ipam_free":         "#cbd5e1",
+        "ipam_gateway":      "#0284c7",
+        "ipam_conflict":     "#dc2626",
+        "ipam_reserved":     "#d97706",
@@ "midnight": {
         "success":           "#4ade80",
         "warning":           "#fbbf24",
         "error":             "#f87171",
+        "ipam_used":         "#4ade80",
+        "ipam_free":         "#334155",
+        "ipam_gateway":      "#22d3ee",
+        "ipam_conflict":     "#f87171",
+        "ipam_reserved":     "#fbbf24",
```

Use the generated CSS variables directly in IPAM components:

- `var(--ht-ipam-used)`
- `var(--ht-ipam-free)`
- `var(--ht-ipam-gateway)`
- `var(--ht-ipam-conflict)`
- `var(--ht-ipam-reserved)`

### 7.6 Existing-file diffs

`src/ui/components/sidebar.py`

```diff
@@
 _NAV_ITEMS: list[dict[str, str]] = [
     {"label": "Dashboard", "route": "/", "icon": "dashboard"},
     {"label": "Workspaces", "route": "/workspaces", "icon": "workspaces"},
     {"label": "Inventory", "route": "/inventory", "icon": "inventory_2"},
+    {"label": "IPAM", "route": "/ipam", "icon": "grid_view"},
     {"label": "Map", "route": "/map", "icon": "map", "disabled": "true"},
 ]
```

`src/main.py`

```diff
@@
 from src.ui.pages import topology  # noqa: F401 — registers /topology page
 from src.ui.pages import inventory  # noqa: F401 — registers /inventory page
+from src.ui.pages import ipam  # noqa: F401 — registers /ipam page
 from src.ui.pages import device_edit  # noqa: F401 — registers /inventory/edit/{device_id} page
```

---

## 8. Security Boundaries

1. All IPAM API routes are gated with `Depends(require_role(Role.Reader))`.
2. The `/ipam` page is authenticated only; it does not call `redirect_if_insufficient_role()` because Reader access is intentional.
3. HT-024 is read-only end-to-end. No create/update/delete routes, no modal editors, no write-side JavaScript, no hidden edit controls.
4. Device navigation remains a plain redirect to the already-authenticated topology page. HT-024 does not widen access to any device data beyond what Reader already sees elsewhere.
5. Do not log search queries or per-cell tooltips. The feature does not need new structured logs.
6. MAC addresses are included in IPAM detail payloads because the story requires them in used/conflict tooltips. Keep them in response payloads only; do not echo them in notifications or logs.
7. Security remains double-gated:
   - UI exposes only read-only actions
   - API enforces Reader-authenticated access on both IPAM endpoints

---

## 9. Edge Cases

1. Empty state
   - No networks -> summary returns zeros and `items=[]`; `/ipam` renders an empty-state card instead of expansions.
   - Network exists but has no claims -> `used_ip_count=0`, `conflict_ip_count=0`, `device_claim_count=0`, and detail still renders free/gateway/reserved states correctly.
2. Boundary values
   - `/24` grid returns `256` cells with `254` usable addresses.
   - `/31` and `/32` grids emit no reserved addresses.
   - IPv4 broader than `/16` returns `render_mode="unsupported"` to avoid pathological block counts.
   - IPv6 returns `render_mode="unsupported"` with a stable reason string.
3. Concurrent access
   - No optimistic locking is needed because HT-024 introduces no writes.
   - Page-level cached detail can become stale if another user changes memberships; a full page refresh is the only refresh mechanism in HT-024.
4. Cascade effects
   - Existing delete behavior on `Network` and `DeviceNetwork` remains authoritative.
   - If a device or network disappears between summary load and detail click, the next detail or topology request will follow existing `404` behavior.
5. RBAC per operation
   - Reader: can load `/ipam`, list networks, expand detail, search visible networks, and navigate to topology.
   - Contributor/Admin: same read behavior, but HT-024 does not add any extra write affordances.
6. Round-trip integrity
   - No export/import changes are required. HT-024 adds no new persisted data, so `export_schema.py`, import validation, and export/import tests remain unchanged.
7. Canvas impact
   - No Cytoscape.js or Leaflet code changes are required.
   - HT-024 only reuses the existing `/topology?device_id={id}` focus behavior.
8. Performance at scale
   - Summary route remains compact because it returns counts only.
   - Grid detail is bounded at `256` cells.
   - Block-summary detail is bounded at `256` block cards.
   - Visible-network-only search avoids detail prefetch fan-out during typing.

---

## 10. Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `src/models/types.py` | Modify | Add `IpamAddressFamily`, `IpamRenderMode`, and `IpamCellStatus`. |
| `src/models/ipam.py` | Create | Define summary/detail IPAM response models. |
| `src/domain/ipam.py` | Create | Own pure IP allocation, status, and conflict logic. |
| `src/repositories/network_repository.py` | Modify | Add grouped membership batch lookup for summary aggregation. |
| `src/services/ipam_service.py` | Create | Orchestrate repository reads into IPAM response models. |
| `src/api/routers/ipam.py` | Create | Expose Reader-accessible IPAM endpoints. |
| `src/api/app.py` | Modify | Register the new IPAM router. |
| `src/ui/design/tokens.py` | Modify | Add IPAM semantic color tokens. |
| `src/ui/components/ipam_stats_row.py` | Create | Render aggregate header stats. |
| `src/ui/components/ipam_grid.py` | Create | Render clickable grid-mode cells. |
| `src/ui/components/ipam_block_summary.py` | Create | Render `/24` block summaries for large networks. |
| `src/ui/services/ipam_data.py` | Create | Fetch and validate summary/detail IPAM payloads. |
| `src/ui/services/ipam_search.py` | Create | Resolve visible-network search matches and scroll targets. |
| `src/ui/pages/ipam.py` | Create | Register the `/ipam` page and own page-level state. |
| `src/ui/components/sidebar.py` | Modify | Add `/ipam` to the primary navigation. |
| `src/main.py` | Modify | Import the new page module so NiceGUI registers `/ipam`. |
| `tests/unit/test_design_system.py` | Modify | Assert new IPAM theme tokens/CSS vars are present. |
| `tests/unit/test_app_shell.py` | Modify | Assert `/ipam` appears in `_NAV_ITEMS`. |
| `tests/unit/test_ipam_domain.py` | Create | Cover pure classification and roll-up rules. |
| `tests/unit/test_ipam_service.py` | Create | Cover summary aggregation and detail mapping behavior. |
| `tests/unit/test_ipam_search.py` | Create | Cover visible-network search matching for grid vs block-summary modes. |
| `tests/unit/test_ipam_page_execution.py` | Create | Cover page load, expansion, cached detail, search, and topology navigation wiring. |
| `tests/integration/test_ipam_api.py` | Create | Cover endpoint RBAC and payload correctness against the real API stack. |
| `CHANGELOG.md` | Modify | Add an `[Unreleased]` entry for HT-024 during implementation. |

### 10.1 Implementation order for Feature-Engineer

1. `src/models/types.py` and `src/models/ipam.py`
2. `src/domain/ipam.py`
3. `src/repositories/network_repository.py`
4. `src/services/ipam_service.py`
5. `src/api/routers/ipam.py` and `src/api/app.py`
6. `tests/unit/test_ipam_domain.py` and `tests/unit/test_ipam_service.py`
7. `src/ui/design/tokens.py`
8. `src/ui/services/ipam_data.py`, `src/ui/services/ipam_search.py`
9. `src/ui/components/ipam_stats_row.py`, `src/ui/components/ipam_grid.py`, `src/ui/components/ipam_block_summary.py`
10. `src/ui/pages/ipam.py`, `src/ui/components/sidebar.py`, `src/main.py`
11. `tests/unit/test_ipam_search.py`, `tests/unit/test_ipam_page_execution.py`, `tests/unit/test_app_shell.py`, `tests/unit/test_design_system.py`
12. `tests/integration/test_ipam_api.py`, `CHANGELOG.md`

---

## 11. Test Plan

### 11.1 Unit tests

`tests/unit/test_ipam_domain.py`

- `test_build_summary_classifies_grid_for_prefixlen_gte_24`
- `test_build_summary_classifies_block_summary_for_prefixlen_16_to_23`
- `test_build_summary_marks_ipv6_unsupported`
- `test_build_summary_marks_ipv4_broader_than_16_unsupported`
- `test_build_detail_emits_256_cells_for_24_with_reserved_endpoints`
- `test_build_detail_has_no_reserved_cells_for_31`
- `test_status_precedence_conflict_overrides_gateway_and_reserved`
- `test_used_ip_count_excludes_reserved_address_claims`
- `test_block_summary_uses_parent_network_reserved_rules_not_per_bucket_254`
- `test_allocations_are_sorted_by_ip_address`

`tests/unit/test_ipam_service.py`

- `test_list_networks_builds_page_stats_and_most_utilized_network`
- `test_list_networks_returns_none_for_most_utilized_when_all_networks_are_empty`
- `test_get_network_detail_returns_404_for_missing_network`
- `test_get_network_detail_includes_mac_in_device_claims`
- `test_get_network_detail_groups_duplicate_claims_into_one_conflict_allocation`

`tests/unit/test_ipam_search.py`

- `test_blank_query_returns_no_targets`
- `test_device_name_query_highlights_grid_cell_ids`
- `test_ipv4_query_highlights_block_id_for_block_summary_mode`
- `test_ipv4_query_highlights_allocation_when_address_is_claimed_in_block_summary_mode`
- `test_first_match_becomes_scroll_target_in_page_order`

`tests/unit/test_ipam_page_execution.py`

- Use the existing `FakeUI` + `AsyncClientStub` pattern already used by inventory/settings pages.
- Assert first page load calls only `/api/ipam/networks`.
- Assert first expansion triggers one detail request and second expansion reuses cached detail.
- Assert a used cell click navigates to `/topology?device_id={id}`.
- Assert a search term updates highlight state without issuing more HTTP requests.

`tests/unit/test_app_shell.py`

- Add one assertion: `"/ipam" in [item["route"] for item in _NAV_ITEMS]`.

`tests/unit/test_design_system.py`

- Add explicit assertions that:
  - every theme contains `ipam_used`, `ipam_free`, `ipam_gateway`, `ipam_conflict`, `ipam_reserved`
  - `build_css_var_dict("dark")` contains `--ht-ipam-used` and `--ht-ipam-conflict`

### 11.2 Integration tests

Create `tests/integration/test_ipam_api.py`.

Required cases:

1. `test_reader_can_list_ipam_networks`
2. `test_reader_can_get_ipam_detail_for_grid_network`
3. `test_reader_can_get_ipam_detail_for_block_summary_network`
4. `test_ipam_summary_reports_conflict_counts_for_duplicate_claims`
5. `test_ipam_detail_returns_conflict_cell_with_multiple_device_claims`
6. `test_ipam_detail_returns_unsupported_for_ipv6_network`
7. `test_missing_network_returns_404`
8. `test_unauthenticated_request_is_rejected_by_middleware`

Fixture usage:

- Reuse `client`, `session`, `contributor_token`, and `reader_token` from `tests/conftest.py`.
- No fixture or metadata registration changes are required because HT-024 introduces no new table model.

### 11.3 Verification sequence

During implementation, Feature-Engineer must run:

1. `docker compose exec api pytest tests/unit/test_ipam_domain.py tests/unit/test_ipam_service.py tests/unit/test_ipam_search.py tests/unit/test_ipam_page_execution.py tests/integration/test_ipam_api.py -v`
2. `docker compose exec api pytest`
3. `docker compose exec api mypy src/ --ignore-missing-imports`
4. `docker compose build`

No migration-safety review is needed because there is no Alembic file in this story.
