"""Topology network filter controls for highlighting memberships on canvas."""
import json

from nicegui import ui

from src.models.device_network import DeviceNetworkNetworkRef
from src.models.network import NetworkListResponse

_DEFAULT_NETWORK_COLOR = "var(--ht-accent)"


def _option_label(network: dict[str, object]) -> str:
    name = str(network.get("name", ""))
    cidr = str(network.get("cidr", ""))
    vlan_id = network.get("vlan_id")
    raw_count = network.get("device_count", 0)
    if isinstance(raw_count, int):
        count = raw_count
    elif isinstance(raw_count, str) and raw_count.isdigit():
        count = int(raw_count)
    else:
        count = 0
    if isinstance(vlan_id, int):
        return f"{name} (VLAN {vlan_id}, {cidr}) - {count}"
    return f"{name} ({cidr}) - {count}"


def _network_color(network: dict[str, object]) -> str:
    color = str(network.get("color", "") or "").strip()
    return color or _DEFAULT_NETWORK_COLOR


def _panel_style(inline: bool) -> str:
    if inline:
        return "width:100%; gap:8px;"
    return (
        "width:220px; border-left:1px solid var(--ht-border);"
        " background:var(--ht-bg-sidebar); padding:10px; gap:8px;"
    )


def _active_order(
    by_id: dict[str, dict[str, object]],
    active_ids: set[str],
) -> list[str]:
    ordered_ids = [network_id for network_id in by_id if network_id in active_ids]
    ordered_ids.extend(
        sorted(network_id for network_id in active_ids if network_id not in by_id)
    )
    return ordered_ids


def _sanitize_active_ids(raw_ids: object) -> list[str]:
    if not isinstance(raw_ids, list):
        return []
    active_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in raw_ids:
        network_id = str(raw_id or "").strip()
        if not network_id or network_id in seen:
            continue
        seen.add(network_id)
        active_ids.append(network_id)
    return active_ids


def build_network_filter_records(
    all_networks: list[NetworkListResponse],
    memberships: list[DeviceNetworkNetworkRef],
) -> list[dict[str, object]]:
    """Build filter records from workspace networks with membership fallback rows."""
    options: list[dict[str, object]] = []
    seen: set[str] = set()
    for network in all_networks:
        network_id = str(network.id)
        options.append(
            {
                "id": network_id,
                "name": network.name,
                "cidr": network.cidr,
                "vlan_id": network.vlan_id,
                "device_count": network.device_count,
                "color": network.color,
            }
        )
        seen.add(network_id)
    for membership in memberships:
        network_id = str(membership.network_id)
        if network_id in seen:
            continue
        options.append(
            {
                "id": network_id,
                "name": membership.name,
                "cidr": membership.cidr,
                "vlan_id": membership.vlan_id,
                "device_count": 0,
                "color": membership.color,
            }
        )
    return options


async def read_active_network_ids() -> list[str]:
    """Read the overlay bridge's current network highlight state."""
    raw_ids = await ui.run_javascript(
        "window.htGetActiveNetworks ? window.htGetActiveNetworks() : []"
    )
    return _sanitize_active_ids(raw_ids)


def render_network_highlight_controls(
    networks: list[dict[str, object]],
    *,
    active_ids: list[str] | None = None,
    inline: bool = False,
    sync_empty_state: bool = False,
) -> None:
    """Render highlight toggles for topology networks."""
    if not networks:
        with ui.column().classes("w-full").style(_panel_style(inline)):
            ui.label("Networks").style("font-size:0.9rem; font-weight:600;")
            ui.label("No networks found").style(
                "font-size:0.78rem; color:var(--ht-text-secondary);"
            )
        if sync_empty_state:
            ui.run_javascript(
                "if(window.htSetActiveNetworks) window.htSetActiveNetworks([], {})"
            )
        return

    by_id = {
        str(network.get("id", "")): network
        for network in networks
        if str(network.get("id", "")).strip()
    }
    selected_ids = set(active_ids or [])

    with ui.column().classes("w-full").style(_panel_style(inline)):
        ui.label("Networks").style("font-size:0.9rem; font-weight:600;")
        ui.label("Highlight nodes by membership").style(
            "font-size:0.78rem; color:var(--ht-text-secondary);"
        )
        search_input = ui.input(placeholder="Search networks...").props("dense outlined")
        search_input.classes("w-full")
        rows = ui.column().classes("w-full").style("gap:2px;")

        def _emit_active_set() -> None:
            ordered_ids = _active_order(by_id, selected_ids)
            colors = {
                network_id: _network_color(by_id[network_id])
                for network_id in ordered_ids
                if network_id in by_id
            }
            ui.run_javascript(
                "if(window.htSetActiveNetworks) window.htSetActiveNetworks("
                + json.dumps(ordered_ids)
                + ", "
                + json.dumps(colors)
                + ")"
            )

        def _toggle_network(network_id: str, enabled: bool) -> None:
            if enabled:
                selected_ids.add(network_id)
            else:
                selected_ids.discard(network_id)
            _emit_active_set()

        def _render_rows() -> None:
            rows.clear()
            needle = str(search_input.value or "").strip().lower()
            match_count = 0
            for network in networks:
                name = str(network.get("name", "")).lower()
                cidr = str(network.get("cidr", "")).lower()
                if needle and needle not in name and needle not in cidr:
                    continue
                network_id = str(network.get("id", "")).strip()
                if not network_id:
                    continue
                color = _network_color(network)
                with rows:
                    with ui.row().classes("items-center w-full").style(
                        "gap:8px; min-height:30px;"
                    ):
                        ui.element("span").style(
                            "display:inline-block; width:10px; height:10px;"
                            " border-radius:9999px;"
                            f" background:{color}; border:1px solid var(--ht-border);"
                            " flex-shrink:0;"
                        )
                        checkbox = ui.checkbox(
                            _option_label(network), value=network_id in selected_ids
                        ).props("dense")
                        checkbox.classes("w-full")
                        checkbox.on_value_change(
                            lambda e, selected_id=network_id: _toggle_network(
                                selected_id, bool(getattr(e, "value", False))
                            )
                        )
                match_count += 1

            if match_count == 0:
                with rows:
                    ui.label("No matching networks").style(
                        "font-size:0.75rem; color:var(--ht-text-secondary);"
                    )

        def _clear_filter() -> None:
            selected_ids.clear()
            _render_rows()
            _emit_active_set()

        search_input.on("update:model-value", lambda _: _render_rows())
        _render_rows()
        ui.button("Clear Highlights", on_click=_clear_filter).props("flat")


def render_network_filter_panel(networks: list[dict[str, object]]) -> None:
    """Render the standalone topology network column."""
    # Standalone mode still updates window.htSetActiveNetworks and uses _network_color().
    render_network_highlight_controls(networks, sync_empty_state=True)
