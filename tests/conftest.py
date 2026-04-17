"""Shared test fixtures.

Environment variables are set BEFORE any src/ imports so that
pydantic-settings can load them without requiring a .env file on the test runner.
"""
import os
import warnings

warnings.filterwarnings(
    "ignore",
    message="'crypt' is deprecated and slated for removal in Python 3.13",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"cache could not write path .*",
    category=Warning,
)

# Must precede all src/ imports
os.environ.setdefault("DATABASE_URL", "postgresql://hometower:secret@localhost:5432/hometower")
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_minimum_32bytes!"
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ["ADMIN_PASSWORD"] = "testadminpass123"
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
from src.models.diagram import DiagramLayout  # noqa: E402, F401 — registers DiagramLayout with SQLModel.metadata
from src.models.connection import Connection  # noqa: E402, F401 — registers Connection with SQLModel.metadata
from src.models.location import Location  # noqa: E402, F401 — registers Location with SQLModel.metadata
from src.models.tag import Tag, DeviceTag  # noqa: E402, F401 — registers Tag/DeviceTag with SQLModel.metadata
from src.models.custom_field import CustomField  # noqa: E402, F401 — registers CustomField with SQLModel.metadata
from src.models.network import Network  # noqa: E402, F401 — registers Network with SQLModel.metadata
from src.models.device_network import DeviceNetwork  # noqa: E402, F401 — registers DeviceNetwork with SQLModel.metadata
from src.models.service import Service  # noqa: E402, F401 — registers Service with SQLModel.metadata
from src.models.service_dependency import ServiceDependency  # noqa: E402, F401 — registers ServiceDependency with SQLModel.metadata
from src.models.workspace import Workspace  # noqa: E402, F401 — registers Workspace with SQLModel.metadata
from src.models.topology import Topology  # noqa: E402, F401 — registers Topology with SQLModel.metadata
from src.models.topology_history_entry import TopologyHistoryEntry  # noqa: E402, F401 — registers TopologyHistoryEntry with SQLModel.metadata
from src.models.topology_personal_draft import TopologyPersonalDraft  # noqa: E402, F401 — registers TopologyPersonalDraft with SQLModel.metadata
from src.models.power_settings import PowerSettings  # noqa: E402, F401 — registers PowerSettings with SQLModel.metadata
from src.models.attachment import DeviceAttachment  # noqa: E402, F401 — registers DeviceAttachment with SQLModel.metadata
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
def client(session: Session, test_engine) -> Generator[TestClient, None, None]:  # type: ignore[type-arg]
    """Test client with DB overridden to SQLite and startup hooks patched.

    Also patches the engine reference inside AuthMiddleware so the token-version
    DB check uses the same in-memory SQLite database.
    """
    from src.api.app import app
    from src.utils.db import get_session
    import src.api.middleware.auth as _auth_mw

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session

    original_engine = _auth_mw.engine
    _auth_mw.engine = test_engine
    try:
        with patch("src.api.app._startup"):
            with TestClient(app) as test_client:
                yield test_client
    finally:
        _auth_mw.engine = original_engine

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Reset slowapi in-memory limiter storage before each test to prevent cross-test pollution."""
    from src.api.middleware.rate_limit import limiter
    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        limiter._storage.reset()


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Signed JWT backed by a real Admin user in the test DB."""
    return create_jwt({"sub": str(admin_user.id), "role": "Admin", "version": admin_user.token_version})


@pytest.fixture
def contributor_token(session: Session) -> str:
    """Signed JWT backed by a real Contributor user in the test DB."""
    user = User(
        username=f"contrib_tok_{uuid4().hex[:8]}",
        email=f"contrib_tok_{uuid4().hex[:8]}@token.local",
        password_hash=hash_password("x"),
        role=Role.Contributor,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return create_jwt({"sub": str(user.id), "role": "Contributor", "version": user.token_version})


@pytest.fixture
def reader_token(session: Session) -> str:
    """Signed JWT backed by a real Reader user in the test DB."""
    user = User(
        username=f"reader_tok_{uuid4().hex[:8]}",
        email=f"reader_tok_{uuid4().hex[:8]}@token.local",
        password_hash=hash_password("x"),
        role=Role.Reader,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return create_jwt({"sub": str(user.id), "role": "Reader", "version": user.token_version})


@pytest.fixture
def two_devices(client: TestClient, contributor_token: str) -> tuple[int, int]:
    """Create two devices and return their IDs."""
    headers = {"Authorization": f"Bearer {contributor_token}"}
    d1 = client.post("/api/devices/", json={"name": "Dev-1", "type": "Server"}, headers=headers)
    d2 = client.post("/api/devices/", json={"name": "Dev-2", "type": "Switch"}, headers=headers)
    assert d1.status_code == 201
    assert d2.status_code == 201
    return d1.json()["id"], d2.json()["id"]


@pytest.fixture
def admin_user(session: Session) -> User:
    """Real Admin user in the test DB — shared by admin_token and tests that need the object."""
    user = User(
        username=f"admin_tok_{uuid4().hex[:8]}",
        email=f"admin_tok_{uuid4().hex[:8]}@token.local",
        password_hash=hash_password("testadminpass123"),
        role=Role.Admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
