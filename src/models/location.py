"""Location SQLModel definitions."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from src.models.types import LocationType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_rack(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    stripped = v.strip()
    if stripped == "":
        return None
    return stripped


def _validate_row(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v

    stripped = v.strip()
    if stripped == "":
        raise ValueError("row must not be empty")

    if stripped.startswith("-") and stripped[1:].isdigit():
        raise ValueError("row must be non-negative")

    if not any(ch.isalnum() for ch in stripped):
        raise ValueError("row must contain at least one alphanumeric character")

    return stripped


class LocationBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    type: LocationType
    lat: Optional[float] = Field(default=None)
    lng: Optional[float] = Field(default=None)
    rack: Optional[str] = Field(default=None, max_length=64)
    row: Optional[str] = Field(default=None, max_length=64)
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="locations.id")

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -90 or v > 90):
            raise ValueError(f"lat must be between -90 and 90, got {v}")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -180 or v > 180):
            raise ValueError(f"lng must be between -180 and 180, got {v}")
        return v

    @field_validator("rack")
    @classmethod
    def validate_rack(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_rack(v)

    @field_validator("row")
    @classmethod
    def validate_row(cls, v: Optional[str]) -> Optional[str]:
        return _validate_row(v)


class Location(LocationBase, table=True):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_location_parent_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class LocationCreate(LocationBase):
    pass


class LocationUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[LocationType] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rack: Optional[str] = Field(default=None, max_length=64)
    row: Optional[str] = Field(default=None, max_length=64)
    parent_id: Optional[uuid.UUID] = None

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            raise ValueError("name must not be blank")
        return v

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -90 or v > 90):
            raise ValueError(f"lat must be between -90 and 90, got {v}")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -180 or v > 180):
            raise ValueError(f"lng must be between -180 and 180, got {v}")
        return v

    @field_validator("rack")
    @classmethod
    def validate_rack(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_rack(v)

    @field_validator("row")
    @classmethod
    def validate_row(cls, v: Optional[str]) -> Optional[str]:
        return _validate_row(v)


class LocationResponse(LocationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LocationResponseWithAncestors(LocationResponse):
    ancestors: list[LocationResponse] = Field(default_factory=list)
