"""Device attachment endpoints (HT-042)."""
import asyncio
import inspect
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.api.middleware.rate_limit import limiter
from src.models.attachment import DeviceAttachmentResponse
from src.models.types import Role
from src.services import attachment_service
from src.utils.db import get_session

router = APIRouter(prefix="/devices", tags=["devices"])


def _read_upload_bytes(file: UploadFile, max_bytes: int) -> bytes:
    """Read upload bytes while supporting async-only test doubles."""
    if hasattr(file, "file") and file.file is not None:
        return file.file.read(max_bytes)
    maybe_bytes = file.read(max_bytes)
    if isinstance(maybe_bytes, bytes):
        return maybe_bytes
    if inspect.isawaitable(maybe_bytes):
        return asyncio.run(maybe_bytes)
    raise HTTPException(status_code=400, detail="Upload stream could not be read")


def _attachment_response(
    path: Path,
    *,
    media_type: str,
    filename: str,
    content_disposition_type: str,
) -> FileResponse:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type=content_disposition_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/{device_id}/attachments",
    response_model=list[DeviceAttachmentResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_device_attachments(
    device_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[DeviceAttachmentResponse]:
    """Return all attachments for a device."""
    return attachment_service.list_for_device(device_id, session)


@router.post(
    "/{device_id}/attachments",
    status_code=201,
    response_model=DeviceAttachmentResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
@limiter.limit("50/minute")
def upload_device_attachment(
    request: Request,
    device_id: uuid.UUID,
    file: UploadFile,
    session: Session = Depends(get_session),
) -> DeviceAttachmentResponse:
    """Upload one device attachment via multipart/form-data."""
    raw = _read_upload_bytes(file, attachment_service.MAX_ATTACHMENT_BYTES + 1)
    return attachment_service.upload(device_id, file.filename or "", raw, session)


@router.get(
    "/{device_id}/attachments/{attachment_id}/download",
    dependencies=[Depends(require_role(Role.Reader))],
)
def download_device_attachment(
    device_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Download an attachment with attachment disposition headers."""
    attachment = attachment_service.get_attachment(device_id, attachment_id, session)
    return _attachment_response(
        attachment_service.resolve_original_path(attachment),
        media_type=attachment.content_type,
        filename=attachment.filename,
        content_disposition_type="attachment",
    )


@router.get(
    "/{device_id}/attachments/{attachment_id}/preview",
    dependencies=[Depends(require_role(Role.Reader))],
)
def preview_device_attachment(
    device_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Serve an image attachment inline for lightbox preview."""
    attachment = attachment_service.get_attachment(device_id, attachment_id, session)
    if not attachment_service.is_image_attachment(attachment):
        raise HTTPException(status_code=404, detail="Attachment preview not available")
    return _attachment_response(
        attachment_service.resolve_original_path(attachment),
        media_type=attachment.content_type,
        filename=attachment.filename,
        content_disposition_type="inline",
    )


@router.get(
    "/{device_id}/attachments/{attachment_id}/thumbnail",
    dependencies=[Depends(require_role(Role.Reader))],
)
def thumbnail_device_attachment(
    device_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Serve a generated thumbnail for image attachments."""
    attachment = attachment_service.get_attachment(device_id, attachment_id, session)
    if not attachment_service.is_image_attachment(attachment):
        raise HTTPException(status_code=404, detail="Attachment thumbnail not available")
    thumbnail_path = attachment_service.resolve_thumbnail_path(attachment)
    if not thumbnail_path.is_file():
        raise HTTPException(status_code=404, detail="Attachment thumbnail not available")
    return _attachment_response(
        thumbnail_path,
        media_type="image/png",
        filename=f"{Path(attachment.filename).stem}_thumb.png",
        content_disposition_type="inline",
    )


@router.delete(
    "/{device_id}/attachments/{attachment_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_device_attachment(
    device_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete one attachment and its stored files."""
    attachment_service.delete(device_id, attachment_id, session)