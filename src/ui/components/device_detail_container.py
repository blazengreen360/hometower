"""Container rendering helpers extracted from device_detail_panel.py (HT-021).

Provides API fetch helpers and hierarchical breadcrumb/children renderers
so that device_detail_panel.py stays under the 250-line limit.
"""
import html
import uuid
from collections.abc import Awaitable, Callable
from typing import Optional

import httpx
from nicegui import ui

from src.models.attachment import DeviceAttachmentResponse
from src.models.connection import ConnectionResponse
from src.models.device import DeviceResponse, DeviceResponseEnriched
from src.models.network import NetworkListResponse
from src.models.tag import TagResponse
from src.utils.logger import logger
from src.utils.settings import settings


async def _api_get_device(
    token: str, device_id: uuid.UUID, include: str = ""
) -> Optional[DeviceResponseEnriched]:
    params = {"include": include} if include else {}
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{settings.api_base_url}/api/devices/{device_id}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        if r.status_code == 200:
            return DeviceResponseEnriched.model_validate(r.json())
        logger.warning("Device fetch {}: {}", device_id, r.status_code)
    except httpx.HTTPError as exc:
        logger.error("Panel device fetch: {}", str(exc))
    return None


async def _api_get_connections(
    token: str, device_id: uuid.UUID
) -> list[ConnectionResponse]:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{settings.api_base_url}/api/devices/{device_id}/connections",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        if r.status_code == 200:
            return [ConnectionResponse.model_validate(x) for x in r.json()]
    except httpx.HTTPError as exc:
        logger.error("Panel connections fetch: {}", str(exc))
    return []


async def _api_get_attachments(
    token: str, device_id: uuid.UUID
) -> list[DeviceAttachmentResponse]:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{settings.api_base_url}/api/devices/{device_id}/attachments",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
        if r.status_code == 200:
            return [DeviceAttachmentResponse.model_validate(item) for item in r.json()]
    except httpx.HTTPError as exc:
        logger.error("Panel attachments fetch: {}", str(exc))
    return []


async def _api_get_all_tags(token: str) -> list[TagResponse]:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{settings.api_base_url}/api/tags/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        if r.status_code == 200:
            return [TagResponse.model_validate(t) for t in r.json()]
    except httpx.HTTPError as exc:
        logger.error("Panel tags fetch: {}", str(exc))
    return []


async def _api_get_all_networks(token: str) -> list[NetworkListResponse]:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{settings.api_base_url}/api/networks/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        if r.status_code == 200:
            return [NetworkListResponse.model_validate(t) for t in r.json()]
    except httpx.HTTPError as exc:
        logger.error("Panel networks fetch: {}", str(exc))
    return []


def render_parent_breadcrumb(
    parent_chain: list[DeviceResponse],
    state: dict[str, object],
    refresh_fn: Callable[[], Awaitable[None]],
) -> None:
    """Render 'Inside: → ancestor chain' breadcrumb row. No-op when chain is empty."""
    if not parent_chain:
        return
    with ui.row().classes("w-full items-center gap-1").style(
        "font-size:0.8rem; color:var(--ht-text-secondary); flex-wrap:wrap;"
    ):
        ui.label("Inside:").style("color:var(--ht-text-secondary);")
        for i, ancestor in enumerate(reversed(parent_chain)):
            if i > 0:
                ui.label("→").style("color:var(--ht-text-secondary);")

            async def _select_ancestor(
                aid: uuid.UUID = ancestor.id,
            ) -> None:
                state["device_id"] = aid
                await refresh_fn()

            ui.button(
                html.escape(ancestor.name), on_click=_select_ancestor
            ).props(
                'flat dense no-caps aria-label="Navigate to ancestor"'
            ).style(
                "color:var(--ht-accent); padding:0; min-height:0;"
            )


def render_children_section(
    children_list: list[DeviceResponse],
    state: dict[str, object],
    refresh_fn: Callable[[], Awaitable[None]],
) -> None:
    """Render expandable children list. No-op when children_list is empty."""
    if not children_list:
        return
    with ui.expansion(
        f"Children ({len(children_list)})",
        icon="account_tree",
        value=True,
    ).classes("w-full"):
        with ui.element("div").props('aria-label="Child devices"').classes("w-full"):
            for child in children_list:

                async def _select_child(
                    cid: uuid.UUID = child.id,
                ) -> None:
                    state["device_id"] = cid
                    await refresh_fn()

                with ui.row().classes("w-full items-center gap-2").style(
                    "padding:4px 0;"
                ):
                    ui.icon("device_hub").style(
                        "font-size:1rem; color:var(--ht-text-secondary);"
                    )
                    ui.button(
                        html.escape(child.name), on_click=_select_child
                    ).props(
                        'flat dense no-caps aria-label="Navigate to child device"'
                    ).style(
                        "color:var(--ht-text-primary); padding:0; min-height:0;"
                    )
