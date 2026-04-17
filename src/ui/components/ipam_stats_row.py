"""Aggregate header stats row for the /ipam page (HT-024)."""

from src.models.ipam import IpamPageStatsResponse
from nicegui import ui


def render_ipam_stats_row(summary: IpamPageStatsResponse) -> None:
    """Render the four aggregate IPAM stat cards."""
    most_name = summary.most_utilized_network.name if summary.most_utilized_network else "None"
    most_pct = (
        f"{summary.most_utilized_network.utilization_pct:.2f}%"
        if summary.most_utilized_network is not None
        else "0.00%"
    )

    cards = [
        ("Total Networks", str(summary.total_networks)),
        ("Assigned IPs", str(summary.total_assigned_ips)),
        ("Conflicts", str(summary.total_conflicts)),
        ("Most Utilized", f"{most_name} ({most_pct})"),
    ]

    with ui.row().classes("w-full gap-3 items-stretch flex-wrap"):
        for label, value in cards:
            with ui.card().classes("min-w-[220px] flex-1"):
                ui.label(label).style(
                    "font-size:0.75rem; color:var(--ht-text-secondary);"
                    " text-transform:uppercase; letter-spacing:0.04em;"
                )
                ui.label(value).style(
                    "font-size:1rem; font-weight:600; color:var(--ht-text-primary);"
                )
