"""Execution tests for the device detail attachments section."""
from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
import uuid

import pytest

from tests.unit.nicegui_fakes import AsyncClientStub, FakeResponse, FakeUI, install_fake_ui


async def _invoke(handler):
    result = handler()
    if inspect.isawaitable(result):
        return await result
    return result


class TestDeviceDetailAttachmentsSection:
    def test_upload_accept_list_excludes_svg(self) -> None:
        import src.ui.components.device_detail_attachments_section as section_module

        assert ".svg" not in section_module._ACCEPT_EXTENSIONS

    def test_render_section_hides_upload_for_readers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_attachments_section as section_module
        from src.models.attachment import DeviceAttachmentResponse

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, section_module, fake_ui)
        monkeypatch.setattr(section_module, "show_toast", lambda **_kwargs: None)

        section_module.render_attachments_section(
            uuid.uuid4(),
            [
                DeviceAttachmentResponse(
                    id=uuid.uuid4(),
                    device_id=uuid.uuid4(),
                    filename="manual.pdf",
                    content_type="application/pdf",
                    size_bytes=1024,
                    created_at=section_module.datetime.now(section_module.timezone.utc),
                    is_image=False,
                    has_thumbnail=False,
                )
            ],
            token="reader-token",
            is_editor=False,
            on_change=lambda: None,
        )

        assert fake_ui.created["upload"] == []
        assert fake_ui.created["link"]

    def test_upload_posts_attachment_and_refreshes(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.ui.components.device_detail_attachments_section as section_module

        fake_ui = FakeUI()
        install_fake_ui(monkeypatch, section_module, fake_ui)

        toast_calls: list[dict[str, object]] = []
        monkeypatch.setattr(section_module, "show_toast", lambda **kwargs: toast_calls.append(kwargs))

        client_stub = AsyncClientStub([
            FakeResponse(status_code=201, payload={"id": str(uuid.uuid4())}, headers={"content-type": "application/json"})
        ])
        monkeypatch.setattr(section_module.httpx, "AsyncClient", lambda: client_stub)

        refreshed = {"count": 0}
        device_id = uuid.uuid4()

        section_module.render_attachments_section(
            device_id,
            [],
            token="token-123",
            is_editor=True,
            on_change=lambda: refreshed.__setitem__("count", refreshed["count"] + 1),
        )

        upload = fake_ui.created["upload"][0]

        class _AsyncUploadFile:
            name = "rack.png"

            async def read(self) -> bytes:
                return b"png-bytes"

        async def exercise() -> None:
            await _invoke(
                lambda: upload.handlers["upload"](
                    SimpleNamespace(file=_AsyncUploadFile())
                )
            )

        asyncio.run(exercise())

        assert client_stub.calls == [
            ("POST", f"{section_module.settings.api_base_url}/api/devices/{device_id}/attachments")
        ]
        uploaded_file = client_stub.call_kwargs[0]["files"]["file"]
        assert uploaded_file[0] == "rack.png"
        assert uploaded_file[1] == b"png-bytes"
        assert refreshed["count"] == 1
        assert any(call["title"] == "Attachment uploaded" for call in toast_calls)

    def test_format_file_size_uses_human_readable_units(self) -> None:
        import src.ui.components.device_detail_attachments_section as section_module

        assert section_module._format_file_size(512) == "512 B"
        assert section_module._format_file_size(1536) == "1.5 KB"
        assert section_module._format_file_size(10485760) == "10.0 MB"