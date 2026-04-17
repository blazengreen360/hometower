"""Data helpers for the /map page (HT-008)."""

from __future__ import annotations

import asyncio
from typing import TypedDict

import httpx
from nicegui import app as nicegui_app

from src.utils.logger import logger
from src.utils.settings import settings

_MAP_API_URL = f"{settings.api_base_url}/api/locations/"
_POWER_SUMMARY_API_URL = f"{settings.api_base_url}/api/power/summary"


class MapDevice(TypedDict):
    id: str
    name: str
    type: str
    status: str


class MapLocation(TypedDict):
    id: str
    name: str
    lat: float
    lng: float
    device_count: int
    devices: list[MapDevice]
    power_total_watts: int
    power_device_count: int


def _auth_headers() -> dict[str, str]:
    token = nicegui_app.storage.user.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _parse_geo_locations(raw: object) -> list[MapLocation]:
    if not isinstance(raw, list):
        return []

    locations: list[MapLocation] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        raw_name = item.get("name")
        raw_id = item.get("id")
        raw_lat = item.get("lat")
        raw_lng = item.get("lng")
        if not isinstance(raw_name, str):
            continue
        if not isinstance(raw_lat, (int, float)) or not isinstance(raw_lng, (int, float)):
            continue

        raw_devices = item.get("devices")
        devices: list[MapDevice] = []
        if isinstance(raw_devices, list):
            for device in raw_devices:
                if not isinstance(device, dict):
                    continue
                device_id = device.get("id")
                device_name = device.get("name")
                device_type = device.get("type")
                device_status = device.get("status")
                if not isinstance(device_name, str):
                    continue
                devices.append(
                    {
                        "id": str(device_id),
                        "name": device_name,
                        "type": str(device_type),
                        "status": str(device_status),
                    }
                )

        raw_count = item.get("device_count")
        count = int(raw_count) if isinstance(raw_count, int) else len(devices)

        locations.append(
            {
                "id": str(raw_id),
                "name": raw_name,
                "lat": float(raw_lat),
                "lng": float(raw_lng),
                "device_count": count,
                "devices": devices,
                "power_total_watts": 0,
                "power_device_count": 0,
            }
        )

    return locations


def _parse_power_by_location(raw: object) -> dict[str, tuple[int, int]]:
    if not isinstance(raw, dict):
        return {}

    by_location = raw.get("by_location")
    if not isinstance(by_location, list):
        return {}

    merged: dict[str, tuple[int, int]] = {}
    for item in by_location:
        if not isinstance(item, dict):
            continue

        location_id = item.get("location_id")
        total_watts = item.get("total_watts")
        device_count = item.get("device_count")

        if location_id is None:
            continue

        watts = int(total_watts) if isinstance(total_watts, int) else 0
        count = int(device_count) if isinstance(device_count, int) else 0
        merged[str(location_id)] = (max(0, watts), max(0, count))

    return merged


async def load_geo_locations() -> list[MapLocation]:
    """Fetch geo locations with embedded devices for the map view."""
    try:
        async with httpx.AsyncClient() as client:
            locations_result, power_result = await asyncio.gather(
                client.get(
                    _MAP_API_URL,
                    params={"type": "geo", "include": "devices"},
                    headers=_auth_headers(),
                    timeout=8.0,
                ),
                client.get(
                    _POWER_SUMMARY_API_URL,
                    headers=_auth_headers(),
                    timeout=8.0,
                ),
                return_exceptions=True,
            )

        if not isinstance(locations_result, httpx.Response):
            logger.error("Map page failed to fetch locations: {}", locations_result)
            return []

        if locations_result.status_code != 200:
            logger.warning(
                "Map page locations request failed with status={}",
                locations_result.status_code,
            )
            return []

        locations = _parse_geo_locations(locations_result.json())

        power_by_location: dict[str, tuple[int, int]] = {}
        if not isinstance(power_result, httpx.Response):
            logger.warning("Map page failed to fetch power summary: {}", power_result)
        elif power_result.status_code != 200:
            logger.warning(
                "Map page power summary request failed with status={}",
                power_result.status_code,
            )
        else:
            power_by_location = _parse_power_by_location(power_result.json())

        for location in locations:
            watts, count = power_by_location.get(location["id"], (0, 0))
            location["power_total_watts"] = watts
            location["power_device_count"] = count

        return locations
    except httpx.HTTPError as exc:
        logger.error("Map page request failed: {}", exc)
        return []