"""Support helpers for topology page data fetches and header actions."""

from typing import Awaitable, Callable

import httpx
from nicegui import ui

from src.ui.components.topology_layout_runtime import trigger_topology_layout_sync
from src.ui.components.topology_edit_toggle import render_edit_toggle
from src.ui.components.topology_layout_bar import render_layout_bar
from src.ui.components.topology_undo_bar import render_topology_undo_bar
from src.utils.logger import logger
from src.utils.settings import settings


async def _fetch_stencil_devices(token: str) -> list[dict[str, str | int]]:
    """Fetch all devices for the stencils panel inventory list."""
    headers = {"Authorization": f"Bearer {token}"}
    devices: list[dict[str, str | int]] = []
    try:
        async with httpx.AsyncClient() as client:
            page = 1
            while True:
                resp = await client.get(
                    f"{settings.api_base_url}/api/devices/",
                    params={"page": page, "limit": 100},
                    headers=headers,
                    timeout=5.0,
                )
                if resp.status_code != 200:
                    break
                items = resp.json().get("items", [])
                for item in items:
                    if isinstance(item, dict):
                        raw_version = item.get("version", 1)
                        devices.append(
                            {
                                "id": str(item.get("id", "")),
                                "name": str(item.get("name", "")),
                                "type": str(item.get("type", "")),
                                "ip": str(item.get("ip", "") or ""),
                                "version": int(raw_version)
                                if isinstance(raw_version, (int, str))
                                else 1,
                            }
                        )
                if len(items) < 100:
                    break
                page += 1
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Stencil device fetch failed: {error}", error=str(exc))
    return devices


async def _resolve_topology_id_from_layout(token: str, layout_id: str) -> str:
    """Resolve topology_id from a legacy layout_id deep link."""
    if not layout_id:
        return ""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.api_base_url}/api/diagrams/{layout_id}",
                headers=headers,
                timeout=5.0,
            )
        if resp.status_code != 200:
            return ""
        topology_value = resp.json().get("topology_id")
        return str(topology_value) if topology_value else ""
    except (httpx.HTTPError, httpx.TimeoutException):
        return ""


_FOCUS_DEVICE_JS_TEMPLATE = """
(function() {
    var targetId = __HT_DEVICE_ID__;
    if (!targetId) return;

    function isBridgeReady() {
        return !!(
            window._htDetailBridgeInit &&
            window.did_handshake === true &&
            window.socket &&
            window.socket.connected
        );
    }

    function dispatchNodeSelected(detail, attempt) {
        var currentAttempt = attempt || 0;
        if (!isBridgeReady()) {
            if (currentAttempt >= 50) return;
            setTimeout(function() { dispatchNodeSelected(detail, currentAttempt + 1); }, 100);
            return;
        }
        document.dispatchEvent(new CustomEvent('ht:node-selected', { detail: detail }));
    }

    function focus(attempt) {
        var currentAttempt = attempt || 0;
        if (!window._cy) {
            if (currentAttempt >= 50) return;
            setTimeout(function() { focus(currentAttempt + 1); }, 100);
            return;
        }

        var node = window._cy.getElementById(targetId);
        if (!node || !node.length) {
            dispatchNodeSelected({
                id: targetId,
                name: '',
                data: {}
            }, 0);
            return;
        }

        window._cy.nodes().unselect();
        node.select();
        window._cy.animate({ center: { eles: node } }, { duration: 220 });

        var detail = node.data();
        dispatchNodeSelected({
            id: node.id(),
            name: String(detail.label || ''),
            data: detail
        }, 0);
    }

    setTimeout(function() { focus(0); }, 0);
})();
"""


def _render_header_actions(
    token: str,
    user_role: str,
    refs: dict[str, object],
    topology_id: str,
    initial_diagram_id: str,
    initial_diagram_version: int | None,
    initial_draft_version: int | None,
    initial_has_unsaved_changes: bool,
) -> None:
    """Render history/save-version controls and edit toggle in the topology topbar."""
    render_layout_bar(
        token,
        user_role,
        topology_id=topology_id,
        initial_diagram_id=initial_diagram_id,
        initial_diagram_version=initial_diagram_version,
        initial_draft_version=initial_draft_version,
        initial_has_unsaved_changes=initial_has_unsaved_changes,
    )
    render_topology_undo_bar(user_role)
    ui.label("").props('id="ht-draft-badge"').style(
        "font-size:0.75rem; color:var(--ht-warning); font-weight:600;"
        " padding:2px 8px; border-radius:12px;"
        " background:color-mix(in srgb,var(--ht-warning) 15%,transparent); display:none;"
    )
    render_edit_toggle(
        user_role,
        on_enter_edit=_make_enter_edit(refs),
        on_exit_edit=_make_exit_edit(refs),
    )


def _make_enter_edit(
    refs: dict[str, object],
) -> Callable[[], Awaitable[None]]:
    async def _enter() -> None:
        palette_container = refs.get("palette")
        if palette_container is not None:
            palette_container.set_visibility(True)  # type: ignore[attr-defined]
        trigger_topology_layout_sync()
        await ui.run_javascript("htSetEditMode()")
        await ui.run_javascript(
            "if(!window._htEventsWired && window._htInitEventHandlers){"
            "window._htInitEventHandlers(window._htDeviceShapes||{});"
            "window._htEventsWired=true;}"
        )
        await ui.run_javascript(
            "if(window._htUpdateDraftBadge) window._htUpdateDraftBadge()"
        )

    return _enter


def _make_exit_edit(
    refs: dict[str, object],
) -> Callable[[], Awaitable[None]]:
    async def _exit() -> None:
        await ui.run_javascript(
            "if(window._htFlushAutosave) window._htFlushAutosave()"
        )
        palette_container = refs.get("palette")
        if palette_container is not None:
            palette_container.set_visibility(False)  # type: ignore[attr-defined]
        trigger_topology_layout_sync()
        await ui.run_javascript("htSetViewMode()")

    return _exit
