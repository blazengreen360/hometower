"""Inventory bulk action handlers for the inventory page controller."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol
import uuid

from src.models.device import DeviceResponseEnriched
from src.models.location import LocationResponse
from src.models.tag import TagResponse
from src.ui.components.toast import show_toast
from src.ui.design.tokens import COLOR_TEXT_MUTED
from src.ui.pages.inventory_bulk_actions import (
    BulkActionOutcome,
    BulkProgress,
    add_tag_to_devices,
    delete_devices_with_connection_preflight,
    list_locations,
    remove_tag_from_devices,
    set_location_for_devices,
)


class BulkState(Protocol):
    """State contract required by inventory bulk handlers."""

    all_devices: list[DeviceResponseEnriched]
    all_tags: list[dict[str, object]]
    locations: list[LocationResponse] | None
    orphan_ids: set[str]
    placement_counts: dict[str, int]


RunBulk = Callable[..., Awaitable[tuple[BulkActionOutcome, int] | None]]


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


class InventoryBulkHandlers:
    """Typed handlers that run HT-031 bulk operations and emit toast feedback."""

    def __init__(
        self,
        *,
        state: BulkState,
        token: str,
        run_bulk: RunBulk,
        on_progress: Callable[[BulkProgress], None],
    ) -> None:
        self._state = state
        self._token = token
        self._run_bulk = run_bulk
        self._on_progress = on_progress

    def _tag_response(self, tag_id: uuid.UUID) -> TagResponse | None:
        for tag in self._state.all_tags:
            if str(tag.get("id", "")) == str(tag_id):
                return TagResponse(
                    id=tag_id,
                    name=str(tag.get("name", "")),
                    color=str(tag.get("color", COLOR_TEXT_MUTED)),
                    created_at=_parse_datetime(tag.get("created_at")),
                )
        return None

    @staticmethod
    def _notify_network_abort(title: str, succeeded: int, total: int) -> None:
        show_toast(
            type="error",
            title=title,
            description=f"{succeeded} of {total} completed before the connection failed",
        )

    async def add_tag(self, tag_id_raw: str) -> None:
        tag_id = _parse_uuid(tag_id_raw)
        if tag_id is None:
            return
        tag_ref = self._tag_response(tag_id)

        async def _runner(
            devices: list[DeviceResponseEnriched],
            on_settled: Callable[[BulkActionOutcome], None],
        ) -> BulkActionOutcome:
            return await add_tag_to_devices(
                devices,
                tag_id,
                self._token,
                self._on_progress,
                on_settled,
            )

        def _on_success(outcome: BulkActionOutcome) -> None:
            if tag_ref is None:
                return
            for device in self._state.all_devices:
                if str(device.id) in outcome.succeeded_ids and all(t.id != tag_id for t in device.tags):
                    device.tags.append(tag_ref)

        result = await self._run_bulk(action="Adding", runner=_runner, on_success=_on_success)
        if result is None:
            return

        outcome, total = result
        succeeded = len(outcome.succeeded_ids)
        tag_name = tag_ref.name if tag_ref is not None else "selected tag"
        if outcome.aborted:
            self._notify_network_abort("Bulk add tag stopped after a network error", succeeded, total)
        elif not outcome.failed:
            show_toast(type="success", title=f"Tag '{tag_name}' added to {succeeded} devices")
        else:
            show_toast(
                type="warning",
                title=f"Tag '{tag_name}' added to {succeeded} of {total} devices",
                description=f"{len(outcome.failed)} failed. Selection kept for review.",
            )

    async def remove_tag(self, tag_id_raw: str) -> None:
        tag_id = _parse_uuid(tag_id_raw)
        if tag_id is None:
            return
        tag_ref = self._tag_response(tag_id)

        async def _runner(
            devices: list[DeviceResponseEnriched],
            on_settled: Callable[[BulkActionOutcome], None],
        ) -> BulkActionOutcome:
            return await remove_tag_from_devices(
                devices,
                tag_id,
                self._token,
                self._on_progress,
                on_settled,
            )

        def _on_success(outcome: BulkActionOutcome) -> None:
            for device in self._state.all_devices:
                if str(device.id) in outcome.succeeded_ids:
                    device.tags = [tag for tag in device.tags if tag.id != tag_id]

        result = await self._run_bulk(action="Removing", runner=_runner, on_success=_on_success)
        if result is None:
            return

        outcome, total = result
        succeeded = len(outcome.succeeded_ids)
        tag_name = tag_ref.name if tag_ref is not None else "selected tag"
        if outcome.aborted:
            self._notify_network_abort("Bulk remove tag stopped after a network error", succeeded, total)
        elif not outcome.failed:
            show_toast(type="success", title=f"Tag '{tag_name}' removed from {succeeded} devices")
        else:
            show_toast(
                type="warning",
                title=f"Tag '{tag_name}' removed from {succeeded} of {total} devices",
                description=f"{len(outcome.failed)} failed. Selection kept for review.",
            )

    async def set_location(self, location_id_raw: str) -> None:
        location_id = _parse_uuid(location_id_raw)
        if location_id is None:
            return
        if self._state.locations is None:
            self._state.locations = await list_locations(self._token)
        location_names = {
            str(location.id): location.name
            for location in (self._state.locations or [])
        }

        async def _runner(
            devices: list[DeviceResponseEnriched],
            on_settled: Callable[[BulkActionOutcome], None],
        ) -> BulkActionOutcome:
            return await set_location_for_devices(
                devices,
                location_id,
                self._token,
                self._on_progress,
                on_settled,
            )

        def _on_success(outcome: BulkActionOutcome) -> None:
            for device in self._state.all_devices:
                updated = outcome.updated_devices.get(str(device.id))
                if updated is None:
                    continue
                device.location_id = updated.location_id
                device.location_name = location_names.get(str(location_id), "")
                device.version = updated.version
                device.updated_at = updated.updated_at

        result = await self._run_bulk(action="Moving", runner=_runner, on_success=_on_success)
        if result is None:
            return

        outcome, total = result
        succeeded = len(outcome.succeeded_ids)
        location_name = location_names.get(str(location_id), "location")
        if outcome.aborted:
            self._notify_network_abort("Bulk location update stopped after a network error", succeeded, total)
        elif not outcome.failed:
            show_toast(type="success", title=f"Moved {succeeded} devices to {location_name}")
        else:
            show_toast(
                type="warning",
                title=f"Moved {succeeded} of {total} devices to {location_name}",
                description=f"{len(outcome.failed)} failed. Selection kept for review.",
            )

    async def delete_selected(self) -> None:
        async def _runner(
            devices: list[DeviceResponseEnriched],
            on_settled: Callable[[BulkActionOutcome], None],
        ) -> BulkActionOutcome:
            return await delete_devices_with_connection_preflight(
                devices,
                self._token,
                self._on_progress,
                on_settled,
            )

        def _on_success(outcome: BulkActionOutcome) -> None:
            succeeded = set(outcome.succeeded_ids)
            if not succeeded:
                return
            self._state.all_devices = [d for d in self._state.all_devices if str(d.id) not in succeeded]
            self._state.orphan_ids.difference_update(succeeded)
            for device_id in succeeded:
                self._state.placement_counts.pop(device_id, None)

        result = await self._run_bulk(action="Deleting", runner=_runner, on_success=_on_success)
        if result is None:
            return

        outcome, total = result
        succeeded = len(outcome.succeeded_ids)
        skipped = len(outcome.skipped)
        failed = len(outcome.failed)
        if outcome.aborted:
            self._notify_network_abort("Bulk delete stopped after a network error", succeeded, total)
            return
        if skipped == 0 and failed == 0:
            show_toast(type="success", title=f"Deleted {succeeded} devices")
            return

        parts: list[str] = []
        if skipped:
            parts.append(f"{skipped} skipped: have active connections")
        if failed:
            parts.append(f"{failed} failed")
        show_toast(
            type="warning",
            title=f"Deleted {succeeded} of {total} devices",
            description=". ".join(parts) + ". Selection kept for review.",
        )
