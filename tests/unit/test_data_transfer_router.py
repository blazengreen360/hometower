"""Unit tests for import/export data transfer router internals."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
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
