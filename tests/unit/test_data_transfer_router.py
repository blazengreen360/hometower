"""Unit tests for import/export data transfer router internals."""
import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from src.api.middleware.rate_limit import limiter
from src.api.routers.data_transfer import _MAX_IMPORT_BYTES, import_json


class _FakeUpload:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.read_calls: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_calls.append(size)
        if size < 0:
            return self.payload
        return self.payload[:size]


def _make_request() -> Request:
    app = FastAPI()
    app.state.limiter = limiter
    scope: dict[str, object] = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/import",
        "raw_path": b"/api/import",
        "query_string": b"confirm=true",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "app": app,
    }
    return Request(scope)


def _valid_export_bytes() -> bytes:
    return json.dumps(
        {
            "version": "1.0",
            "exported_at": "2026-04-21T00:00:00Z",
            "devices": [],
            "connections": [],
            "locations": [],
            "tags": [],
            "device_tags": [],
            "networks": [],
            "device_networks": [],
            "custom_fields": [],
            "services": [],
            "service_dependencies": [],
            "workspaces": [],
            "topologies": [],
            "diagram_layouts": [],
            "users": [],
        }
    ).encode("utf-8")


def test_import_uses_bounded_read_and_rejects_oversized_file() -> None:
    fake_upload = _FakeUpload(b"x" * (_MAX_IMPORT_BYTES + 64))

    with pytest.raises(HTTPException) as exc_info:
        import_json(
            request=_make_request(),
            file=fake_upload,
            confirm=True,
            session=MagicMock(),
        )

    assert exc_info.value.status_code == 413
    assert fake_upload.read_calls == [_MAX_IMPORT_BYTES + 1]


def test_import_does_not_commit_in_router_after_service_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()

    monkeypatch.setattr(
        "src.api.routers.data_transfer.import_full_snapshot",
        lambda current_session, payload: {"devices": 0},
    )

    result = import_json(
        request=_make_request(),
        file=_FakeUpload(_valid_export_bytes()),
        confirm=True,
        session=session,
    )

    assert result == {"devices": 0}
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_import_does_not_rollback_in_router_when_service_raises_integrity_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()

    def _fail_import(current_session: object, payload: object) -> dict[str, int]:
        raise IntegrityError("INSERT ...", {}, Exception("simulated duplicate"))

    monkeypatch.setattr(
        "src.api.routers.data_transfer.import_full_snapshot",
        _fail_import,
    )

    with pytest.raises(HTTPException) as exc_info:
        import_json(
            request=_make_request(),
            file=_FakeUpload(_valid_export_bytes()),
            confirm=True,
            session=session,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Import failed: data integrity violation"
    session.rollback.assert_not_called()
