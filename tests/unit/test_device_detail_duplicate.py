"""Unit tests for src/ui/components/device_detail_duplicate.py."""

import uuid
from datetime import datetime, timezone

import pytest

from src.models.device import DeviceResponseEnriched
from src.models.types import DeviceStatus, DeviceType
from src.ui.components import device_detail_duplicate


def _device_for_duplicate(name: str, power_watts: int | None = None) -> DeviceResponseEnriched:
    now = datetime.now(timezone.utc)
    return DeviceResponseEnriched(
        id=uuid.uuid4(),
        name=name,
        type=DeviceType.Server,
        status=DeviceStatus.Active,
        ip=None,
        mac=None,
        os="Linux",
        notes="test",
        power_watts=power_watts,
        location_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object], text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict[str, object]:
        return self._payload


class TestDuplicateDevice:
    @pytest.mark.asyncio
    async def test_duplicate_device_fetches_all_name_pages_for_collision_resolution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created_device_id = uuid.uuid4()
        posted_payloads: list[dict[str, object]] = []
        fetched_pages: list[int] = []

        class _FakeAsyncClient:
            async def __aenter__(self) -> "_FakeAsyncClient":
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            async def get(
                self,
                url: str,
                params: dict[str, int] | None = None,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> _FakeResponse:
                del url, headers, timeout
                page = (params or {}).get("page", 1)
                fetched_pages.append(page)
                if page == 1:
                    return _FakeResponse(
                        200,
                        {
                            "items": [{"name": "Edge"}],
                            "total": 1001,
                        },
                    )
                if page == 2:
                    return _FakeResponse(
                        200,
                        {
                            "items": [{"name": "Edge (copy)"}],
                            "total": 1001,
                        },
                    )
                return _FakeResponse(200, {"items": [], "total": 1001})

            async def post(
                self,
                url: str,
                json: dict[str, object] | None = None,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> _FakeResponse:
                del headers, timeout
                posted_payloads.append({"url": url, "json": json or {}})
                if url.endswith("/api/devices/"):
                    return _FakeResponse(201, {"id": str(created_device_id)})
                return _FakeResponse(204, {})

        monkeypatch.setattr(device_detail_duplicate.httpx, "AsyncClient", _FakeAsyncClient)
        monkeypatch.setattr(device_detail_duplicate, "show_toast", lambda **kwargs: None)

        result = await device_detail_duplicate.duplicate_device(
            "fake-token",
            _device_for_duplicate("Edge", power_watts=95),
        )

        create_call = next(
            call for call in posted_payloads if str(call["url"]).endswith("/api/devices/")
        )
        create_payload = create_call["json"]

        assert result == created_device_id
        assert 2 in fetched_pages
        assert create_payload["name"] == "Edge (copy 2)"
        assert create_payload["power_watts"] == 95
