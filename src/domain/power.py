"""Power domain logic — pure functions, no I/O (HT-044)."""
import uuid
from typing import TypedDict


class PowerDeviceSnapshot(TypedDict):
    location_id: uuid.UUID | None
    power_watts: int | None


class PowerLocationSnapshot(TypedDict):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None


class PowerLocationRollup(TypedDict):
    location_id: uuid.UUID
    location_name: str
    parent_location_id: uuid.UUID | None
    total_watts: int
    device_count: int
    estimated_monthly_cost: float | None


def validate_cost_settings(
    cost_per_kwh: float | None,
    currency: str | None,
) -> tuple[float | None, str | None]:
    """Validate the pair invariant for power cost settings."""
    if cost_per_kwh is None and currency is None:
        return None, None
    if cost_per_kwh is None or currency is None:
        raise ValueError("cost_per_kwh and currency must be provided together")
    return cost_per_kwh, currency


def estimate_monthly_kwh(total_watts: int) -> float:
    """Estimate monthly kWh from watts using the HT-044 formula."""
    if total_watts < 0:
        raise ValueError("total_watts must be non-negative")
    return round(total_watts * 24 * 30.44 / 1000, 2)


def estimate_monthly_cost(
    total_watts: int,
    cost_per_kwh: float | None,
) -> float | None:
    """Estimate monthly energy cost from watts and configured rate."""
    if cost_per_kwh is None:
        return None
    if cost_per_kwh < 0:
        raise ValueError("cost_per_kwh must be non-negative")
    return round(estimate_monthly_kwh(total_watts) * cost_per_kwh, 2)


def build_recursive_location_rollups(
    devices: list[PowerDeviceSnapshot],
    locations: list[PowerLocationSnapshot],
    cost_per_kwh: float | None,
) -> list[PowerLocationRollup]:
    """Build recursive location totals with descendant rollups and cycle guards."""
    location_by_id: dict[uuid.UUID, PowerLocationSnapshot] = {
        location["id"]: location for location in locations
    }

    children_by_parent: dict[uuid.UUID, list[uuid.UUID]] = {}
    for location in locations:
        parent_id = location["parent_id"]
        if parent_id is None:
            continue
        if parent_id not in location_by_id:
            continue
        children_by_parent.setdefault(parent_id, []).append(location["id"])

    direct_watts: dict[uuid.UUID, int] = {location_id: 0 for location_id in location_by_id}
    direct_known_devices: dict[uuid.UUID, int] = {
        location_id: 0 for location_id in location_by_id
    }

    for device in devices:
        location_id = device["location_id"]
        if location_id is None or location_id not in location_by_id:
            continue

        power_watts = device["power_watts"]
        if power_watts is None:
            continue

        direct_watts[location_id] += power_watts
        direct_known_devices[location_id] += 1

    memo: dict[uuid.UUID, tuple[int, int]] = {}

    def aggregate(
        location_id: uuid.UUID,
        visiting: set[uuid.UUID],
    ) -> tuple[int, int, bool]:
        if location_id in memo:
            cached_watts, cached_count = memo[location_id]
            return cached_watts, cached_count, False

        # Guard against corrupt cycles in persisted location hierarchies.
        if location_id in visiting:
            return 0, 0, True

        visiting.add(location_id)
        total_watts = direct_watts[location_id]
        device_count = direct_known_devices[location_id]
        cycle_detected = False

        for child_id in children_by_parent.get(location_id, []):
            child_watts, child_count, child_cycle_detected = aggregate(
                child_id,
                visiting,
            )
            total_watts += child_watts
            device_count += child_count
            cycle_detected = cycle_detected or child_cycle_detected

        visiting.remove(location_id)

        # Cache only acyclic branches so later traversals are not path-dependent.
        if not cycle_detected:
            memo[location_id] = (total_watts, device_count)
        return total_watts, device_count, cycle_detected

    rollups: list[PowerLocationRollup] = []
    for location_id, location in location_by_id.items():
        total_watts, device_count, _ = aggregate(location_id, set())
        if total_watts == 0 and device_count == 0:
            continue

        rollups.append(
            {
                "location_id": location_id,
                "location_name": location["name"],
                "parent_location_id": location["parent_id"],
                "total_watts": total_watts,
                "device_count": device_count,
                "estimated_monthly_cost": estimate_monthly_cost(
                    total_watts,
                    cost_per_kwh,
                ),
            }
        )

    rollups.sort(key=lambda item: (-item["total_watts"], item["location_name"]))
    return rollups
