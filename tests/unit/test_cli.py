"""Unit tests for src/cli.py — reset-password subcommand."""
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import hash_password, verify_password


def _make_user(email: str = "user@test.local") -> User:
    return User(
        id=uuid.uuid4(),
        username=email.split("@")[0],
        email=email,
        password_hash=hash_password("oldpassword"),
        role=Role.Contributor,
    )


class TestResetPassword:
    def test_success(self, session: Session) -> None:
        """reset-password updates the password hash in the DB."""
        from src.repositories import user_repository
        from src.cli import _reset_password

        user = _make_user("cli_user@test.local")
        session.add(user)
        session.commit()
        session.refresh(user)

        with patch("src.cli.Session") as MockSession:
            MockSession.return_value.__enter__ = lambda s: session
            MockSession.return_value.__exit__ = MagicMock(return_value=False)
            result = _reset_password("cli_user@test.local", "newpassword1")

        assert result == 0
        # Verify the password was actually updated
        updated = user_repository.get_by_email(session, "cli_user@test.local")
        assert updated is not None
        assert verify_password("newpassword1", updated.password_hash)

    def test_user_not_found_returns_1(self, session: Session) -> None:
        from src.cli import _reset_password

        with patch("src.cli.Session") as MockSession:
            MockSession.return_value.__enter__ = lambda s: session
            MockSession.return_value.__exit__ = MagicMock(return_value=False)
            result = _reset_password("nobody@test.local", "newpassword1")

        assert result == 1

    def test_short_password_returns_1(self, session: Session) -> None:
        from src.cli import _reset_password

        # Should fail before even opening a session
        result = _reset_password("anyone@test.local", "short")
        assert result == 1

    def test_short_password_exact_boundary(self, session: Session) -> None:
        """Password of exactly 7 characters is rejected."""
        from src.cli import _reset_password

        result = _reset_password("anyone@test.local", "1234567")
        assert result == 1

    def test_minimum_length_password_accepted(self, session: Session) -> None:
        """Password of exactly 8 characters is accepted (if user exists)."""
        from src.repositories import user_repository
        from src.cli import _reset_password

        user = _make_user("boundary@test.local")
        session.add(user)
        session.commit()

        with patch("src.cli.Session") as MockSession:
            MockSession.return_value.__enter__ = lambda s: session
            MockSession.return_value.__exit__ = MagicMock(return_value=False)
            result = _reset_password("boundary@test.local", "12345678")

        assert result == 0

    def test_uses_user_service_layer(self, session: Session) -> None:
        """_reset_password delegates to user_service instead of repository access."""
        from src.cli import _reset_password

        with patch("src.cli.user_service.reset_password_by_email") as mock_reset:
            mock_reset.return_value = None
            with patch("src.cli.Session") as MockSession:
                MockSession.return_value.__enter__ = lambda s: session
                MockSession.return_value.__exit__ = MagicMock(return_value=False)
                result = _reset_password("service_layer@test.local", "newpassword1")

        assert result == 0
        mock_reset.assert_called_once_with("service_layer@test.local", "newpassword1", session)


class TestMainEntryPoint:
    def test_reset_password_subcommand_success(self, session: Session) -> None:
        """main() calls _reset_password and exits with its return code."""
        from src.cli import main

        with patch("src.cli._reset_password", return_value=0) as mock_reset:
            with patch("sys.argv", ["cli", "reset-password", "--username", "u@t.local", "--password", "newpass1"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0
        mock_reset.assert_called_once_with("u@t.local", "newpass1")

    def test_no_subcommand_exits_1(self) -> None:
        from src.cli import main

        with patch("sys.argv", ["cli"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1
