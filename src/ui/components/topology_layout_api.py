"""API helpers for topology history management."""
from typing import Callable

import httpx

from src.utils.logger import logger
from src.utils.settings import settings


async def get_layouts(
    token: str,
    client_factory: Callable[[], httpx.AsyncClient],
    topology_id: str = "",
) -> list[dict[str, object]]:
    """Fetch topology history summaries (legacy name kept for compatibility)."""
    if not topology_id:
        return []
    try:
        params: dict[str, int] = {"limit": 100}
        async with client_factory() as client:
            response = await client.get(
                f"{settings.api_base_url}/api/topologies/{topology_id}/history",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        if response.status_code == 200:
            items: list[dict[str, object]] = response.json().get("items", [])
            return items
    except httpx.HTTPError as exc:
        logger.error("Layout list fetch: {}", str(exc))
    return []
