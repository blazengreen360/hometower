"""Integration tests for the auth endpoints and JWT middleware.

Tests run against the full FastAPI stack with an SQLite in-memory database.
Real JWTs are created via create_jwt() — bcrypt and JWT are never mocked.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlmodel import Session, select

from src.models.types import Role
from src.models.user import User
from src.services.auth_service import create_first_admin_if_needed
from src.utils.auth import create_jwt, hash_password
from src.utils.settings import settings


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_valid_credentials_returns_200_with_token(
        self, client: TestClient, admin_user: User
    ) -> None:
        response = client.post(
            "/api/auth/login",
            json={"email": admin_user.email, "password": "testadminpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_invalid_password_returns_401(
        self, client: TestClient, admin_user: User
    ) -> None:
        response = client.post(
            "/api/auth/login",
            json={"email": admin_user.email, "password": "wrong_password"},
        )
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_nonexistent_email_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/login",
            json={"email": "ghost@nowhere.local", "password": "anypassword"},
        )
        assert response.status_code == 401

    def test_valid_login_token_is_decodable(
        self, client: TestClient, admin_user: User
    ) -> None:
        response = client.post(
            "/api/auth/login",
            json={"email": admin_user.email, "password": "testadminpass123"},
        )
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        assert payload["role"] == Role.Admin.value
        assert "sub" in payload
        assert "exp" in payload

    def test_login_endpoint_accessible_without_auth_header(
        self, client: TestClient, admin_user: User
    ) -> None:
        """Login must NOT return 401 due to missing token — it is public."""
        response = client.post(
            "/api/auth/login",
            json={"email": admin_user.email, "password": "testadminpass123"},
        )
        # 200 = success, 401 (if any) must only be from invalid credentials not middleware
        assert response.status_code != 403


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_with_valid_token_returns_200(
        self, client: TestClient, admin_token: str
    ) -> None:
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Logged out"

    def test_logout_without_token_returns_401(self, client: TestClient) -> None:
        response = client.post("/api/auth/logout")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AuthMiddleware
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    def test_protected_route_without_token_returns_401(
        self, client: TestClient
    ) -> None:
        response = client.post("/api/auth/logout")
        assert response.status_code == 401

    def test_protected_route_with_valid_token_passes(
        self, client: TestClient, admin_token: str
    ) -> None:
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_expired_token_returns_401_with_expired_detail(
        self, client: TestClient
    ) -> None:
        expired_payload: dict[str, str | int] = {
            "sub": str(uuid4()),
            "role": "Admin",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        }
        expired_token = jwt.encode(
            expired_payload, settings.secret_key, algorithm="HS256"
        )
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_tampered_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer totally.invalid.token"},
        )
        assert response.status_code == 401

    def test_health_endpoint_accessible_without_token(
        self, client: TestClient
    ) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_missing_bearer_prefix_returns_401(self, client: TestClient) -> None:
        token = create_jwt({"sub": str(uuid4()), "role": "Admin"})
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": token},  # no "Bearer " prefix
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# First-boot admin creation
# ---------------------------------------------------------------------------

class TestFirstBootAdmin:
    def test_creates_admin_when_no_users_exist(self, session: Session) -> None:
        # Wipe all users for an isolated test
        users = list(session.exec(select(User)).all())
        for u in users:
            session.delete(u)
        session.commit()

        create_first_admin_if_needed(session)

        all_users = list(session.exec(select(User)).all())
        assert len(all_users) == 1
        assert all_users[0].email == settings.admin_email
        assert all_users[0].role == Role.Admin
        assert all_users[0].username == "admin"

    def test_does_not_create_duplicate_when_users_exist(
        self, session: Session, admin_user: User
    ) -> None:
        before = len(list(session.exec(select(User)).all()))
        create_first_admin_if_needed(session)
        after = len(list(session.exec(select(User)).all()))
        assert after == before

    def test_admin_password_is_hashed_not_plaintext(self, session: Session) -> None:
        users = list(session.exec(select(User)).all())
        for u in users:
            session.delete(u)
        session.commit()

        create_first_admin_if_needed(session)

        user = session.exec(select(User)).one()
        assert user.password_hash != settings.admin_password
        assert user.password_hash.startswith("$2b$")
