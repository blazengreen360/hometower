"""Grid renderer for /24-and-smaller IPv4 IPAM detail payloads."""
from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from src.models.ipam import IpamDeviceClaimResponse, IpamNetworkDetailResponse
from src.models.types import IpamCellStatus
from src.ui.services.ipam_search import IpamSearchTargets, build_cell_id


def render_ipam_grid(
    detail: IpamNetworkDetailResponse,
    search_targets: IpamSearchTargets,
    on_open_device: Callable[[str], None],
    network_key: str,
) -> None:
    """Render all addresses as compact status-colored cells."""
    highlighted = set(search_targets.cell_ids)

    with ui.element("div").style(
        "display:grid; grid-template-columns:repeat(16, minmax(0, 1fr));"
        " gap:6px; align-items:stretch;"
    ):
        for cell in detail.cells:
            cell_id = build_cell_id(network_key, cell.address)
            is_highlighted = cell_id in highlighted
            can_open_single_device = cell.claim_count == 1
            with ui.element("div").props(f'id="{cell_id}"').style(
                f"background:{_status_color(cell.status)};"
                " border-radius:6px; min-height:34px; padding:4px 6px;"
                " font-size:0.7rem; color:var(--ht-text-on-accent);"
                " display:flex; align-items:center; justify-content:center;"
                " text-align:center; cursor:pointer;"
                + (
                    " outline:2px solid var(--ht-accent); box-shadow:0 0 0 2px var(--ht-accent-glow);"
                    if is_highlighted
                    else ""
                )
            ).on(
                "click",
                lambda claims=cell.device_claims: _open_single_claim(claims, on_open_device),
            ):
                ui.label(cell.address.split(".")[-1]).style("font-weight:600;")
                _render_cell_tooltip(cell.device_claims, cell.status, on_open_device)

            if not can_open_single_device and cell.claim_count == 0:
                continue


def _render_cell_tooltip(
    claims: list[IpamDeviceClaimResponse],
    status: IpamCellStatus,
    on_open_device: Callable[[str], None],
) -> None:
    with ui.tooltip().classes("max-w-[320px]"):
        if not claims:
            ui.label(status.value.title())
            return

        if len(claims) == 1:
            claim = claims[0]
            ui.label(f"{claim.device_name} ({claim.device_type.value})")
            ui.label(f"IP: {claim.ip_address}")
            ui.label(f"MAC: {claim.mac or '—'}")
            return

        ui.label("Conflict")
        with ui.column().classes("gap-1"):
            for claim in claims:
                ui.button(
                    f"{claim.device_name} ({claim.ip_address})",
                    on_click=lambda c=claim: on_open_device(str(c.device_id)),
                ).props("dense flat").style("justify-content:flex-start; width:100%;")


def _open_single_claim(
    claims: list[IpamDeviceClaimResponse],
    on_open_device: Callable[[str], None],
) -> None:
    if len(claims) != 1:
        return
    on_open_device(str(claims[0].device_id))


def _status_color(status: IpamCellStatus) -> str:
    if status == IpamCellStatus.used:
        return "var(--ht-ipam-used)"
    if status == IpamCellStatus.gateway:
        return "var(--ht-ipam-gateway)"
    if status == IpamCellStatus.conflict:
        return "var(--ht-ipam-conflict)"
    if status == IpamCellStatus.reserved:
        return "var(--ht-ipam-reserved)"
    return "var(--ht-ipam-free)"
