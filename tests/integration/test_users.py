"""Integration tests for /api/users/ endpoints."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_user_payload(
    email: str = "newuser@test.local",
    username: str = "newuser",
    password: str = "securepass1",
    role: str = "Contributor",
) -> dict:
    return {
        "username": username,
        "email": email,
        "password": password,
        "role": role,
    }


def _make_admin_in_db(session: Session, email: str = "admin@example.com") -> User:
    """Create an admin user in the DB and return it."""
    user = User(
        username=email.split("@")[0],
        email=email,
        password_hash=hash_password("adminpass1"),
        role=Role.Admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _token_for(user: User) -> str:
    return create_jwt({"sub": str(user.id), "role": user.role.value, "version": user.token_version})


def _admin_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# CRUD flow
# ---------------------------------------------------------------------------


class TestUsersCRUD:
    def test_list_users_empty(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.get("/api/users/", headers=_admin_headers(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_user(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.post(
            "/api/users/",
            json=_create_user_payload(),
            headers=_admin_headers(admin_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@test.local"
        assert "id" in body
        assert "password_hash" not in body

    def test_get_user(
        self, client: TestClient, admin_token: str
    ) -> None:
        create_resp = client.post(
            "/api/users/",
            json=_create_user_payload(email="get_me@test.local", username="get_me"),
            headers=_admin_headers(admin_token),
        )
        user_id = create_resp.json()["id"]
        resp = client.get(
            f"/api/users/{user_id}", headers=_admin_headers(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == user_id

    def test_update_user(
        self, client: TestClient, admin_token: str
    ) -> None:
        create_resp = client.post(
            "/api/users/",
            json=_create_user_payload(email="upd@test.local", username="upd"),
            headers=_admin_headers(admin_token),
        )
        user_id = create_resp.json()["id"]
        resp = client.patch(
            f"/api/users/{user_id}",
            json={"username": "updated_name"},
            headers=_admin_headers(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "updated_name"

    def test_delete_user(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        admin = _make_admin_in_db(session, email="adm_del@test.local")
        admin_token = _token_for(admin)
        # Create a contributor to delete
        create_resp = client.post(
            "/api/users/",
            json=_create_user_payload(email="to_del@test.local", username="to_del"),
            headers=_admin_headers(admin_token),
        )
        assert create_resp.status_code == 201
        user_id = create_resp.json()["id"]
        resp = client.delete(
            f"/api/users/{user_id}", headers=_admin_headers(admin_token)
        )
        assert resp.status_code == 204
        get_resp = client.get(
            f"/api/users/{user_id}", headers=_admin_headers(admin_token)
        )
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# RBAC enforcement
# ---------------------------------------------------------------------------


class TestUsersRBAC:
    def test_list_requires_admin(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.get(
            "/api/users/", headers={"Authorization": f"Bearer {contributor_token}"}
        )
        assert resp.status_code == 403

    def test_list_reader_forbidden(
        self, client: TestClient, reader_token: str
    ) -> None:
        resp = client.get(
            "/api/users/", headers={"Authorization": f"Bearer {reader_token}"}
        )
        assert resp.status_code == 403

    def test_create_requires_admin(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.post(
            "/api/users/",
            json=_create_user_payload(email="rbac@test.local"),
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 403

    def test_delete_requires_admin(
        self, client: TestClient, contributor_token: str
    ) -> None:
        resp = client.delete(
            f"/api/users/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Business rule guards
# ---------------------------------------------------------------------------


class TestUsersGuards:
    def test_duplicate_email_returns_409(
        self, client: TestClient, admin_token: str
    ) -> None:
        payload = _create_user_payload(email="dup409@test.local", username="dup409")
        client.post("/api/users/", json=payload, headers=_admin_headers(admin_token))
        resp = client.post(
            "/api/users/", json=payload, headers=_admin_headers(admin_token)
        )
        assert resp.status_code == 409

    def test_short_password_returns_422(
        self, client: TestClient, admin_token: str
    ) -> None:
        payload = _create_user_payload(
            email="short422@test.local", username="short422", password="tiny"
        )
        resp = client.post(
            "/api/users/", json=payload, headers=_admin_headers(admin_token)
        )
        assert resp.status_code == 422

    def test_whitespace_username_returns_422(
        self, client: TestClient, admin_token: str
    ) -> None:
        payload = _create_user_payload(
            email="whitespace_user@test.local",
            username="   ",
            password="password123",
        )
        resp = client.post(
            "/api/users/", json=payload, headers=_admin_headers(admin_token)
        )
        assert resp.status_code == 422

    def test_invalid_email_returns_422(
        self, client: TestClient, admin_token: str
    ) -> None:
        payload = _create_user_payload(
            email="not-an-email",
            username="invalid_email_user",
            password="password123",
        )
        resp = client.post(
            "/api/users/", json=payload, headers=_admin_headers(admin_token)
        )
        assert resp.status_code == 422

    def test_self_delete_returns_400(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        admin = _make_admin_in_db(session, email="selfdelete@test.local")
        token = _token_for(admin)
        resp = client.delete(
            f"/api/users/{admin.id}", headers=_admin_headers(token)
        )
        assert resp.status_code == 400
        assert "own account" in resp.json()["detail"]

    def test_demoted_admin_old_token_loses_admin_authority(
        self,
        client: TestClient,
        session: Session,
        admin_token: str,
    ) -> None:
        target_admin = _make_admin_in_db(session, email="demote_target@test.local")
        old_admin_token = _token_for(target_admin)

        demote_resp = client.patch(
            f"/api/users/{target_admin.id}",
            json={"role": "Reader"},
            headers=_admin_headers(admin_token),
        )
        assert demote_resp.status_code == 200
        assert demote_resp.json()["role"] == "Reader"

        stale_resp = client.get("/api/users/", headers=_admin_headers(old_admin_token))
        assert stale_resp.status_code == 401
        assert "revoked" in stale_resp.json()["detail"].lower()

    def test_deactivated_admin_old_token_loses_admin_authority(
        self,
        client: TestClient,
        session: Session,
        admin_token: str,
    ) -> None:
        target_admin = _make_admin_in_db(session, email="deactivate_target@test.local")
        old_admin_token = _token_for(target_admin)

        deactivate_resp = client.patch(
            f"/api/users/{target_admin.id}",
            json={"is_active": False},
            headers=_admin_headers(admin_token),
        )
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["is_active"] is False

        stale_resp = client.get("/api/users/", headers=_admin_headers(old_admin_token))
        assert stale_resp.status_code == 401
        assert "revoked" in stale_resp.json()["detail"].lower()

    def test_get_not_found_returns_404(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.get(
            f"/api/users/{uuid.uuid4()}", headers=_admin_headers(admin_token)
        )
        assert resp.status_code == 404

    def test_update_not_found_returns_404(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.patch(
            f"/api/users/{uuid.uuid4()}",
            json={"username": "ghost"},
            headers=_admin_headers(admin_token),
        )
        assert resp.status_code == 404

    def test_delete_not_found_returns_404(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        admin = _make_admin_in_db(session, email="del_404@test.local")
        token = _token_for(admin)
        resp = client.delete(
            f"/api/users/{uuid.uuid4()}", headers=_admin_headers(token)
        )
        assert resp.status_code == 404
