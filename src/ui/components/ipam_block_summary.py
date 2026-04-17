"""Block-summary renderer for large IPv4 networks in /ipam."""
from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from src.models.ipam import IpamNetworkDetailResponse
from src.ui.services.ipam_search import (
    IpamSearchTargets,
    build_allocation_id,
    build_block_id,
)


def render_ipam_block_summary(
    detail: IpamNetworkDetailResponse,
    search_targets: IpamSearchTargets,
    on_open_device: Callable[[str], None],
    network_key: str,
) -> None:
    """Render /24 buckets with utilization and allocation rows."""
    highlighted_blocks = set(search_targets.block_ids)
    highlighted_allocations = set(search_targets.allocation_addresses)

    with ui.column().classes("w-full gap-3"):
        with ui.row().classes("w-full gap-2 flex-wrap"):
            for block in detail.blocks:
                block_id = build_block_id(network_key, block.block_cidr)
                is_highlighted = block_id in highlighted_blocks
                with ui.card().props(f'id="{block_id}"').style(
                    "min-width:190px;"
                    " border:1px solid var(--ht-border);"
                    + (
                        " box-shadow:0 0 0 2px var(--ht-accent-glow);"
                        " border-color:var(--ht-accent);"
                        if is_highlighted
                        else ""
                    )
                ):
                    ui.label(block.block_cidr).style(
                        "font-size:0.85rem; font-weight:600; color:var(--ht-text-primary);"
                    )
                    ui.label(
                        f"{block.used_ip_count}/{block.usable_ip_count} used ({block.utilization_pct:.2f}%)"
                    ).style("font-size:0.75rem; color:var(--ht-text-secondary);")
                    if block.conflict_ip_count > 0:
                        ui.badge(
                            f"{block.conflict_ip_count} conflicts",
                            color="negative",
                        ).props("rounded")

        if detail.allocations:
            ui.label("Claims").style(
                "font-size:0.8rem; color:var(--ht-text-secondary); text-transform:uppercase;"
            )
            for allocation in detail.allocations:
                allocation_id = build_allocation_id(network_key, allocation.address)
                is_highlighted = allocation.address in highlighted_allocations
                with ui.row().props(f'id="{allocation_id}"').classes("items-center w-full gap-2").style(
                    "padding:6px 8px; border-radius:8px;"
                    " background:var(--ht-bg-surface-raised);"
                    + (
                        " outline:2px solid var(--ht-accent);"
                        if is_highlighted
                        else ""
                    )
                ):
                    ui.label(allocation.address).style(
                        "font-family:var(--ht-font-mono); font-size:0.85rem;"
                    )
                    ui.label(allocation.block_cidr).style(
                        "font-size:0.75rem; color:var(--ht-text-secondary);"
                    )
                    ui.space()
                    for claim in allocation.device_claims:
                        ui.button(
                            claim.device_name,
                            on_click=lambda c=claim: on_open_device(str(c.device_id)),
                        ).props("dense flat").style("font-size:0.75rem;")
