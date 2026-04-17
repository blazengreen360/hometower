"""HTTP data loaders for the /ipam page (HT-024)."""
from __future__ import annotations

import httpx

from src.models.ipam import (
    IpamNetworkDetailResponse,
    IpamNetworkListResponse,
    IpamPageStatsResponse,
)
from src.utils.logger import logger
from src.utils.settings import settings


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def load_ipam_summary(token: str) -> IpamNetworkListResponse:
    """Load the summary payload for all networks."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.api_base_url}/api/ipam/networks",
                headers=_auth_headers(token),
                timeout=10.0,
            )
        if response.status_code == 200:
            return IpamNetworkListResponse.model_validate(response.json())
        logger.warning("IPAM summary load failed: status={}", response.status_code)
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("IPAM summary load error: {}", str(exc))

    return IpamNetworkListResponse(
        summary=IpamPageStatsResponse(
            total_networks=0,
            visualizable_networks=0,
            total_assigned_ips=0,
            total_conflicts=0,
            most_utilized_network=None,
        ),
        items=[],
    )


async def load_ipam_detail(token: str, network_id: str) -> IpamNetworkDetailResponse | None:
    """Load detailed IPAM payload for one network."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.api_base_url}/api/ipam/networks/{network_id}",
                headers=_auth_headers(token),
                timeout=10.0,
            )
        if response.status_code == 200:
            return IpamNetworkDetailResponse.model_validate(response.json())
        logger.warning(
            "IPAM detail load failed: network_id={} status={}",
            network_id,
            response.status_code,
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("IPAM detail load error: network_id={} error={}", network_id, str(exc))

    return None
