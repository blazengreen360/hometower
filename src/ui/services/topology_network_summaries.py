"""Network summary loading for topology sidebar filtering."""

import httpx

from src.ui.services.topology_data_helpers import _safe_text
from src.utils.logger import logger
from src.utils.settings import settings


async def load_network_summaries(token: str) -> list[dict[str, object]]:
    """Fetch network summaries for topology sidebar filtering."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.api_base_url}/api/networks/",
                headers=headers,
                timeout=5.0,
            )
        if resp.status_code != 200:
            logger.warning(
                "Topology networks load failed: status={status}",
                status=resp.status_code,
            )
            return []
        raw_items = resp.json()
        if not isinstance(raw_items, list):
            return []

        items: list[dict[str, object]] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            items.append(
                {
                    "id": str(raw.get("id", "")),
                    "name": _safe_text(raw.get("name", "")),
                    "vlan_id": raw.get("vlan_id"),
                    "cidr": _safe_text(raw.get("cidr", "")),
                    "color": _safe_text(raw.get("color", "")),
                    "device_count": int(raw.get("device_count", 0) or 0),
                }
            )
        return items
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
        logger.warning("Topology networks load error: {error}", error=str(exc))
        return []
