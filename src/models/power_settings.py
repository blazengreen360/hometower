"""Power settings SQLModel definitions (HT-044)."""
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_currency(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("currency must be a 3-letter ISO code")
    return normalized


class PowerSettingsBase(SQLModel):
    cost_per_kwh: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_currency(value)


class PowerSettings(PowerSettingsBase, table=True):
    __tablename__ = "power_settings"

    scope: str = Field(default="global", primary_key=True, max_length=16)
    updated_at: datetime = Field(default_factory=_utcnow)


class PowerSettingsCreate(PowerSettingsBase):
    pass


class PowerSettingsUpdate(SQLModel):
    cost_per_kwh: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_currency(value)


class PowerSettingsResponse(PowerSettingsBase):
    updated_at: datetime | None = None