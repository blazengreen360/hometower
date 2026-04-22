"""Integration tests for connection owner-scope enforcement."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.connection import Connection
from src.models.types import ConnectionType, Role
from src.models.user import User
from src.utils.auth import create_jwt, hash_password


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(session: Session, role: Role) -> tuple[User, str]:
    user = User(
        username=f"connection_scope_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@connection-scope.local",
        password_hash=hash_password("x"),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_jwt(
        {"sub": str(user.id), "role": role.value, "version": user.token_version}
    )
    return user, token


def _create_device(client: TestClient, token: str, name: str) -> dict[str, object]:
    response = client.post(
        "/api/devices/",
        json={"name": name, "type": "Server"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_mixed_owner_connection(
    session: Session,
    source_id: str,
    target_id: str,
) -> Connection:
    connection = Connection(
        source_id=uuid.UUID(source_id),
        target_id=uuid.UUID(target_id),
        type=ConnectionType.Ethernet,
    )
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


class TestConnectionOwnerScope:
    def test_create_rejects_mixed_owner_devices(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_token = _make_user(session, Role.Contributor)

        owner_device = _create_device(client, owner_token, "owner-connection-source")
        foreign_device = _create_device(client, foreign_token, "foreign-connection-target")

        response = client.post(
            "/api/connections/",
            json={
                "source_id": owner_device["id"],
                "target_id": foreign_device["id"],
                "type": "Ethernet",
            },
            headers=_auth(owner_token),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Target device not found"

    def test_list_routes_hide_mixed_owner_connections(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_token = _make_user(session, Role.Contributor)

        owner_device = _create_device(client, owner_token, "owner-list-device")
        foreign_device = _create_device(client, foreign_token, "foreign-list-device")
        connection = _seed_mixed_owner_connection(
            session,
            str(owner_device["id"]),
            str(foreign_device["id"]),
        )

        list_response = client.get("/api/connections/", headers=_auth(owner_token))
        assert list_response.status_code == 200
        assert list_response.json()["items"] == []
        assert list_response.json()["total"] == 0

        device_response = client.get(
            f"/api/devices/{owner_device['id']}/connections",
            headers=_auth(owner_token),
        )
        assert device_response.status_code == 200
        assert device_response.json() == []

        filtered_response = client.get(
            f"/api/connections/?source_id={connection.source_id}",
            headers=_auth(owner_token),
        )
        assert filtered_response.status_code == 200
        assert filtered_response.json()["items"] == []

    def test_get_update_and_delete_return_404_for_mixed_owner_connection(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        _, owner_token = _make_user(session, Role.Contributor)
        _, foreign_token = _make_user(session, Role.Contributor)

        owner_device = _create_device(client, owner_token, "owner-mutate-device")
        foreign_device = _create_device(client, foreign_token, "foreign-mutate-device")
        connection = _seed_mixed_owner_connection(
            session,
            str(owner_device["id"]),
            str(foreign_device["id"]),
        )

        get_response = client.get(
            f"/api/connections/{connection.id}",
            headers=_auth(owner_token),
        )
        assert get_response.status_code == 404

        update_response = client.patch(
            f"/api/connections/{connection.id}",
            json={"label": "hidden"},
            headers=_auth(owner_token),
        )
        assert update_response.status_code == 404

        delete_response = client.delete(
            f"/api/connections/{connection.id}",
            headers=_auth(owner_token),
        )
        assert delete_response.status_code == 404