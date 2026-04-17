"""Unit tests for change_own_password and create_first_admin_if_needed (HT-025)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.services.auth_service import change_own_password, create_first_admin_if_needed
from src.utils.auth import hash_password, verify_password


def _make_user(session: Session, password: str = "oldpassword") -> User:
    user = User(
        username="test",
        email=f"test_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password(password),
        role=Role.Contributor,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestChangeOwnPassword:
    def test_happy_path_updates_password_hash(self, session: Session) -> None:
        user = _make_user(session)
        change_own_password(user.id, "oldpassword", "newpassword123", session)
        session.refresh(user)
        assert verify_password("newpassword123", user.password_hash)

    def test_happy_path_updates_updated_at(self, session: Session) -> None:
        user = _make_user(session)
        before = user.updated_at
        change_own_password(user.id, "oldpassword", "newpassword123", session)
        session.refresh(user)
        assert user.updated_at >= before

    def test_wrong_current_raises_401(self, session: Session) -> None:
        user = _make_user(session)
        with pytest.raises(HTTPException) as exc_info:
            change_own_password(user.id, "wrongpass", "newpassword123", session)
        assert exc_info.value.status_code == 401
        assert "Current password is incorrect" in exc_info.value.detail

    def test_short_new_password_raises_422(self, session: Session) -> None:
        user = _make_user(session)
        with pytest.raises(HTTPException) as exc_info:
            change_own_password(user.id, "oldpassword", "short", session)
        assert exc_info.value.status_code == 422
        assert "8 characters" in exc_info.value.detail

    def test_same_as_current_raises_422(self, session: Session) -> None:
        user = _make_user(session)
        with pytest.raises(HTTPException) as exc_info:
            change_own_password(user.id, "oldpassword", "oldpassword", session)
        assert exc_info.value.status_code == 422
        assert "different from current" in exc_info.value.detail

    def test_nonexistent_user_raises_404(self, session: Session) -> None:
        with pytest.raises(HTTPException) as exc_info:
            change_own_password(uuid.uuid4(), "oldpass", "newpassword123", session)
        assert exc_info.value.status_code == 404

    def test_boundary_8_char_new_password_succeeds(self, session: Session) -> None:
        user = _make_user(session)
        change_own_password(user.id, "oldpassword", "exactly8", session)
        session.refresh(user)
        assert verify_password("exactly8", user.password_hash)


class TestCreateFirstAdminIfNeeded:
    def test_warning_logged_when_admin_password_set_but_users_exist(
        self, session: Session
    ) -> None:
        """Else branch: logs warning when DB not empty but admin_password still set."""
        user = _make_user(session, "somepassword")
        # User is committed; db is non-empty

        with patch("src.services.auth_service.settings") as mock_settings:
            mock_settings.admin_password = "still-set-in-env"
            mock_settings.admin_email = "admin@test.local"
            with patch("src.services.auth_service.logger") as mock_logger:
                create_first_admin_if_needed(session)
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "ADMIN_PASSWORD" in warning_msg
            assert "first-boot seeding has already run" in warning_msg

    def test_no_warning_when_admin_password_empty(self, session: Session) -> None:
        _make_user(session)
        with patch("src.services.auth_service.settings") as mock_settings:
            mock_settings.admin_password = ""
            mock_settings.admin_email = "admin@test.local"
            with patch("src.services.auth_service.logger") as mock_logger:
                create_first_admin_if_needed(session)
            mock_logger.warning.assert_not_called()
