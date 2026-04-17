"""Topology network filter panel for highlighting memberships on canvas."""
import json

from nicegui import ui

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


def render_network_filter_panel(networks: list[dict[str, object]]) -> None:
    """Render network toggles and push active-network state to the overlay bridge."""
    if not networks:
        with ui.column().style(
            "width: 220px; border-left: 1px solid var(--ht-border);"
            " background: var(--ht-bg-sidebar); padding: 10px;"
        ):
            ui.label("Networks").style("font-size:0.9rem; font-weight:600;")
            ui.label("No networks found").style(
                "font-size:0.78rem; color:var(--ht-text-secondary);"
            )
        ui.run_javascript("if(window.htSetActiveNetworks) window.htSetActiveNetworks([], {})")
        return

    by_id = {str(network.get("id", "")): network for network in networks}
    active_ids: set[str] = set()

    with ui.column().style(
        "width: 220px; border-left: 1px solid var(--ht-border);"
        " background: var(--ht-bg-sidebar); padding: 10px; gap: 8px;"
    ):
        ui.label("Networks").style("font-size:0.9rem; font-weight:600;")
        ui.label("Highlight nodes by membership").style(
            "font-size:0.78rem; color:var(--ht-text-secondary);"
        )

        search_input = ui.input(placeholder="Search networks...").props("dense outlined")
        rows = ui.column().classes("w-full").style("gap:2px;")

        def _emit_active_set() -> None:
            ordered_ids = [network_id for network_id in by_id if network_id in active_ids]
            colors = {
                network_id: _network_color(by_id[network_id])
                for network_id in ordered_ids
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
                active_ids.add(network_id)
            else:
                active_ids.discard(network_id)
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
                network_id = str(network.get("id", ""))
                if not network_id:
                    continue
                color = _network_color(network)
                with rows:
                    with ui.row().classes("items-center w-full").style("gap:8px; min-height:30px;"):
                        ui.element("span").style(
                            "display:inline-block; width:10px; height:10px; border-radius:9999px;"
                            f" background:{color}; border:1px solid var(--ht-border); flex-shrink:0;"
                        )
                        checkbox = ui.checkbox(
                            _option_label(network),
                            value=network_id in active_ids,
                        ).props("dense")
                        checkbox.classes("w-full")
                        checkbox.on_value_change(
                            lambda e, selected_id=network_id: _toggle_network(
                                selected_id,
                                bool(getattr(e, "value", False)),
                            )
                        )
                match_count += 1

            if match_count == 0:
                with rows:
                    ui.label("No matching networks").style(
                        "font-size:0.75rem; color:var(--ht-text-secondary);"
                    )

        search_input.on("update:model-value", lambda _: _render_rows())
        _render_rows()

        def _clear_filter() -> None:
            active_ids.clear()
            _render_rows()
            _emit_active_set()

        ui.button("Clear Highlights", on_click=_clear_filter).props("flat")
        _emit_active_set()
