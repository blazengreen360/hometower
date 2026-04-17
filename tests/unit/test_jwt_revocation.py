"""Unit tests for JWT revocation and token versioning (SEC-1.1, SEC-4.4).

Tests cover:
- create_jwt appends jti and iat claims automatically
- decode_jwt rejects tokens missing version, jti, or iat
- increment_token_version in user_repository
- authenticate() return type tuple[str, int, str]
- revoke_tokens invalidates tokens
- change_own_password increments token_version
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from jose import JWTError
from sqlmodel import Session

from src.models.types import Role
from src.models.user import User
from src.utils.auth import create_jwt, decode_jwt, hash_password


class TestCreateJwt:
    def test_appends_jti_claim(self) -> None:
        token = create_jwt({"sub": "user-1", "role": "Admin", "version": 1})
        payload = decode_jwt(token)
        assert "jti" in payload

    def test_jti_is_uuid_string(self) -> None:
        token = create_jwt({"sub": "user-1", "role": "Admin", "version": 1})
        payload = decode_jwt(token)
        uuid.UUID(str(payload["jti"]))  # raises if not a valid UUID

    def test_appends_iat_claim(self) -> None:
        before = int(datetime.now(timezone.utc).timestamp())
        token = create_jwt({"sub": "user-1", "role": "Admin", "version": 1})
        after = int(datetime.now(timezone.utc).timestamp())
        payload = decode_jwt(token)
        assert before <= int(payload["iat"]) <= after

    def test_preserves_version_claim(self) -> None:
        token = create_jwt({"sub": "user-1", "role": "Admin", "version": 42})
        payload = decode_jwt(token)
        assert payload["version"] == 42

    def test_different_tokens_have_different_jti(self) -> None:
        t1 = create_jwt({"sub": "user-1", "role": "Admin", "version": 1})
        t2 = create_jwt({"sub": "user-1", "role": "Admin", "version": 1})
        p1 = decode_jwt(t1)
        p2 = decode_jwt(t2)
        assert p1["jti"] != p2["jti"]


class TestDecodeJwt:
    def test_raises_for_missing_version_claim(self) -> None:
        from jose import jwt as jose_jwt
        from src.utils.settings import settings
        token = jose_jwt.encode(
            {"sub": "u", "role": "Admin", "jti": "x", "iat": 1},
            settings.secret_key, algorithm="HS256",
        )
        with pytest.raises(JWTError, match="version"):
            decode_jwt(token)

    def test_raises_for_missing_jti_claim(self) -> None:
        from jose import jwt as jose_jwt
        from src.utils.settings import settings
        token = jose_jwt.encode(
            {"sub": "u", "role": "Admin", "version": 1, "iat": 1},
            settings.secret_key, algorithm="HS256",
        )
        with pytest.raises(JWTError, match="jti"):
            decode_jwt(token)

    def test_raises_for_missing_iat_claim(self) -> None:
        from jose import jwt as jose_jwt
        from src.utils.settings import settings
        token = jose_jwt.encode(
            {"sub": "u", "role": "Admin", "version": 1, "jti": "x"},
            settings.secret_key, algorithm="HS256",
        )
        with pytest.raises(JWTError, match="iat"):
            decode_jwt(token)

    def test_raises_for_missing_sub_claim(self) -> None:
        from jose import jwt as jose_jwt
        from src.utils.settings import settings
        token = jose_jwt.encode(
            {"role": "Admin", "version": 1, "jti": "x", "iat": 1},
            settings.secret_key, algorithm="HS256",
        )
        with pytest.raises(JWTError):
            decode_jwt(token)

    def test_accepts_complete_token(self) -> None:
        token = create_jwt({"sub": "user-1", "role": "Admin", "version": 1})
        payload = decode_jwt(token)
        assert payload["sub"] == "user-1"
        assert payload["role"] == "Admin"
        assert payload["version"] == 1


class TestIncrementTokenVersion:
    def test_increments_by_one(self, session: Session) -> None:
        from src.repositories.user_repository import increment_token_version
        user = User(
            username="vtest",
            email=f"vtest_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("x"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.token_version == 1

        increment_token_version(session, user.id)
        session.commit()
        session.refresh(user)
        assert user.token_version == 2

    def test_increments_repeatedly(self, session: Session) -> None:
        from src.repositories.user_repository import increment_token_version
        user = User(
            username="vtest2",
            email=f"vtest2_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("x"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()

        increment_token_version(session, user.id)
        session.commit()
        increment_token_version(session, user.id)
        session.commit()
        session.refresh(user)
        assert user.token_version == 3

    def test_nonexistent_user_is_noop(self, session: Session) -> None:
        from src.repositories.user_repository import increment_token_version
        # Must not raise
        increment_token_version(session, uuid.uuid4())
        session.commit()


class TestAuthenticate:
    def test_returns_three_tuple(self, session: Session) -> None:
        from src.services.auth_service import authenticate
        user = User(
            username="auth_tup",
            email=f"authtup_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("password123"),
            role=Role.Admin,
        )
        session.add(user)
        session.commit()

        result = authenticate(user.email, "password123", session)
        assert isinstance(result, tuple) and len(result) == 3

    def test_token_includes_version_claim(self, session: Session) -> None:
        from src.services.auth_service import authenticate
        user = User(
            username="auth_ver",
            email=f"authver_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("password123"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()

        token, _, _ = authenticate(user.email, "password123", session)
        payload = decode_jwt(token)
        assert payload["version"] == 1

    def test_returns_correct_role(self, session: Session) -> None:
        from src.services.auth_service import authenticate
        user = User(
            username="auth_role",
            email=f"authrole_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("password123"),
            role=Role.Admin,
        )
        session.add(user)
        session.commit()

        _, _, role = authenticate(user.email, "password123", session)
        assert role == Role.Admin.value

    def test_token_exp_is_future_unix_timestamp(self, session: Session) -> None:
        from src.services.auth_service import authenticate
        user = User(
            username="auth_exp",
            email=f"authexp_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("password123"),
            role=Role.Reader,
        )
        session.add(user)
        session.commit()

        _, token_exp, _ = authenticate(user.email, "password123", session)
        now = int(datetime.now(timezone.utc).timestamp())
        assert token_exp > now


class TestRevokeTokens:
    def test_increments_token_version(self, session: Session) -> None:
        from src.services.auth_service import revoke_tokens
        user = User(
            username="revoke_t",
            email=f"revoke_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("x"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.token_version == 1

        revoke_tokens(user.id, session)
        session.refresh(user)
        assert user.token_version == 2

    def test_change_is_committed(self, session: Session) -> None:
        from src.services.auth_service import revoke_tokens
        user = User(
            username="revoke_c",
            email=f"revokec_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("x"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()

        revoke_tokens(user.id, session)
        session.refresh(user)
        assert user.token_version == 2


class TestChangeOwnPasswordInvalidatesTokens:
    def test_token_version_incremented_after_password_change(self, session: Session) -> None:
        from src.services.auth_service import change_own_password
        user = User(
            username="pwver",
            email=f"pwver_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("oldpassword"),
            role=Role.Contributor,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.token_version == 1

        change_own_password(user.id, "oldpassword", "newpassword123", session)
        session.refresh(user)
        assert user.token_version == 2
