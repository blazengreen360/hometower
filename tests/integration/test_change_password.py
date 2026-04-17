"""Integration tests for PATCH /api/auth/me/password (HT-025)."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password, verify_password


@pytest.fixture
def pw_user(session: Session) -> User:
    """Persist a user with known password for password-change tests."""
    user = User(
        username="pwchange",
        email="pwchange@test.local",
        password_hash=hash_password("oldpassword"),
        role=Role.Contributor,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def pw_token(pw_user: User) -> str:
    return create_jwt({"sub": str(pw_user.id), "role": "Contributor", "version": pw_user.token_version})


class TestChangePasswordEndpoint:
    def test_happy_path_returns_204(
        self, client: TestClient, pw_user: User, pw_token: str
    ) -> None:
        resp = client.patch(
            "/api/auth/me/password",
            json={"current_password": "oldpassword", "new_password": "newpassword123"},
            headers={"Authorization": f"Bearer {pw_token}"},
        )
        assert resp.status_code == 204

    def test_happy_path_updates_hash_in_db(
        self, client: TestClient, pw_user: User, pw_token: str, session: Session
    ) -> None:
        client.patch(
            "/api/auth/me/password",
            json={"current_password": "oldpassword", "new_password": "newpassword123"},
            headers={"Authorization": f"Bearer {pw_token}"},
        )
        session.refresh(pw_user)
        assert verify_password("newpassword123", pw_user.password_hash)

    def test_wrong_current_returns_401(
        self, client: TestClient, pw_user: User, pw_token: str
    ) -> None:
        resp = client.patch(
            "/api/auth/me/password",
            json={"current_password": "wrongpass", "new_password": "newpassword123"},
            headers={"Authorization": f"Bearer {pw_token}"},
        )
        assert resp.status_code == 401
        assert "Current password is incorrect" in resp.json()["detail"]

    def test_short_new_password_returns_422(
        self, client: TestClient, pw_user: User, pw_token: str
    ) -> None:
        resp = client.patch(
            "/api/auth/me/password",
            json={"current_password": "oldpassword", "new_password": "short"},
            headers={"Authorization": f"Bearer {pw_token}"},
        )
        assert resp.status_code == 422

    def test_same_as_current_returns_422(
        self, client: TestClient, pw_user: User, pw_token: str
    ) -> None:
        resp = client.patch(
            "/api/auth/me/password",
            json={"current_password": "oldpassword", "new_password": "oldpassword"},
            headers={"Authorization": f"Bearer {pw_token}"},
        )
        assert resp.status_code == 422
        assert "different from current" in resp.json()["detail"]

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/auth/me/password",
            json={"current_password": "any", "new_password": "newpassword123"},
        )
        assert resp.status_code == 401
