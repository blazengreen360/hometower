"""Dashboard summary response models (HT-082 foundation)."""
import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class DashboardWorkspaceOption(SQLModel):
    id: uuid.UUID | None = None
    name: str


class DashboardPowerWidget(SQLModel):
    workspace_options: list[DashboardWorkspaceOption] = Field(default_factory=list)
    selected_workspace_id: uuid.UUID | None = None
    selected_workspace_name: str
    total_watts: int
    estimated_monthly_cost: float | None = None
    currency: str | None = None


class DashboardBreakdownCount(SQLModel):
    key: str
    count: int
    route: str


class DashboardInventoryBreakdown(SQLModel):
    status_counts: list[DashboardBreakdownCount] = Field(default_factory=list)
    type_counts: list[DashboardBreakdownCount] = Field(default_factory=list)


class DashboardRecentActivityItem(SQLModel):
    kind: str
    title: str
    subtitle: str
    timestamp: datetime
    route: str


class DashboardSummaryResponse(SQLModel):
    devices: int
    workspaces: int
    topologies: int
    offline_devices: int
    recent_edits: int
    power: DashboardPowerWidget
    inventory_breakdown: DashboardInventoryBreakdown
    recent_activity: list[DashboardRecentActivityItem] = Field(default_factory=list)
