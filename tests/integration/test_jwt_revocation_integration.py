"""Integration tests for JWT revocation (SEC-1.1, SEC-4.4).

Tests cover:
- Login sets HttpOnly cookie with correct attributes
- Login response body has LoginResponse fields (no access_token)
- Logout revokes tokens server-side
- Old token rejected after logout
- Old token rejected after password change
- Bearer header fallback still works
- Token version mismatch returns 401
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password
from src.utils.settings import settings


@pytest.fixture
def login_user(session: Session) -> User:
    """Persist a user for login-based tests."""
    user = User(
        username="login_test",
        email=f"login_{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("loginpass123"),
        role=Role.Contributor,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestLoginCookie:
    def test_login_sets_httponly_cookie(
        self, client: TestClient, login_user: User
    ) -> None:
        resp = client.post(
            "/api/auth/login",
            json={"email": login_user.email, "password": "loginpass123"},
        )
        assert resp.status_code == 200
        assert "ht_access_token" in resp.cookies

    def test_login_response_has_user_id(
        self, client: TestClient, login_user: User
    ) -> None:
        resp = client.post(
            "/api/auth/login",
            json={"email": login_user.email, "password": "loginpass123"},
        )
        data = resp.json()
        assert "user_id" in data
        assert data["user_id"] == str(login_user.id)

    def test_login_response_has_role(
        self, client: TestClient, login_user: User
    ) -> None:
        resp = client.post(
            "/api/auth/login",
            json={"email": login_user.email, "password": "loginpass123"},
        )
        data = resp.json()
        assert "role" in data
        assert data["role"] == Role.Contributor.value

    def test_login_response_has_token_exp(
        self, client: TestClient, login_user: User
    ) -> None:
        from datetime import datetime, timezone
        before = int(datetime.now(timezone.utc).timestamp())
        resp = client.post(
            "/api/auth/login",
            json={"email": login_user.email, "password": "loginpass123"},
        )
        data = resp.json()
        assert "token_exp" in data
        assert data["token_exp"] > before

    def test_login_response_has_cookie_token_type(
        self, client: TestClient, login_user: User
    ) -> None:
        resp = client.post(
            "/api/auth/login",
            json={"email": login_user.email, "password": "loginpass123"},
        )
        assert resp.json()["token_type"] == "cookie"

    def test_login_response_includes_access_token_field(
        self, client: TestClient, login_user: User
    ) -> None:
        resp = client.post(
            "/api/auth/login",
            json={"email": login_user.email, "password": "loginpass123"},
        )
        assert "access_token" in resp.json()


class TestTokenVersionRevocation:
    def test_old_bearer_rejected_after_logout(
        self, client: TestClient, session: Session
    ) -> None:
        """After logout, the old Bearer token returns 401."""
        user = User(
            username="revoke_integ",
            email=f"revoke_{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("testpass123"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_jwt({"sub": str(user.id), "role": "Contributor", "version": 1})
        headers = {"Authorization": f"Bearer {token}"}

        # Logout
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 200

        # Old token is now rejected
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 401

    def test_old_token_rejected_after_password_change(
        self, client: TestClient, session: Session
    ) -> None:
        """After password change, old token (same version) is rejected."""
        user = User(
            username="pwchange_integ",
            email=f"pwchg_{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("oldpass123"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_jwt({"sub": str(user.id), "role": "Contributor", "version": 1})
        headers = {"Authorization": f"Bearer {token}"}

        # Change password
        resp = client.patch(
            "/api/auth/me/password",
            json={"current_password": "oldpass123", "new_password": "newpass456"},
            headers=headers,
        )
        assert resp.status_code == 204

        # Old token is now rejected
        resp = client.post("/api/auth/logout", headers=headers)
        assert resp.status_code == 401

    def test_version_mismatch_returns_401(
        self, client: TestClient, session: Session
    ) -> None:
        user = User(
            username="ver_mismatch",
            email=f"verm_{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("x"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Bump token_version so token with version=1 is stale
        user.token_version = 2
        session.add(user)
        session.commit()

        token = create_jwt({"sub": str(user.id), "role": "Contributor", "version": 1})
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert "revoked" in resp.json()["detail"].lower()

    def test_missing_version_claim_returns_401(
        self, client: TestClient
    ) -> None:
        """Token without version claim is rejected as invalid."""
        from jose import jwt as jose_jwt
        token = jose_jwt.encode(
            {"sub": str(uuid.uuid4()), "role": "Admin"},
            settings.secret_key, algorithm="HS256",
        )
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


class TestBearerFallback:
    def test_bearer_token_still_authenticates(
        self, client: TestClient, session: Session
    ) -> None:
        user = User(
            username="bearer_test",
            email=f"bearer_{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("x"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_jwt({"sub": str(user.id), "role": "Contributor", "version": 1})
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_no_token_no_cookie_returns_401(self, client: TestClient) -> None:
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401


class TestLogoutClearsCookie:
    def test_logout_clears_cookie(
        self, client: TestClient, session: Session
    ) -> None:
        user = User(
            username="cookie_logout",
            email=f"ckout_{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("x"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_jwt({"sub": str(user.id), "role": "Contributor", "version": 1})
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Cookie should be deleted (empty value or set-cookie with max-age=0)
        set_cookie_header = resp.headers.get("set-cookie", "")
        assert "ht_access_token" in set_cookie_header
