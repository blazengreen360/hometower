"""Topology shell helpers for HT-076 canvas-first layout."""

from typing import Protocol

from nicegui import ui

from src.ui.components.device_palette import render_palette
from src.ui.components.stencils_panel import StencilDevice, render_stencils_panel
from src.ui.components.topology_layout_runtime import trigger_topology_layout_sync
from src.ui.components.topology_layout_shell_styles import _TOPOLOGY_LAYOUT_SHELL_CSS


class _ExpandableSection(Protocol):
  def set_value(self, value: bool) -> None:
    ...


def inject_topology_layout_shell_css() -> None:
    """Inject shared CSS for the HT-076 topology shell layout."""
    ui.add_head_html(_TOPOLOGY_LAYOUT_SHELL_CSS)


def render_topology_left_rail(
    stencil_devices: list[StencilDevice],
    placed_ids: set[str],
) -> ui.element:
    """Render the consolidated left tool rail used in topology edit mode."""
    state = {
        "device_types_open": True,
        "inventory_open": False,
    }
    sections: dict[str, _ExpandableSection] = {}

    rail = ui.element("aside").props(
        'id="ht-topology-left-rail" role="complementary" aria-label="Topology tools"'
    )

    def _sync_rail_state(*, dispatch_resize: bool) -> None:
        is_compact = not state["device_types_open"] and not state["inventory_open"]
        if is_compact:
            rail.classes(add="ht-topology-left-rail--compact")
        else:
            rail.classes(remove="ht-topology-left-rail--compact")
        if dispatch_resize:
            trigger_topology_layout_sync()

    def _on_section_toggle(key: str):
        def _handle(event: object) -> None:
            next_value = bool(getattr(event, "value", False))
            state[key] = next_value
            if next_value:
                other_key = "inventory_open" if key == "device_types_open" else "device_types_open"
                state[other_key] = False
                other_section = sections.get(other_key)
                if other_section is not None:
                    other_section.set_value(False)
            _sync_rail_state(dispatch_resize=True)

        return _handle

    with rail:
        device_types = ui.expansion(
            "Device Types", icon="drag_indicator", value=state["device_types_open"]
        ).classes(
            "w-full ht-topology-rail-section"
        )
        sections["device_types_open"] = device_types
        device_types.on_value_change(_on_section_toggle("device_types_open"))
        with device_types:
            with ui.element("div").classes("ht-topology-palette-slot"):
                render_palette()

        inventory = ui.expansion(
            "Inventory", icon="inventory_2", value=state["inventory_open"]
        ).classes(
            "w-full ht-topology-rail-section"
        )
        sections["inventory_open"] = inventory
        inventory.on_value_change(_on_section_toggle("inventory_open"))
        with inventory:
            with ui.element("div").classes("ht-topology-stencils-slot"):
                render_stencils_panel(stencil_devices, placed_ids)

    _sync_rail_state(dispatch_resize=False)
    rail.set_visibility(False)
    return rail
