"""Sidebar navigation component for the authenticated app shell (HT-026).

Owns the left-drawer, nav items, settings items, and the collapse toggle.
Kept separate from app_shell.py so each file stays under the 250-line limit.
"""
from dataclasses import dataclass
import inspect
from typing import Callable

from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.auth_guard import get_ui_role
from src.ui.components.sidebar_nav_item import _nav_item

# ---------------------------------------------------------------------------
# Navigation items
# ---------------------------------------------------------------------------
_NAV_ITEMS: list[dict[str, str]] = [
    {"label": "Dashboard", "route": "/", "icon": "dashboard"},
    {"label": "Workspaces", "route": "/workspaces", "icon": "workspaces"},
    {"label": "Inventory", "route": "/inventory", "icon": "inventory_2"},
    {"label": "IPAM", "route": "/ipam", "icon": "grid_view"},
    {"label": "Map", "route": "/map", "icon": "map"},
]

_SETTINGS_ITEMS: list[dict[str, str]] = [
    {"label": "Locations", "route": "/settings/locations", "icon": "location_on"},
    {"label": "Networks", "route": "/settings/networks", "icon": "lan"},
    {"label": "Power", "route": "/settings/power", "icon": "bolt", "admin_only": "true"},
    {"label": "Users", "route": "/settings/users", "icon": "people", "admin_only": "true"},
    {"label": "Data", "route": "/settings/data", "icon": "cloud_download"},
    {"label": "Profile", "route": "/settings/profile", "icon": "person"},
    {"label": "About", "route": "/settings/about", "icon": "info"},
]


@dataclass(frozen=True)
class SidebarControls:
    """Callable sidebar controls for the unified header affordance and explicit expand."""

    open_drawer: Callable[[], None]
    expand_sidebar: Callable[[], None]

    def __call__(self) -> None:
        self.open_drawer()


# ---------------------------------------------------------------------------
# Public render function — called from app_shell.py
# ---------------------------------------------------------------------------
def render_sidebar(current_route: str) -> SidebarControls:
    """Render the left navigation sidebar with collapse toggle."""
    role = get_ui_role()
    expanded: bool = nicegui_app.storage.user.get("sidebar_expanded", True)
    use_leave_guard = current_route == "/topology"

    with ui.left_drawer(value=False).props(
        f'id="ht-app-sidebar" show-if-above breakpoint=768 width=220 mini-width=56 {"mini" if not expanded else ""}'
    ).style(
        "background:color-mix(in srgb, var(--ht-bg-surface-raised) 94%, transparent);"
        " border-right:1px solid var(--ht-border); backdrop-filter:blur(18px);"
    ) as drawer:
        button_ref: list[ui.button] = []

        def _on_toggle() -> None:
            if button_ref:
                _toggle_sidebar(drawer, button_ref[0])

        with ui.row().classes("justify-end px-2 pt-2"):
            collapse_button = ui.button(
                icon="chevron_left" if expanded else "chevron_right",
                on_click=_on_toggle,
            ).props("flat dense round size=sm").classes("text-[var(--ht-text-secondary)]")
            button_ref.append(collapse_button)

        for item in _NAV_ITEMS:
            disabled = item.get("disabled") == "true"
            _nav_item(
                label=item["label"],
                icon=item["icon"],
                route=item["route"],
                active=(current_route == item["route"]),
                disabled=disabled,
                use_leave_guard=use_leave_guard,
                ui_module=ui,
            )

        ui.separator().classes("my-2")
        ui.label("Settings").classes(
            "text-[var(--ht-text-secondary)] text-[0.74rem] px-3 py-1 font-[700] tracking-[0.16em] uppercase"
        )

        for item in _SETTINGS_ITEMS:
            admin_only = item.get("admin_only") == "true"
            if admin_only and role != Role.Admin:
                continue
            _nav_item(
                label=item["label"],
                icon=item["icon"],
                route=item["route"],
                active=(current_route == item["route"]),
                disabled=False,
                use_leave_guard=use_leave_guard,
                ui_module=ui,
            )

    _sync_sidebar_state(expanded)
    return SidebarControls(
        open_drawer=lambda: _activate_sidebar_affordance(drawer, button_ref[0]) if button_ref else drawer.toggle(),
        expand_sidebar=lambda: _set_sidebar_expanded(drawer, button_ref[0], True) if button_ref else None,
    )
def _set_sidebar_expanded(
    drawer: ui.left_drawer,  # type: ignore[name-defined]
    toggle_button: ui.button,
    expanded: bool,
) -> None:
    """Apply the sidebar expanded state, persist it, and sync page affordances."""
    nicegui_app.storage.user["sidebar_expanded"] = expanded
    drawer.props(f"mini={str((not expanded)).lower()}")
    drawer.update()
    toggle_button.props(f'icon="{"chevron_left" if expanded else "chevron_right"}"')
    toggle_button.update()
    _sync_sidebar_state(expanded)


def _toggle_sidebar(drawer: ui.left_drawer, toggle_button: ui.button) -> None:  # type: ignore[name-defined]
    """Toggle sidebar expanded/collapsed and persist preference."""
    current: bool = nicegui_app.storage.user.get("sidebar_expanded", True)
    _set_sidebar_expanded(drawer, toggle_button, not current)


def _activate_sidebar_affordance(
    drawer: ui.left_drawer,  # type: ignore[name-defined]
    toggle_button: ui.button,
) -> None:
    """Open the drawer on narrow screens or re-expand the sidebar when collapsed."""
    if nicegui_app.storage.user.get("sidebar_expanded", True):
        drawer.toggle()
        return
    _set_sidebar_expanded(drawer, toggle_button, True)
    drawer.value = True
    drawer.update()


def _sync_sidebar_state(expanded: bool) -> None:
    """Mirror the drawer state into page-level classes and resize listeners."""
    result = ui.run_javascript(
        "document.body.classList.toggle("
        "'ht-sidebar-collapsed', "
        f"{str((not expanded)).lower()}"
        ");"
        "window.dispatchEvent(new CustomEvent('ht:topology-layout-sync'));"
    )
    if inspect.iscoroutine(result):
        result.close()
