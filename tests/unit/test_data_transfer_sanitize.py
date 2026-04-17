"""Unit tests for sanitization of import endpoint errors.

Ensure DB IntegrityError details are not leaked to API clients.
"""
import json

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import IntegrityError


class TestDataTransferImportSanitize:
    def _make_export_bytes(self) -> bytes:
        payload = {
            "version": "1.0",
            "exported_at": "2026-04-13T00:00:00Z",
            "users": [],
            "locations": [],
            "tags": [],
            "devices": [],
            "services": [],
            "service_dependencies": [],
            "connections": [],
            "device_tags": [],
            "custom_fields": [],
            "diagram_layouts": [],
        }
        return json.dumps(payload).encode("utf-8")

    def test_import_integrityerror_returns_generic_detail(
        self, client: TestClient, admin_token: str, monkeypatch
    ) -> None:
        """When the import raises IntegrityError, response detail is generic."""

        def _fake_import(session, payload):
            orig = Exception(
                'duplicate key value violates unique constraint "users_email_key" DETAIL: Key (email)=(sensitive@example.com) already exists'
            )
            raise IntegrityError("INSERT ...", {}, orig)

        monkeypatch.setattr(
            "src.api.routers.data_transfer.import_full_snapshot",
            _fake_import,
        )

        files = {"file": ("export.json", self._make_export_bytes(), "application/json")}
        headers = {"Authorization": f"Bearer {admin_token}"}

        resp = client.post("/api/import?confirm=true", files=files, headers=headers)

        assert resp.json()["detail"] == "Import failed: data integrity violation"

        # Ensure sensitive DB/SQL strings are not present in the response body
        body_lower = resp.text.lower()
        assert "duplicate key" not in body_lower
        assert "users_email_key" not in body_lower
        assert "sensitive@example.com" not in body_lower

    def test_import_integrityerror_returns_422_status(
        self, client: TestClient, admin_token: str, monkeypatch
    ) -> None:
        """When the import raises IntegrityError, status code is 422."""

        def _fake_import(session, payload):
            orig = Exception("some sql error: duplicate key")
            raise IntegrityError("INSERT ...", {}, orig)

        monkeypatch.setattr(
            "src.api.routers.data_transfer.import_full_snapshot",
            _fake_import,
        )

        files = {"file": ("export.json", self._make_export_bytes(), "application/json")}
        headers = {"Authorization": f"Bearer {admin_token}"}

        resp = client.post("/api/import?confirm=true", files=files, headers=headers)

        assert resp.status_code == 422
