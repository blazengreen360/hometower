"""Read-only IPAM page at /ipam (HT-024)."""
from __future__ import annotations

import json

from nicegui import app as nicegui_app
from nicegui import ui
from nicegui.element import Element
from nicegui.events import ValueChangeEventArguments

from src.models.ipam import IpamNetworkDetailResponse, IpamNetworkListResponse
from src.models.types import IpamRenderMode
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_unauthenticated
from src.ui.components.ipam_block_summary import render_ipam_block_summary
from src.ui.components.ipam_grid import render_ipam_grid
from src.ui.components.ipam_stats_row import render_ipam_stats_row
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import page_container
from src.ui.design.primitives import render_page_intro
from src.ui.services.ipam_data import load_ipam_detail, load_ipam_summary
from src.ui.services.ipam_search import IpamSearchTargets, resolve_visible_matches


@ui.page("/ipam")
async def ipam_page() -> None:
    """Render read-only IP utilization maps for visible networks."""
    if redirect_if_unauthenticated(current_path="/ipam"):
        return

    token: str = nicegui_app.storage.user.get("access_token", "")
    summary_payload: IpamNetworkListResponse = await load_ipam_summary(token)

    query: str = ""
    details_by_network: dict[str, IpamNetworkDetailResponse] = {}
    search_targets: dict[str, IpamSearchTargets] = {}
    detail_containers: dict[str, Element] = {}

    def _open_device(device_id: str) -> None:
        ui.navigate.to(f"/topology?device_id={device_id}")

    def _refresh_search_targets() -> None:
        search_targets.clear()
        search_targets.update(resolve_visible_matches(query, details_by_network))

    def _render_network_detail(network_key: str) -> None:
        container = detail_containers.get(network_key)
        if container is None:
            return
        detail = details_by_network.get(network_key)
        if detail is None:
            return

        targets = search_targets.get(network_key, IpamSearchTargets())
        container.clear()
        with container:
            if detail.network.render_mode == IpamRenderMode.grid:
                render_ipam_grid(detail, targets, _open_device, network_key)
                return

            if detail.network.render_mode == IpamRenderMode.block_summary:
                render_ipam_block_summary(detail, targets, _open_device, network_key)
                return

            ui.label(detail.network.unsupported_reason or "Unsupported network type").style(
                "color:var(--ht-text-secondary);"
            )

    async def _scroll_to_first_match() -> None:
        for network in summary_payload.items:
            target = search_targets.get(str(network.network_id))
            if target is None or target.scroll_target_id is None:
                continue
            script = (
                "(function(){"
                f"var el=document.getElementById({json.dumps(target.scroll_target_id)});"
                "if(el){el.scrollIntoView({behavior:'smooth', block:'center'});}"
                "})();"
            )
            await ui.run_javascript(script)
            return

    async def _on_search_change(event: ValueChangeEventArguments) -> None:
        nonlocal query
        query = event.value or ""
        _refresh_search_targets()
        for network_key in details_by_network:
            _render_network_detail(network_key)
        await _scroll_to_first_match()

    async def _load_detail_if_needed(network_key: str) -> None:
        if network_key in details_by_network:
            _render_network_detail(network_key)
            return

        detail = await load_ipam_detail(token, network_key)
        if detail is None:
            ui.notify("Unable to load network detail", type="negative")
            return

        details_by_network[network_key] = detail
        _refresh_search_targets()
        _render_network_detail(network_key)
        await _scroll_to_first_match()

    with app_shell("IPAM", "/ipam", breadcrumb=["IPAM"]):
        with page_container(ui.column()):
            with ui.row().classes("w-full items-end justify-between gap-3 flex-wrap"):
                render_page_intro(
                    ui,
                    "IPAM",
                    "Inspect network utilization, conflicts, and device occupancy in a read-only address-management surface.",
                    "Network View",
                )
                ui.badge("Read-only").classes("bg-[var(--ht-bg-surface-raised)] text-[var(--ht-text-secondary)]")

            ui.input(placeholder="Search by IP or device name...").props("outlined debounce=200").classes(
                "w-full"
            ).on_value_change(_on_search_change)

            render_ipam_stats_row(summary_payload.summary)

            if not summary_payload.items:
                with card_surface(ui.card()):
                    with card_section(ui.column()):
                        ui.label("No networks found.").classes("ht-muted-copy")
                return

            for network in summary_payload.items:
                network_key = str(network.network_id)
                title = f"{network.name} ({network.cidr})"
                with ui.expansion(title, value=False).classes("w-full") as expansion:
                    with ui.row().classes("w-full items-center gap-2"):
                        if network.vlan_id is not None:
                            ui.badge(f"VLAN {network.vlan_id}").props("rounded")
                        utilization = (
                            f"{network.used_ip_count}/{network.usable_ip_count} used"
                            if network.usable_ip_count is not None
                            else "Unsupported"
                        )
                        ui.label(utilization).classes("ht-small-copy")
                        if network.conflict_ip_count > 0:
                            ui.badge(f"{network.conflict_ip_count} conflicts", color="negative").props(
                                "rounded"
                            )
                        if network.render_mode == IpamRenderMode.block_summary:
                            ui.badge("Block Summary", color="info").props("rounded")
                        if network.render_mode == IpamRenderMode.unsupported:
                            ui.badge("Unsupported", color="grey").props("rounded")

                    detail_containers[network_key] = ui.column().classes("w-full gap-2")

                async def _on_expansion_change(
                    event: ValueChangeEventArguments,
                    key: str = network_key,
                ) -> None:
                    if bool(event.value):
                        await _load_detail_if_needed(key)

                expansion.on_value_change(_on_expansion_change)
