"""Device attachment SQLModel definitions (HT-042)."""
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeviceAttachment(SQLModel, table=True):
    __tablename__ = "device_attachments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", index=True)
    filename: str = Field(max_length=255)
    stored_path: str = Field(max_length=1024)
    content_type: str = Field(max_length=255)
    size_bytes: int = Field(ge=0)
    created_at: datetime = Field(default_factory=_utcnow)


class DeviceAttachmentResponse(SQLModel):
    id: uuid.UUID
    device_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    is_image: bool
    has_thumbnail: bool