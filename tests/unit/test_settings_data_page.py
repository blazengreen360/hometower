"""Unit tests for settings data page helpers."""
from io import BytesIO

from src.ui.pages.settings_data import _extract_upload_bytes
from src.ui.pages.settings_data import _export_download_js


class _BrokenReader:
    def read(self) -> bytes:
        raise RuntimeError("boom")


def test_extract_upload_bytes_accepts_bytes() -> None:
    assert _extract_upload_bytes(b"hello") == b"hello"


def test_extract_upload_bytes_reads_file_like_objects() -> None:
    assert _extract_upload_bytes(BytesIO(b"hello")) == b"hello"


def test_extract_upload_bytes_converts_bytearray() -> None:
    assert _extract_upload_bytes(bytearray(b"hello")) == b"hello"


def test_extract_upload_bytes_returns_none_for_unreadable_reader() -> None:
    assert _extract_upload_bytes(_BrokenReader()) is None


def test_extract_upload_bytes_returns_none_for_missing_payload() -> None:
    assert _extract_upload_bytes(None) is None


def test_export_download_js_includes_bearer_auth_header() -> None:
    js = _export_download_js("token-123")
    assert "Authorization" in js
    assert "Bearer token-123" in js


def test_export_download_js_contains_specific_failure_messages_without_alert() -> None:
    js = _export_download_js("token-123")
    assert "session may have expired" in js
    assert "does not have permission" in js
    assert "Backup failed" in js
    assert "window.alert" not in js


def test_export_download_js_handles_401_403_and_server_failures_distinctly() -> None:
    js = _export_download_js("token-123")
    assert "response.status === 401" in js
    assert "response.status === 403" in js
    assert "response.status >= 500" in js


def test_export_download_js_includes_credentials_include() -> None:
    js = _export_download_js("token-123")
    assert "credentials: 'include'" in js
