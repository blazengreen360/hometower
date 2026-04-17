"""Integration tests for HT-044 power APIs."""
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session

from src.models.power_settings import PowerSettings


_UNSET = object()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_rack(
    client: TestClient,
    token: str,
    *,
    name: str,
    parent_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, str] = {"name": name, "type": "rack"}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/api/locations/", json=payload, headers=_auth(token))
    assert response.status_code == 201, response.text
    return response.json()


def _create_device(
    client: TestClient,
    token: str,
    *,
    name: str,
    location_id: str | None = None,
    power_watts: object = _UNSET,
) -> dict[str, object]:
    payload: dict[str, object] = {"name": name, "type": "Server"}
    if location_id is not None:
        payload["location_id"] = location_id
    if power_watts is not _UNSET:
        payload["power_watts"] = power_watts
    response = client.post("/api/devices/", json=payload, headers=_auth(token))
    assert response.status_code == 201, response.text
    return response.json()


class TestPowerSummaryApi:
    def test_summary_reader_and_contributor_can_read(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        _create_device(
            client,
            contributor_token,
            name=f"power-summary-{uuid4().hex[:8]}",
            power_watts=10,
        )

        reader_resp = client.get("/api/power/summary", headers=_auth(reader_token))
        contributor_resp = client.get(
            "/api/power/summary", headers=_auth(contributor_token)
        )

        assert reader_resp.status_code == 200
        assert contributor_resp.status_code == 200

    def test_summary_aggregates_recursive_rollups_and_global_totals(
        self,
        client: TestClient,
        contributor_token: str,
        reader_token: str,
    ) -> None:
        baseline_response = client.get("/api/power/summary", headers=_auth(reader_token))
        assert baseline_response.status_code == 200, baseline_response.text
        baseline = baseline_response.json()

        suffix = uuid4().hex[:8]
        root = _create_rack(client, contributor_token, name=f"root-{suffix}")
        child = _create_rack(
            client,
            contributor_token,
            name=f"child-{suffix}",
            parent_id=str(root["id"]),
        )
        _create_rack(client, contributor_token, name=f"empty-{suffix}")

        _create_device(
            client,
            contributor_token,
            name=f"root-known-{suffix}",
            location_id=str(root["id"]),
            power_watts=100,
        )
        _create_device(
            client,
            contributor_token,
            name=f"child-known-{suffix}",
            location_id=str(child["id"]),
            power_watts=200,
        )
        _create_device(
            client,
            contributor_token,
            name=f"child-zero-{suffix}",
            location_id=str(child["id"]),
            power_watts=0,
        )
        _create_device(
            client,
            contributor_token,
            name=f"root-unknown-{suffix}",
            location_id=str(root["id"]),
        )
        _create_device(
            client,
            contributor_token,
            name=f"unassigned-known-{suffix}",
            power_watts=50,
        )

        response = client.get("/api/power/summary", headers=_auth(reader_token))
        assert response.status_code == 200, response.text

        payload = response.json()
        assert payload["total_watts"] == baseline["total_watts"] + 350
        assert payload["total_devices"] == baseline["total_devices"] + 5
        assert payload["devices_with_power"] == baseline["devices_with_power"] + 4
        assert (
            payload["devices_without_power"] == baseline["devices_without_power"] + 1
        )
        assert payload["estimated_monthly_cost"] is None
        assert payload["currency"] is None
        assert payload["cost_per_kwh"] is None

        by_location = payload["by_location"]
        assert len(by_location) == 2

        root_row = next(row for row in by_location if row["location_id"] == root["id"])
        child_row = next(
            row for row in by_location if row["location_id"] == child["id"]
        )

        assert root_row["total_watts"] == 300
        assert root_row["device_count"] == 3
        assert root_row["estimated_monthly_cost"] is None

        assert child_row["total_watts"] == 200
        assert child_row["device_count"] == 2
        assert child_row["estimated_monthly_cost"] is None

    def test_summary_applies_settings_rate_and_rounding(
        self,
        client: TestClient,
        contributor_token: str,
        admin_token: str,
        reader_token: str,
    ) -> None:
        put_response = client.put(
            "/api/power/settings",
            json={"cost_per_kwh": 0.12, "currency": "usd"},
            headers=_auth(admin_token),
        )
        assert put_response.status_code == 200
        assert put_response.json()["currency"] == "USD"

        baseline_response = client.get("/api/power/summary", headers=_auth(reader_token))
        assert baseline_response.status_code == 200, baseline_response.text
        baseline = baseline_response.json()

        _create_device(
            client,
            contributor_token,
            name=f"summary-cost-{uuid4().hex[:8]}",
            power_watts=1250,
        )

        summary_response = client.get("/api/power/summary", headers=_auth(reader_token))
        assert summary_response.status_code == 200
        summary = summary_response.json()

        assert summary["total_watts"] == baseline["total_watts"] + 1250
        assert (
            round(summary["estimated_monthly_kwh"] - baseline["estimated_monthly_kwh"], 2)
            == 913.2
        )

        assert summary["estimated_monthly_cost"] is not None
        assert baseline["estimated_monthly_cost"] is not None
        assert (
            round(
                summary["estimated_monthly_cost"] - baseline["estimated_monthly_cost"],
                2,
            )
            == pytest.approx(109.58, abs=0.01)
        )
        assert summary["currency"] == "USD"
        assert summary["cost_per_kwh"] == 0.12


class TestPowerSettingsApi:
    def test_get_settings_unconfigured_returns_nulls_for_admin(
        self,
        client: TestClient,
        admin_token: str,
        session: Session,
    ) -> None:
        existing = session.get(PowerSettings, "global")
        if existing is not None:
            session.delete(existing)
            session.commit()

        response = client.get("/api/power/settings", headers=_auth(admin_token))
        assert response.status_code == 200
        payload = response.json()
        assert payload["cost_per_kwh"] is None
        assert payload["currency"] is None
        assert payload["updated_at"] is None

    def test_reader_and_contributor_cannot_access_settings_endpoints(
        self,
        client: TestClient,
        reader_token: str,
        contributor_token: str,
    ) -> None:
        for token in (reader_token, contributor_token):
            get_response = client.get("/api/power/settings", headers=_auth(token))
            put_response = client.put(
                "/api/power/settings",
                json={"cost_per_kwh": 0.2, "currency": "USD"},
                headers=_auth(token),
            )
            assert get_response.status_code == 403
            assert put_response.status_code == 403

    def test_admin_can_upsert_and_clear_settings(
        self,
        client: TestClient,
        admin_token: str,
    ) -> None:
        set_response = client.put(
            "/api/power/settings",
            json={"cost_per_kwh": 0.15, "currency": "EUR"},
            headers=_auth(admin_token),
        )
        assert set_response.status_code == 200
        set_payload = set_response.json()
        assert set_payload["cost_per_kwh"] == 0.15
        assert set_payload["currency"] == "EUR"
        assert set_payload["updated_at"] is not None

        get_response = client.get("/api/power/settings", headers=_auth(admin_token))
        assert get_response.status_code == 200
        get_payload = get_response.json()
        assert get_payload["cost_per_kwh"] == 0.15
        assert get_payload["currency"] == "EUR"
        assert get_payload["updated_at"] is not None

        clear_response = client.put(
            "/api/power/settings",
            json={"cost_per_kwh": None, "currency": None},
            headers=_auth(admin_token),
        )
        assert clear_response.status_code == 200
        clear_payload = clear_response.json()
        assert clear_payload["cost_per_kwh"] is None
        assert clear_payload["currency"] is None

    def test_settings_pair_invariant_rejects_partial_payload(
        self,
        client: TestClient,
        admin_token: str,
    ) -> None:
        only_cost = client.put(
            "/api/power/settings",
            json={"cost_per_kwh": 0.15},
            headers=_auth(admin_token),
        )
        assert only_cost.status_code == 422
        assert (
            only_cost.json()["detail"]
            == "cost_per_kwh and currency must be provided together"
        )

        only_currency = client.put(
            "/api/power/settings",
            json={"currency": "USD"},
            headers=_auth(admin_token),
        )
        assert only_currency.status_code == 422
        assert (
            only_currency.json()["detail"]
            == "cost_per_kwh and currency must be provided together"
        )
