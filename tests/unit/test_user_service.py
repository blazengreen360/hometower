"""Unit tests for src/services/user_service.py."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models.types import Role
from src.models.user import User, UserCreate, UserUpdate
from src.services import user_service


def _make_user(
    *,
    role: Role = Role.Contributor,
    email: str = "user@test.local",
    password_hash: str = "hashed",
    is_active: bool = True,
) -> User:
    return User(
        id=uuid.uuid4(),
        username=email.split("@")[0],
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
    )


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


class TestCreateUser:
    def test_short_password_raises_422(self, session: Session) -> None:
        data = UserCreate(
            username="alice", email="alice@test.local", password="short"
        )
        with pytest.raises(HTTPException) as exc_info:
            user_service.create_user(data, session)
        assert exc_info.value.status_code == 422

    def test_short_password_message(self, session: Session) -> None:
        data = UserCreate(
            username="alice", email="alice@test.local", password="abc"
        )
        with pytest.raises(HTTPException) as exc_info:
            user_service.create_user(data, session)
        assert "8 characters" in exc_info.value.detail

    def test_duplicate_email_raises_409(self, session: Session) -> None:
        data = UserCreate(
            username="alice", email="alice@test.local", password="password123"
        )
        user_service.create_user(data, session)
        with pytest.raises(HTTPException) as exc_info:
            user_service.create_user(data, session)
        assert exc_info.value.status_code == 409

    def test_duplicate_email_message(self, session: Session) -> None:
        data = UserCreate(
            username="bob", email="bob@test.local", password="password123"
        )
        user_service.create_user(data, session)
        with pytest.raises(HTTPException) as exc_info:
            user_service.create_user(data, session)
        assert "already registered" in exc_info.value.detail

    def test_success_returns_user_response(self, session: Session) -> None:
        data = UserCreate(
            username="carol", email="carol@test.local", password="securepass"
        )
        result = user_service.create_user(data, session)
        assert result.email == "carol@test.local"
        assert result.username == "carol"
        assert result.id is not None

    def test_password_is_hashed(self, session: Session) -> None:
        """The stored password_hash must not equal the plaintext password."""
        from src.repositories import user_repository

        data = UserCreate(
            username="dave", email="dave@test.local", password="plaintext1"
        )
        result = user_service.create_user(data, session)
        stored = user_repository.get_by_id(session, result.id)
        assert stored is not None
        assert stored.password_hash != "plaintext1"
        assert len(stored.password_hash) > 20  # bcrypt hash is long

    def test_response_never_exposes_password_hash(self, session: Session) -> None:
        data = UserCreate(
            username="eve", email="eve@test.local", password="password99"
        )
        result = user_service.create_user(data, session)
        assert not hasattr(result, "password_hash")


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------


class TestUpdateUser:
    def test_not_found_raises_404(self, session: Session) -> None:
        with pytest.raises(HTTPException) as exc_info:
            user_service.update_user(uuid.uuid4(), UserUpdate(), session)
        assert exc_info.value.status_code == 404

    def test_email_conflict_raises_409(self, session: Session) -> None:
        u1 = UserCreate(
            username="f1", email="f1@test.local", password="password123"
        )
        u2 = UserCreate(
            username="f2", email="f2@test.local", password="password123"
        )
        r1 = user_service.create_user(u1, session)
        user_service.create_user(u2, session)
        with pytest.raises(HTTPException) as exc_info:
            user_service.update_user(
                r1.id, UserUpdate(email="f2@test.local"), session
            )
        assert exc_info.value.status_code == 409

    def test_short_password_raises_422(self, session: Session) -> None:
        data = UserCreate(
            username="g1", email="g1@test.local", password="password123"
        )
        r = user_service.create_user(data, session)
        with pytest.raises(HTTPException) as exc_info:
            user_service.update_user(r.id, UserUpdate(password="tiny"), session)
        assert exc_info.value.status_code == 422

    def test_same_email_does_not_conflict(self, session: Session) -> None:
        data = UserCreate(
            username="h1", email="h1@test.local", password="password123"
        )
        r = user_service.create_user(data, session)
        result = user_service.update_user(
            r.id, UserUpdate(email="h1@test.local"), session
        )
        assert result.email == "h1@test.local"

    def test_success_updates_fields(self, session: Session) -> None:
        data = UserCreate(
            username="i1", email="i1@test.local", password="password123"
        )
        r = user_service.create_user(data, session)
        result = user_service.update_user(
            r.id, UserUpdate(username="updated_name", role=Role.Admin), session
        )
        assert result.username == "updated_name"
        assert result.role == Role.Admin

    def test_role_change_increments_token_version(self, session: Session) -> None:
        data = UserCreate(
            username="tv_role", email="tv_role@test.local", password="password123"
        )
        r = user_service.create_user(data, session)

        user_service.update_user(r.id, UserUpdate(role=Role.Admin), session)

        updated = session.get(User, r.id)
        assert updated is not None
        assert updated.token_version == 2

    def test_is_active_change_increments_token_version(self, session: Session) -> None:
        data = UserCreate(
            username="tv_active", email="tv_active@test.local", password="password123"
        )
        r = user_service.create_user(data, session)

        user_service.update_user(r.id, UserUpdate(is_active=False), session)

        updated = session.get(User, r.id)
        assert updated is not None
        assert updated.token_version == 2

    def test_non_authz_updates_do_not_increment_token_version(self, session: Session) -> None:
        data = UserCreate(
            username="tv_name", email="tv_name@test.local", password="password123"
        )
        r = user_service.create_user(data, session)

        user_service.update_user(r.id, UserUpdate(username="tv_name_2"), session)

        updated = session.get(User, r.id)
        assert updated is not None
        assert updated.token_version == 1


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------


class TestDeleteUser:
    def test_self_delete_raises_400(self, session: Session) -> None:
        data = UserCreate(
            username="j1", email="j1@test.local", password="password123"
        )
        r = user_service.create_user(data, session)
        with pytest.raises(HTTPException) as exc_info:
            user_service.delete_user(r.id, str(r.id), session)
        assert exc_info.value.status_code == 400
        assert "own account" in exc_info.value.detail

    def test_last_admin_raises_400(self, session: Session) -> None:
        # Mock locking count query to return 1 — avoids DB state pollution from prior tests
        # (prior tests may have committed Admin users that weren't rolled back).
        from src.repositories import user_repository as repo_module

        data = UserCreate(
            username="k1", email="k1@test.local", password="password123",
            role=Role.Admin,
        )
        r = user_service.create_user(data, session)
        other_id = str(uuid.uuid4())
        with patch.object(repo_module, "count_by_role_for_update", return_value=1):
            with pytest.raises(HTTPException) as exc_info:
                user_service.delete_user(r.id, other_id, session)
        assert exc_info.value.status_code == 400
        assert "last admin" in exc_info.value.detail

    def test_last_admin_rule_without_stale_token_path(self, session: Session) -> None:
        existing_admins = session.exec(select(User).where(User.role == Role.Admin)).all()
        for existing in existing_admins:
            existing.role = Role.Reader
            session.add(existing)
        session.commit()

        admin = user_service.create_user(
            UserCreate(
                username="k2",
                email="k2@test.local",
                password="password123",
                role=Role.Admin,
            ),
            session,
        )
        requester = user_service.create_user(
            UserCreate(
                username="k3",
                email="k3@test.local",
                password="password123",
                role=Role.Reader,
            ),
            session,
        )

        with pytest.raises(HTTPException) as exc_info:
            user_service.delete_user(admin.id, str(requester.id), session)
        assert exc_info.value.status_code == 400
        assert "last admin" in exc_info.value.detail

    def test_not_found_raises_404(self, session: Session) -> None:
        with pytest.raises(HTTPException) as exc_info:
            user_service.delete_user(uuid.uuid4(), str(uuid.uuid4()), session)
        assert exc_info.value.status_code == 404

    def test_delete_non_last_admin_succeeds(self, session: Session) -> None:
        admin1 = UserCreate(
            username="l1", email="l1@test.local", password="password123",
            role=Role.Admin,
        )
        admin2 = UserCreate(
            username="l2", email="l2@test.local", password="password123",
            role=Role.Admin,
        )
        r1 = user_service.create_user(admin1, session)
        r2 = user_service.create_user(admin2, session)
        # Delete admin1 as admin2 — should succeed since admin2 is still an admin
        user_service.delete_user(r1.id, str(r2.id), session)
        with pytest.raises(HTTPException) as exc_info:
            user_service.get_user(r1.id, session)
        assert exc_info.value.status_code == 404

    def test_delete_contributor_succeeds(self, session: Session) -> None:
        data = UserCreate(
            username="m1", email="m1@test.local", password="password123",
            role=Role.Contributor,
        )
        r = user_service.create_user(data, session)
        user_service.delete_user(r.id, str(uuid.uuid4()), session)
        with pytest.raises(HTTPException) as exc_info:
            user_service.get_user(r.id, session)
        assert exc_info.value.status_code == 404
