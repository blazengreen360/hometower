"""Support helpers for the dedicated inventory device editor page."""
import uuid

import httpx

from src.models.device import DeviceResponseEnriched
from src.utils.logger import logger
from src.utils.settings import settings


def clean_optional(value: str | None) -> str | None:
    """Return stripped text or None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def clean_optional_int(value: str | None) -> int | str | None:
    """Return a non-negative int, None, or the invalid raw value."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = int(stripped)
    except ValueError:
        return stripped
    if parsed < 0:
        return stripped
    return parsed


def extract_error_detail(resp: httpx.Response) -> str:
    """Return a friendly validation message from an API response."""
    try:
        payload = resp.json()
    except Exception:
        return f"Save failed ({resp.status_code})"

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            msg = first.get("msg")
            if isinstance(msg, str):
                return msg
    return f"Save failed ({resp.status_code})"


async def load_device(token: str, device_id: uuid.UUID) -> DeviceResponseEnriched | None:
    """Load a device for the dedicated inventory editor page."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.api_base_url}/api/devices/{device_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8.0,
            )
    except httpx.HTTPError as exc:
        logger.error("Inventory editor load failed: {}", str(exc))
        return None

    if resp.status_code != 200:
        logger.warning("Inventory editor load status={} id={}", resp.status_code, str(device_id))
        return None

    try:
        return DeviceResponseEnriched.model_validate(resp.json())
    except Exception as exc:
        logger.error("Inventory editor parse failed: {}", str(exc))
        return None
