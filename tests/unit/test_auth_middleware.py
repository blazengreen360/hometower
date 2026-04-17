"""Unit tests for AuthMiddleware dispatch handling malformed version claim (BUG-003).

Tests ensure that malformed or missing `version` claims and tokens for
non-existent users are rejected with HTTP 401 rather than raising.
"""
import uuid

import pytest

from src.utils.auth import create_jwt


class TestAuthMiddleware:
    def test_non_numeric_version_returns_401(self, client, admin_user) -> None:
        """A token with a non-integer `version` claim must return 401."""
        token = create_jwt({"sub": str(admin_user.id), "role": "Admin", "version": "not-an-int"})
        res = client.get("/api/workspaces/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_missing_version_returns_401(self, client, admin_user) -> None:
        """A token missing the `version` claim must return 401."""
        # create_jwt will append jti/iat/exp but we intentionally omit `version`
        token = create_jwt({"sub": str(admin_user.id), "role": "Admin"})
        res = client.get("/api/workspaces/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_valid_version_but_nonexistent_user_returns_401(self, client) -> None:
        """A token with a valid numeric version but whose `sub` does not
        correspond to any user in the DB should return 401.
        """
        token = create_jwt({"sub": str(uuid.uuid4()), "role": "Admin", "version": 1})
        res = client.get("/api/workspaces/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_malformed_sub_returns_401(self, client) -> None:
        """A token with a non-UUID `sub` claim must return 401."""
        token = create_jwt({"sub": "not-a-uuid", "role": "Admin", "version": 1})
        res = client.get("/api/workspaces/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_db_role_overrides_stale_token_role_claim(self, client, admin_user) -> None:
        """RBAC should use role loaded from DB, not role claim from token."""
        token = create_jwt(
            {
                "sub": str(admin_user.id),
                "role": "Reader",  # stale/forged claim
                "version": admin_user.token_version,
            }
        )
        res = client.get("/api/users/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    def test_inactive_user_rejected_even_with_matching_token_version(
        self, client, session, admin_user
    ) -> None:
        """Middleware must reject disabled users from DB state."""
        admin_user.is_active = False
        session.add(admin_user)
        session.commit()

        token = create_jwt(
            {
                "sub": str(admin_user.id),
                "role": "Admin",
                "version": admin_user.token_version,
            }
        )
        res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert "disabled" in res.json()["detail"].lower()
