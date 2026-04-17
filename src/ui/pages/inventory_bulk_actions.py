"""Inventory bulk action HTTP orchestration helpers (HT-031)."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import uuid

import httpx

from src.models.device import DeviceResponse, DeviceResponseEnriched
from src.models.location import LocationResponse
from src.utils.settings import settings


@dataclass(frozen=True)
class BulkFailure:
    """A per-device failure or skip entry from a bulk action."""

    device_id: str
    device_name: str
    detail: str


@dataclass(frozen=True)
class BulkProgress:
    """Bulk action progress snapshot."""

    completed: int
    total: int


@dataclass(frozen=True)
class BulkActionOutcome:
    """Normalized result shape for all inventory bulk actions."""

    succeeded_ids: list[str] = field(default_factory=list)
    updated_devices: dict[str, DeviceResponse] = field(default_factory=dict)
    failed: list[BulkFailure] = field(default_factory=list)
    skipped: list[BulkFailure] = field(default_factory=list)
    aborted: bool = False
    abort_detail: str | None = None


ProgressCallback = Callable[[BulkProgress], None]
SettledCallback = Callable[[BulkActionOutcome], None]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _detail_from_response(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return f"Request failed ({response.status_code})"

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                msg = first.get("msg")
                if isinstance(msg, str):
                    return msg
    return f"Request failed ({response.status_code})"


def _failure(device: DeviceResponseEnriched, detail: str) -> BulkFailure:
    return BulkFailure(device_id=str(device.id), device_name=device.name, detail=detail)


def _progress(on_progress: ProgressCallback, *, completed: int, total: int) -> None:
    on_progress(BulkProgress(completed=completed, total=total))


def _settled(on_settled: SettledCallback | None, outcome: BulkActionOutcome) -> None:
    if on_settled is not None:
        on_settled(outcome)


def _network_abort(
    *,
    succeeded_ids: list[str],
    updated_devices: dict[str, DeviceResponse] | None = None,
    failed: list[BulkFailure] | None = None,
    skipped: list[BulkFailure] | None = None,
    exc: Exception,
) -> BulkActionOutcome:
    return BulkActionOutcome(
        succeeded_ids=succeeded_ids,
        updated_devices=updated_devices or {},
        failed=failed or [],
        skipped=skipped or [],
        aborted=True,
        abort_detail=str(exc),
    )


async def list_locations(token: str) -> list[LocationResponse]:
    """Fetch available locations for bulk set-location options."""
    try:
        async with httpx.AsyncClient() as http:
            response = await http.get(
                f"{settings.api_base_url}/api/locations/",
                headers=_headers(token),
                timeout=10.0,
            )
    except httpx.HTTPError:
        return []

    if response.status_code != 200:
        return []

    payload = response.json()
    if not isinstance(payload, list):
        return []
    return [LocationResponse.model_validate(item) for item in payload]


async def add_tag_to_devices(
    devices: Sequence[DeviceResponseEnriched],
    tag_id: uuid.UUID,
    token: str,
    on_progress: ProgressCallback,
    on_settled: SettledCallback | None = None,
) -> BulkActionOutcome:
    """Attach one tag to each selected device using existing single-device endpoint."""
    total = len(devices)
    completed = 0
    succeeded_ids: list[str] = []
    failed: list[BulkFailure] = []

    try:
        async with httpx.AsyncClient() as http:
            for device in devices:
                response = await http.post(
                    f"{settings.api_base_url}/api/devices/{device.id}/tags",
                    json={"tag_id": str(tag_id)},
                    headers=_headers(token),
                    timeout=10.0,
                )
                if response.status_code in {200, 201, 204}:
                    device_id = str(device.id)
                    succeeded_ids.append(device_id)
                    _settled(on_settled, BulkActionOutcome(succeeded_ids=[device_id]))
                else:
                    failure = _failure(device, _detail_from_response(response))
                    failed.append(failure)
                    _settled(on_settled, BulkActionOutcome(failed=[failure]))
                completed += 1
                _progress(on_progress, completed=completed, total=total)
    except httpx.HTTPError as exc:
        return _network_abort(succeeded_ids=succeeded_ids, failed=failed, exc=exc)

    return BulkActionOutcome(succeeded_ids=succeeded_ids, failed=failed)


async def remove_tag_from_devices(
    devices: Sequence[DeviceResponseEnriched],
    tag_id: uuid.UUID,
    token: str,
    on_progress: ProgressCallback,
    on_settled: SettledCallback | None = None,
) -> BulkActionOutcome:
    """Detach one tag from each selected device using existing single-device endpoint."""
    total = len(devices)
    completed = 0
    succeeded_ids: list[str] = []
    failed: list[BulkFailure] = []

    try:
        async with httpx.AsyncClient() as http:
            for device in devices:
                response = await http.delete(
                    f"{settings.api_base_url}/api/devices/{device.id}/tags/{tag_id}",
                    headers=_headers(token),
                    timeout=10.0,
                )
                if response.status_code in {200, 204}:
                    device_id = str(device.id)
                    succeeded_ids.append(device_id)
                    _settled(on_settled, BulkActionOutcome(succeeded_ids=[device_id]))
                else:
                    failure = _failure(device, _detail_from_response(response))
                    failed.append(failure)
                    _settled(on_settled, BulkActionOutcome(failed=[failure]))
                completed += 1
                _progress(on_progress, completed=completed, total=total)
    except httpx.HTTPError as exc:
        return _network_abort(succeeded_ids=succeeded_ids, failed=failed, exc=exc)

    return BulkActionOutcome(succeeded_ids=succeeded_ids, failed=failed)


async def set_location_for_devices(
    devices: Sequence[DeviceResponseEnriched],
    location_id: uuid.UUID,
    token: str,
    on_progress: ProgressCallback,
    on_settled: SettledCallback | None = None,
) -> BulkActionOutcome:
    """Assign one location to each selected device via existing PATCH endpoint."""
    total = len(devices)
    completed = 0
    succeeded_ids: list[str] = []
    updated_devices: dict[str, DeviceResponse] = {}
    failed: list[BulkFailure] = []

    try:
        async with httpx.AsyncClient() as http:
            for device in devices:
                response = await http.patch(
                    f"{settings.api_base_url}/api/devices/{device.id}",
                    json={"location_id": str(location_id), "version": int(device.version)},
                    headers=_headers(token),
                    timeout=10.0,
                )
                if response.status_code == 200:
                    updated = DeviceResponse.model_validate(response.json())
                    device_id = str(device.id)
                    succeeded_ids.append(device_id)
                    updated_devices[device_id] = updated
                    _settled(
                        on_settled,
                        BulkActionOutcome(
                            succeeded_ids=[device_id],
                            updated_devices={device_id: updated},
                        ),
                    )
                else:
                    failure = _failure(device, _detail_from_response(response))
                    failed.append(failure)
                    _settled(on_settled, BulkActionOutcome(failed=[failure]))
                completed += 1
                _progress(on_progress, completed=completed, total=total)
    except httpx.HTTPError as exc:
        return _network_abort(
            succeeded_ids=succeeded_ids,
            updated_devices=updated_devices,
            failed=failed,
            exc=exc,
        )

    return BulkActionOutcome(
        succeeded_ids=succeeded_ids,
        updated_devices=updated_devices,
        failed=failed,
    )


async def delete_devices_with_connection_preflight(
    devices: Sequence[DeviceResponseEnriched],
    token: str,
    on_progress: ProgressCallback,
    on_settled: SettledCallback | None = None,
) -> BulkActionOutcome:
    """Delete selected devices while skipping devices that currently have connections."""
    total = len(devices)
    completed = 0
    succeeded_ids: list[str] = []
    failed: list[BulkFailure] = []
    skipped: list[BulkFailure] = []

    try:
        async with httpx.AsyncClient() as http:
            for device in devices:
                preflight = await http.get(
                    f"{settings.api_base_url}/api/devices/{device.id}/connections",
                    headers=_headers(token),
                    timeout=10.0,
                )
                if preflight.status_code != 200:
                    failure = _failure(device, _detail_from_response(preflight))
                    failed.append(failure)
                    _settled(on_settled, BulkActionOutcome(failed=[failure]))
                    completed += 1
                    _progress(on_progress, completed=completed, total=total)
                    continue

                payload = preflight.json()
                if isinstance(payload, list) and payload:
                    skipped_item = _failure(device, "have active connections")
                    skipped.append(skipped_item)
                    _settled(on_settled, BulkActionOutcome(skipped=[skipped_item]))
                    completed += 1
                    _progress(on_progress, completed=completed, total=total)
                    continue

                response = await http.delete(
                    f"{settings.api_base_url}/api/devices/{device.id}",
                    headers=_headers(token),
                    timeout=10.0,
                )
                if response.status_code == 204:
                    device_id = str(device.id)
                    succeeded_ids.append(device_id)
                    _settled(on_settled, BulkActionOutcome(succeeded_ids=[device_id]))
                else:
                    failure = _failure(device, _detail_from_response(response))
                    failed.append(failure)
                    _settled(on_settled, BulkActionOutcome(failed=[failure]))
                completed += 1
                _progress(on_progress, completed=completed, total=total)
    except httpx.HTTPError as exc:
        return _network_abort(
            succeeded_ids=succeeded_ids,
            failed=failed,
            skipped=skipped,
            exc=exc,
        )

    return BulkActionOutcome(
        succeeded_ids=succeeded_ids,
        failed=failed,
        skipped=skipped,
    )
