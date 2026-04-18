"""Networks section renderer for the device detail panel."""
import html
import uuid
from collections.abc import Callable

import httpx
from nicegui import ui

from src.models.device_network import DeviceNetworkNetworkRef
from src.models.network import NetworkListResponse
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import danger_button
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import secondary_button
from src.utils.logger import logger
from src.utils.settings import settings


def _network_label(network: NetworkListResponse) -> str:
    if network.vlan_id is None:
        return f"{network.name} ({network.cidr})"
    return f"{network.name} (VLAN {network.vlan_id}, {network.cidr})"


def render_networks_section(
    device_id: uuid.UUID,
    networks: list[DeviceNetworkNetworkRef],
    all_networks: list[NetworkListResponse],
    token: str,
    is_editor: bool,
    on_change: Callable[[], None],
) -> None:
    """Render network memberships and attach/detach controls for editors."""
    if not networks and not is_editor:
        ui.label("No networks").style("font-size:0.875rem; color:var(--ht-text-secondary);")
        return

    with ui.row().classes("flex-wrap gap-1"):
        for membership in networks:
            base_label = html.escape(membership.name)
            vlan = f"VLAN {membership.vlan_id}" if membership.vlan_id is not None else "No VLAN"
            text = f"{base_label} • {vlan} • {html.escape(membership.ip_address)}"
            with ui.row().classes("items-center gap-1").style(
                f"background:{membership.color}; border-radius: var(--ht-radius-pill);"
                " padding:3px 10px; max-width:fit-content;"
            ):
                ui.label(text).style(
                    "font-size:0.75rem; color:var(--ht-text-on-accent); font-weight:500;"
                )
                if is_editor:
                    confirm_dlg = ui.dialog()

                    async def _detach(
                        network_id: uuid.UUID = membership.network_id,
                        dlg=confirm_dlg,
                    ) -> None:
                        try:
                            async with httpx.AsyncClient() as c:
                                r = await c.delete(
                                    f"{settings.api_base_url}/api/devices/{device_id}/networks/{network_id}",
                                    headers={"Authorization": f"Bearer {token}"},
                                    timeout=5.0,
                                )
                            if r.status_code not in (200, 204):
                                ui.notify("Detach failed", type="negative")
                                return
                        except httpx.HTTPError as exc:
                            logger.error("Network detach: {}", str(exc))
                            ui.notify("Connection error", type="negative")
                            return
                        dlg.close()
                        on_change()

                    with confirm_dlg:
                        with card_surface(ui.card()).classes("min-w-[320px]"):
                            with card_section(ui.column()):
                                ui.label(
                                    f"Remove {html.escape(membership.name)} from this device?"
                                ).classes("ht-section-title")
                                with ui.row().classes("justify-end gap-2"):
                                    secondary_button(ui.button("Cancel", on_click=confirm_dlg.close))
                                    danger_button(ui.button("Remove", on_click=_detach))

                    ui.button(icon="close", on_click=lambda dlg=confirm_dlg: dlg.open()).props(
                        "flat dense round size=xs aria-label='Remove network membership'"
                    ).style("color:var(--ht-text-on-accent); padding:0;")

    if not is_editor:
        return

    attached_ids = {membership.network_id for membership in networks}
    available_networks = [n for n in all_networks if n.id not in attached_ids]

    ui.separator()
    if not available_networks:
        ui.label("All networks already attached").style(
            "font-size:0.8125rem; color:var(--ht-text-secondary);"
        )
        return

    options = {str(network.id): _network_label(network) for network in available_networks}

    with ui.column().classes("w-full gap-2"):
        network_select = ui.select(options=options, label="Network").classes("w-full").props(
            "dense outlined"
        )
        ip_input = ui.input(label="IP address", placeholder="10.0.10.5").classes("w-full").props(
            "dense outlined"
        )

        async def _attach_membership() -> None:
            selected = network_select.value
            ip_text = str(ip_input.value or "").strip()
            if not selected or not ip_text:
                ui.notify("Select a network and enter an IP", type="warning")
                return
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.post(
                        f"{settings.api_base_url}/api/devices/{device_id}/networks",
                        json={"network_id": selected, "ip_address": ip_text},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5.0,
                    )
            except httpx.HTTPError as exc:
                logger.error("Network attach: {}", str(exc))
                ui.notify("Connection error", type="negative")
                return

            if r.status_code == 201:
                network_select.set_value(None)
                ip_input.set_value("")
                on_change()
                return

            detail = "Attach failed"
            try:
                payload = r.json()
                raw_detail = payload.get("detail")
                if isinstance(raw_detail, str):
                    detail = raw_detail
            except Exception:
                detail = f"Attach failed ({r.status_code})"
            ui.notify(detail, type="negative")

        primary_button(ui.button("Attach Network", on_click=_attach_membership))
