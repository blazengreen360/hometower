"""Integration tests for GET /api/system/stats (HT-035)."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import hash_password


class TestSystemStats:
    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/system/stats")
        assert resp.status_code == 401

    def test_reader_can_access(self, client: TestClient, reader_token: str) -> None:
        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.status_code == 200

    def test_contributor_can_access(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200

    def test_returns_all_count_fields(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        data = resp.json()
        for field in ("devices", "connections", "locations", "tags", "custom_fields", "diagrams"):
            assert field in data
            assert isinstance(data[field], int)

    def test_non_admin_gets_null_user_count(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        assert resp.json()["users"] is None

    def test_reader_response_omits_db_diagnostics(
        self, client: TestClient, reader_token: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "src.api.routers.system.get_db_diagnostics",
            lambda session: ("PostgreSQL 16.2", 123456),
        )

        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {reader_token}"},
        )

        data = resp.json()
        assert "db_version" not in data
        assert "db_size_bytes" not in data
        assert data["users"] is None

    def test_contributor_response_omits_db_diagnostics(
        self,
        client: TestClient,
        contributor_token: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "src.api.routers.system.get_db_diagnostics",
            lambda session: ("PostgreSQL 16.2", 123456),
        )

        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        data = resp.json()
        assert "db_version" not in data
        assert "db_size_bytes" not in data

    def test_admin_gets_integer_user_count(
        self, client: TestClient, admin_token: str, session: Session
    ) -> None:
        user = User(
            username="statstest",
            email="statstest@example.com",
            password_hash=hash_password("password123"),
            role=Role.Reader,
        )
        session.add(user)
        session.commit()
        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.json()["users"] is not None
        assert resp.json()["users"] >= 1

    def test_admin_response_includes_db_diagnostics(
        self, client: TestClient, admin_token: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "src.api.routers.system.get_db_diagnostics",
            lambda session: ("PostgreSQL 16.2", 123456),
        )

        resp = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert resp.json()["db_version"] == "PostgreSQL 16.2"
        assert resp.json()["db_size_bytes"] == 123456

    def test_counts_reflect_created_device(
        self, client: TestClient, contributor_token: str, reader_token: str
    ) -> None:
        before = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {reader_token}"},
        ).json()["devices"]

        client.post(
            "/api/devices/",
            json={"name": "StatsDevice", "type": "Server"},
            headers={"Authorization": f"Bearer {contributor_token}"},
        )

        after = client.get(
            "/api/system/stats",
            headers={"Authorization": f"Bearer {reader_token}"},
        ).json()["devices"]
        assert after == before + 1
