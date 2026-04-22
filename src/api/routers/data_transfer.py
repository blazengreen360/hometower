"""Data transfer router — export and import endpoints (HT-012, HT-013).

This module hides the HTTP streaming strategy and Content-Disposition format.
"""
import asyncio
from collections.abc import Generator
from datetime import date
import inspect
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.api.middleware.rate_limit import limiter
from src.domain.export import validate_export_version
from src.api.dependencies.rbac import require_role
from src.models.export_schema import ExportSchema
from src.models.types import Role
from src.services.export_service import build_full_export
from src.services.import_validation import ImportPayloadValidationError
from src.services.import_service import import_full_snapshot
from src.utils.db import get_session
from src.utils.logger import logger

router = APIRouter(tags=["data-transfer"])

_MAX_IMPORT_BYTES = 50 * 1024 * 1024  # 50 MB


def _redact_export_payload(payload: dict[str, object]) -> dict[str, object]:
    """Apply best-effort redaction to sensitive export fields."""
    redacted = dict(payload)
    devices_raw = redacted.get("devices")
    if isinstance(devices_raw, list):
        for item in devices_raw:
            if not isinstance(item, dict):
                continue
            if "ip" in item:
                item["ip"] = "[REDACTED]"
            if "mac" in item:
                item["mac"] = "[REDACTED]"
            if "notes" in item:
                item["notes"] = "[REDACTED]"
    return redacted


def _read_upload_bytes(file: UploadFile, max_bytes: int) -> bytes:
    """Read upload payload in sync handlers while supporting async-only test doubles."""
    if hasattr(file, "file") and file.file is not None:
        return file.file.read(max_bytes)
    maybe_bytes = file.read(max_bytes)
    if isinstance(maybe_bytes, bytes):
        return maybe_bytes
    if inspect.isawaitable(maybe_bytes):
        return asyncio.run(maybe_bytes)
    raise HTTPException(status_code=400, detail="Upload stream could not be read")


@router.get(
    "/export",
    dependencies=[Depends(require_role(Role.Contributor))],
    summary="Export all data as JSON",
)
@limiter.limit("3/minute")
def export_json(
    request: Request,
    redact: bool = Query(
        default=False,
        description="When true, redacts sensitive fields in exported payload.",
    ),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Return a streaming JSON download of the full database snapshot.

    Content-Disposition: attachment; filename="hometower-export-YYYY-MM-DD.json"
    Accessible to Contributor role and above.
    """
    data = build_full_export(session)
    filename = f"hometower-export-{date.today().isoformat()}.json"

    def _generate() -> Generator[str, None, None]:
        if not redact:
            yield data.model_dump_json(indent=2)
            return
        payload = json.loads(data.model_dump_json())
        if isinstance(payload, dict):
            yield json.dumps(_redact_export_payload(payload), indent=2)
            return
        yield data.model_dump_json(indent=2)

    return StreamingResponse(
        _generate(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/import",
    dependencies=[Depends(require_role(Role.Admin))],
    summary="Import a full JSON snapshot (destructive)",
)
@limiter.limit("1/minute")
def import_json(
    request: Request,
    file: UploadFile,
    confirm: bool = Query(
        False,
        description="Must be true to confirm destructive replace",
    ),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Destructively replace all data from a previously-exported Hometower JSON.

    - ``confirm=true`` query parameter is required to prevent accidental calls.
    - File size capped at 50 MB.
    - Admin role required.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true query parameter is required to perform destructive import",
        )

    raw = _read_upload_bytes(file, _MAX_IMPORT_BYTES + 1)
    if len(raw) > _MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 50 MB limit")

    try:
        payload_dict = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Malformed JSON: {exc}") from exc

    try:
        payload = ExportSchema.model_validate(payload_dict)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        validate_export_version(payload.version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        counts = import_full_snapshot(session, payload)
    except ImportPayloadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        logger.error("import IntegrityError on data_transfer import")
        raise HTTPException(
            status_code=422,
            detail="Import failed: data integrity violation",
        ) from exc

    return counts
