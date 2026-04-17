"""Helper functions for inventory page controller behavior."""
from __future__ import annotations

from datetime import datetime, timezone

from src.ui.pages.inventory_bulk_actions import BulkActionOutcome


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
