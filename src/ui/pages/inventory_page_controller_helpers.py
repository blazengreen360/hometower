"""Helper functions for inventory page controller behavior."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import httpx

from src.models.device import DeviceResponseEnriched

from src.ui.pages.inventory_bulk_actions import BulkActionOutcome
from src.utils.logger import logger
from src.utils.settings import settings


def resolve_selection_after_bulk(
    requested_ids: set[str],
    outcome: BulkActionOutcome,
) -> set[str]:
    """Return selection set to keep after a bulk action."""
    succeeded_ids = set(outcome.succeeded_ids)
    if outcome.aborted:
        return requested_ids.difference(succeeded_ids)
    if not outcome.failed and not outcome.skipped:
        return set()
    keep_ids = {failure.device_id for failure in outcome.failed}
    keep_ids.update(skip.device_id for skip in outcome.skipped)
    return keep_ids


def relative_time(dt: datetime) -> str:
    """Format datetimes as compact relative labels for inventory rows."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = int((datetime.now(timezone.utc) - dt).total_seconds())
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    return f"{diff // 86400}d ago"


def _inventory_query_params(workspace_id: str | None) -> dict[str, str]:
    params = {"include": "location,tags,services,networks", "limit": "1000"}
    if workspace_id:
        params["workspace_id"] = workspace_id
    return params


async def load_inventory_devices(
    token: str,
    workspace_id: str | None,
) -> list[DeviceResponseEnriched]:
    """Load enriched inventory devices for the page controller."""
    try:
        async with httpx.AsyncClient() as http:
            response = await http.get(
                f"{settings.api_base_url}/api/devices/",
                params=_inventory_query_params(workspace_id),
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
    except Exception as exc:
        logger.error("Inventory load error: {}", str(exc))
        return []

    if response.status_code != 200:
        logger.error("Inventory load failed: status={}", response.status_code)
        return []

    return [
        DeviceResponseEnriched.model_validate(item)
        for item in response.json().get("items", [])
    ]


async def load_inventory_placement_data(
    token: str,
    device_ids: set[uuid.UUID],
    workspace_id: str | None,
) -> tuple[set[str], dict[str, int]]:
    """Return orphan IDs and placement counts for the inventory table."""
    all_ids = {str(device_id) for device_id in device_ids}
    try:
        async with httpx.AsyncClient() as http:
            response = await http.get(
                f"{settings.api_base_url}/api/devices/placed-ids",
                params={"workspace_id": workspace_id} if workspace_id else None,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
    except Exception as exc:
        logger.error("Orphan data load error: {}", str(exc))
        return set(), {}

    if response.status_code != 200:
        logger.error("Orphan data load failed: status={}", response.status_code)
        return set(), {}

    placed_ids = set(response.json())
    orphan_ids = all_ids.difference(placed_ids)
    placement_counts = {device_id: (1 if device_id in placed_ids else 0) for device_id in all_ids}
    return orphan_ids, placement_counts
