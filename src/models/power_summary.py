"""Power summary response models (HT-044)."""
import uuid

from sqlmodel import Field, SQLModel


class PowerLocationSummary(SQLModel):
    location_id: uuid.UUID
    location_name: str
    parent_location_id: uuid.UUID | None = None
    total_watts: int
    device_count: int
    estimated_monthly_cost: float | None = None


class PowerSummaryResponse(SQLModel):
    total_watts: int
    total_devices: int
    devices_with_power: int
    devices_without_power: int
    estimated_monthly_kwh: float
    estimated_monthly_cost: float | None = None
    currency: str | None = None
    cost_per_kwh: float | None = None
    by_location: list[PowerLocationSummary] = Field(default_factory=list)