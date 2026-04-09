"""Shared test fixtures.

Environment variables are set BEFORE any src/ imports so that
pydantic-settings can load them without requiring a .env file on the test runner.
"""
import os

# Must precede all src/ imports
os.environ.setdefault("DATABASE_URL", "postgresql://hometower:secret@localhost:5432/hometower")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only_minimum_32bytes!")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD", "testadminpass123")
os.environ.setdefault("JWT_EXPIRE_HOURS", "24")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from typing import Generator  # noqa: E402
from unittest.mock import patch  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from src.models.user import User  # noqa: E402, F401 — registers User with SQLModel.metadata
from src.models.device import Device  # noqa: E402, F401 — registers Device with SQLModel.metadata
from src.models.types import Role  # noqa: E402
from src.utils.auth import create_jwt, hash_password  # noqa: E402

TEST_DATABASE_URL = "sqlite://"  # in-memory SQLite; no PostgreSQL needed for tests


@pytest.fixture(scope="session")
def test_engine():
    """Create an in-memory SQLite engine and build all tables once per session."""
    eng = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)


@pytest.fixture
def session(test_engine) -> Generator[Session, None, None]:  # type: ignore[type-arg]
    """Provide a fresh session that rolls back after each test."""
    with Session(test_engine) as s:
        yield s
        s.rollback()


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    """Test client with DB overridden to SQLite and startup hooks patched."""
    from src.api.app import app
    from src.utils.db import get_session

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session

    with patch("src.api.app._startup"):
        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_token() -> str:
    """Signed JWT for an Admin user — bypasses bcrypt."""
    return create_jwt({"sub": str(uuid4()), "role": "Admin"})


@pytest.fixture
def contributor_token() -> str:
    """Signed JWT for a Contributor user."""
    return create_jwt({"sub": str(uuid4()), "role": "Contributor"})


@pytest.fixture
def reader_token() -> str:
    """Signed JWT for a Reader user."""
    return create_jwt({"sub": str(uuid4()), "role": "Reader"})


@pytest.fixture
def admin_user(session: Session) -> User:
    """Persist an admin user and return it."""
    user = User(
        username="admin",
        email="admin@test.local",
        password_hash=hash_password("testadminpass123"),
        role=Role.Admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
