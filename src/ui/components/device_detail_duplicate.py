"""Device duplication helper — client-orchestrated clone operation (HT-041).

All API calls go through httpx. Called from device_detail_panel when the
Duplicate button is clicked.
"""
import uuid
from typing import Optional

import httpx

from src.domain.devices import generate_copy_name
from src.models.device import DeviceResponseEnriched
from src.ui.components.toast import show_toast
from src.utils.logger import logger
from src.utils.settings import settings


async def _fetch_all_device_names(base: str, headers: dict[str, str]) -> list[str]:
    """Fetch all device names across pages for copy-name collision detection."""
    existing_names: list[str] = []
    page = 1
    try:
        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    f"{base}/api/devices/",
                    params={"limit": 1000, "page": page},
                    headers=headers,
                    timeout=10.0,
                )
                if response.status_code != 200:
                    break
                payload = response.json()
                raw_items = payload.get("items", [])
                if not isinstance(raw_items, list):
                    break
                items = [i for i in raw_items if isinstance(i, dict)]
                existing_names.extend(
                    name
                    for item in items
                    if isinstance(name := item.get("name"), str)
                )
                total = payload.get("total")
                if len(items) == 0:
                    break
                if isinstance(total, int) and len(existing_names) >= total:
                    break
                page += 1
    except httpx.HTTPError as exc:
        logger.warning("Duplicate: could not fetch device names: {}", str(exc))
    return existing_names


async def duplicate_device(
    token: str,
    device: DeviceResponseEnriched,
) -> Optional[uuid.UUID]:
    """Clone *device* via the API and return the new device's UUID, or None on failure.

    Steps:
      1. Fetch all device names to calculate the copy name.
      2. POST the new device (ip/mac cleared, other fields copied).
      3. Copy all tags to the new device.
      4. Copy all custom fields to the new device.
    """
    headers = {"Authorization": f"Bearer {token}"}
    base = settings.api_base_url

    # 1. Fetch all device names for copy-name collision detection
    existing_names = await _fetch_all_device_names(base, headers)

    # 2. Generate unique copy name
    copy_name = generate_copy_name(device.name, existing_names)

    # 3. POST new device (ip/mac deliberately excluded → null)
    payload: dict = {
        "name": copy_name,
        "type": device.type.value,
        "status": device.status.value,
        "os": device.os,
        "notes": device.notes,
        "power_watts": device.power_watts,
        "location_id": str(device.location_id) if device.location_id else None,
    }
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{base}/api/devices/",
                json=payload,
                headers=headers,
                timeout=5.0,
            )
        if r.status_code != 201:
            logger.warning("Duplicate device POST failed: status={}", r.status_code)
            show_toast(type="error", title="Duplication failed", description=r.text[:120])
            return None
        new_id = uuid.UUID(r.json()["id"])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.error("Duplicate device error: {}", str(exc))
        show_toast(type="error", title="Duplication failed")
        return None

    # 4. Copy tags (best-effort; individual failures are logged but not fatal)
    for tag in device.tags:
        try:
            async with httpx.AsyncClient() as c:
                await c.post(
                    f"{base}/api/devices/{new_id}/tags",
                    json={"tag_id": str(tag.id)},
                    headers=headers,
                    timeout=5.0,
                )
        except httpx.HTTPError as exc:
            logger.warning("Duplicate: tag copy failed tag_id={}: {}", tag.id, str(exc))

    # 5. Copy custom fields (best-effort)
    for cf in device.custom_fields:
        try:
            async with httpx.AsyncClient() as c:
                await c.post(
                    f"{base}/api/devices/{new_id}/custom-fields",
                    json={"key": cf.key, "value": cf.value},
                    headers=headers,
                    timeout=5.0,
                )
        except httpx.HTTPError as exc:
            logger.warning("Duplicate: CF copy failed key={}: {}", cf.key, str(exc))

    show_toast(type="success", title=f"Device duplicated: {copy_name}")
    return new_id
