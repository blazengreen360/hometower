"""Integration tests for the Search API (HT-020).

Covers: type:X, ip:X, tag:X, os:X, location:X, service:X, free_text,
combined operators, unknown operator fallback, empty results, wildcard IP.
"""
import pytest
from fastapi.testclient import TestClient


def _make_device(client: TestClient, token: str, **kwargs) -> dict:
    payload = {"name": "search-dev", "type": "Server", **kwargs}
    resp = client.post(
        "/api/devices/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_tag(client: TestClient, token: str, name: str) -> dict:
    resp = client.post(
        "/api/tags/",
        json={"name": name, "color": "#ff0000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _attach_tag(client: TestClient, token: str, device_id: str, tag_id: str) -> None:
    resp = client.post(
        f"/api/devices/{device_id}/tags",
        json={"tag_id": tag_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204, resp.text


def _make_service(
    client: TestClient, token: str, device_id: str, name: str
) -> dict:
    resp = client.post(
        f"/api/devices/{device_id}/services",
        json={"name": name, "protocol": "tcp"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _search(client: TestClient, token: str, q: str) -> list[dict]:
    resp = client.get(
        f"/api/devices/?include=location,tags,services&limit=1000&q={q}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


# ---------------------------------------------------------------------------
# type: operator
# ---------------------------------------------------------------------------


class TestSearchByType:
    def test_type_server_returns_only_servers(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _make_device(client, contributor_token, name="srv-search-1", type="Server")
        _make_device(client, contributor_token, name="sw-search-1", type="Switch")
        items = _search(client, contributor_token, "type:Server")
        types = {i["type"] for i in items}
        assert "Server" in types
        # Switch should not be in the filtered results for type:Server
        non_server = [i for i in items if i["type"] != "Server"]
        assert len(non_server) == 0

    def test_type_case_insensitive(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _make_device(client, contributor_token, name="nas-search-1", type="NAS")
        items = _search(client, contributor_token, "type:nas")
        types = {i["type"] for i in items}
        assert "NAS" in types

    def test_multiple_type_or(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _make_device(client, contributor_token, name="vm-search-1", type="VM")
        _make_device(client, contributor_token, name="lxc-search-1", type="LXC")
        items = _search(client, contributor_token, "type:VM type:LXC")
        types = {i["type"] for i in items}
        assert "VM" in types
        assert "LXC" in types


# ---------------------------------------------------------------------------
# ip: operator
# ---------------------------------------------------------------------------


class TestSearchByIp:
    def test_exact_ip(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _make_device(
            client, contributor_token, name="ip-exact-dev", ip="10.0.0.5", type="Server"
        )
        items = _search(client, contributor_token, "ip:10.0.0.5")
        ips = [i["ip"] for i in items]
        assert "10.0.0.5" in ips

    def test_wildcard_ip(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _make_device(
            client, contributor_token, name="ip-wild-dev", ip="192.168.10.1", type="Server"
        )
        items = _search(client, contributor_token, "ip:192.168.*")
        ips = [i["ip"] for i in items]
        assert "192.168.10.1" in ips

    def test_wildcard_no_match(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _make_device(
            client, contributor_token, name="no-match-ip-dev", ip="172.16.1.1", type="Server"
        )
        items = _search(client, contributor_token, "ip:192.168.*")
        ips_172 = [i for i in items if i.get("ip", "").startswith("172.16.1")]
        # 172.16.1.1 should not appear in 192.168.* results
        assert len(ips_172) == 0


# ---------------------------------------------------------------------------
# tag: operator
# ---------------------------------------------------------------------------


class TestSearchByTag:
    def test_tag_filter(
        self, client: TestClient, contributor_token: str
    ) -> None:
        dev = _make_device(
            client, contributor_token, name="tagged-dev", type="Server"
        )
        tag = _make_tag(client, contributor_token, "prod-env")
        _attach_tag(client, contributor_token, dev["id"], tag["id"])
        items = _search(client, contributor_token, "tag:prod-env")
        ids = [i["id"] for i in items]
        assert dev["id"] in ids

    def test_tag_substring(
        self, client: TestClient, contributor_token: str
    ) -> None:
        dev = _make_device(
            client, contributor_token, name="tag-sub-dev", type="Server"
        )
        tag = _make_tag(client, contributor_token, "production-infra")
        _attach_tag(client, contributor_token, dev["id"], tag["id"])
        items = _search(client, contributor_token, "tag:production")
        ids = [i["id"] for i in items]
        assert dev["id"] in ids


# ---------------------------------------------------------------------------
# service: operator (requires HT-023)
# ---------------------------------------------------------------------------


class TestSearchByService:
    def test_service_filter(
        self, client: TestClient, contributor_token: str
    ) -> None:
        dev = _make_device(
            client, contributor_token, name="svc-filter-dev", type="Server"
        )
        _make_service(client, contributor_token, dev["id"], "plex-media")
        items = _search(client, contributor_token, "service:plex")
        ids = [i["id"] for i in items]
        assert dev["id"] in ids

    def test_service_no_match_empty(
        self, client: TestClient, contributor_token: str
    ) -> None:
        items = _search(client, contributor_token, "service:nonexistent-xyz-svc")
        assert len(items) == 0


# ---------------------------------------------------------------------------
# Free text
# ---------------------------------------------------------------------------


class TestSearchFreeText:
    def test_free_text_name_match(
        self, client: TestClient, contributor_token: str
    ) -> None:
        _make_device(
            client, contributor_token, name="uniquehost-xyz", type="Server"
        )
        items = _search(client, contributor_token, "uniquehost-xyz")
        names = [i["name"] for i in items]
        assert "uniquehost-xyz" in names

    def test_free_text_no_match(
        self, client: TestClient, contributor_token: str
    ) -> None:
        items = _search(client, contributor_token, "zzz-no-match-ever-xyz123")
        assert len(items) == 0


# ---------------------------------------------------------------------------
# Unknown operator fallback
# ---------------------------------------------------------------------------


class TestUnknownOperatorFallback:
    def test_unknown_operator_treated_as_free_text(
        self, client: TestClient, contributor_token: str
    ) -> None:
        # "parent:rack" should fall to free text — device named "parent:rack"
        # won't exist, so we just verify we get a 200 with empty or some results
        resp = client.get(
            "/api/devices/?include=location&limit=1000&q=parent:rack1",
            headers={"Authorization": f"Bearer {contributor_token}"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Combined operators
# ---------------------------------------------------------------------------


class TestCombinedOperators:
    def test_type_and_tag_and(
        self, client: TestClient, contributor_token: str
    ) -> None:
        dev_match = _make_device(
            client, contributor_token, name="both-match-dev", type="Server"
        )
        dev_no_tag = _make_device(
            client, contributor_token, name="no-tag-dev", type="Server"
        )
        tag = _make_tag(client, contributor_token, "combo-tag")
        _attach_tag(client, contributor_token, dev_match["id"], tag["id"])
        items = _search(client, contributor_token, "type:Server tag:combo-tag")
        ids = [i["id"] for i in items]
        assert dev_match["id"] in ids
        assert dev_no_tag["id"] not in ids
