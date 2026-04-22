"""Support helpers for connection detail panel network updates."""

import httpx

from src.utils.logger import logger
from src.utils.settings import settings

_ROLES_WITH_EDIT = {"Admin", "Contributor"}


def can_edit_connection(user_role: str) -> bool:
    """Return whether the role can perform connection write actions."""
    return user_role in _ROLES_WITH_EDIT


async def patch_connection(
    token: str,
    conn_id: str,
    payload: dict[str, object],
) -> bool:
    """Persist connection edits through the API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{settings.api_base_url}/api/connections/{conn_id}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        return response.status_code == 200
    except httpx.HTTPError as exc:
        logger.error("Connection PATCH: {}", str(exc))
        return False