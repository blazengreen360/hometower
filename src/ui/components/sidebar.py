"""Sidebar navigation component for the authenticated app shell (HT-026).

Owns the left-drawer, nav items, settings items, and the collapse toggle.
Kept separate from app_shell.py so each file stays under the 250-line limit.
"""
from collections.abc import Callable

from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.auth_guard import get_ui_role

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


# ---------------------------------------------------------------------------
# Public render function — called from app_shell.py
# ---------------------------------------------------------------------------
def render_sidebar(current_route: str) -> Callable[[], None]:
    """Render the left navigation sidebar with collapse toggle."""
    role = get_ui_role()
    expanded: bool = nicegui_app.storage.user.get("sidebar_expanded", True)
    use_leave_guard = current_route == "/topology"

    with ui.left_drawer(value=False).props(
        f"show-if-above breakpoint=768 width=220 mini-width=56 {'mini' if not expanded else ''}"
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
            )

    return drawer.toggle


def _nav_item(
    label: str,
    icon: str,
    route: str,
    active: bool,
    disabled: bool,
    use_leave_guard: bool,
) -> None:
    """Render a single sidebar navigation row."""
    active_style = (
        "background-color:var(--ht-accent-glow); border-left:3px solid var(--ht-accent);"
        if active
        else "background-color:transparent; border-left:3px solid transparent;"
    )
    text_color = "var(--ht-accent)" if active else "var(--ht-text-primary)"
    guard_child_style = " pointer-events:none;" if use_leave_guard else ""

    click_handler: Callable[[], object] | None = None
    guard_props = 'data-ht-guard-nav="true"'
    guard_target_props = f'data-ht-nav-target="{route}"'
    guard_disabled_props = 'data-ht-nav-disabled="true" aria-disabled="true"'

    if not use_leave_guard:

        def _on_click_direct() -> None:
            if disabled:
                return
            ui.navigate.to(route)

        click_handler = _on_click_direct

    row = ui.row().classes(
        "items-center px-3 py-2 cursor-pointer w-full ht-nav-item rounded-r-[10px]"
    ).style(
        active_style + f" color:{text_color};"
        " transition:background-color var(--ht-transition-fast);"
    )
    if use_leave_guard:
        row.props(guard_props)
        if disabled:
            row.props(guard_disabled_props)
        else:
            row.props(f'{guard_target_props} role="link" tabindex="0"')
    elif click_handler is not None:
        row.on("click", click_handler)

    with row:
        icon_el = ui.icon(icon).style(f"color:{text_color}; font-size:1.25rem;{guard_child_style}")
        label_el = ui.label(label).style(
            f"font-weight:{'600' if active else '400'}; font-size:0.875rem;{guard_child_style}"
        )
        if use_leave_guard:
            icon_el.props(guard_props)
            label_el.props(guard_props)
            if disabled:
                icon_el.props(guard_disabled_props)
                label_el.props(guard_disabled_props)
            else:
                icon_el.props(guard_target_props)
                label_el.props(guard_target_props)
        if disabled:
            ui.badge("soon").classes("bg-[var(--ht-bg-base)] text-[var(--ht-text-secondary)]")


def _toggle_sidebar(drawer: ui.left_drawer, toggle_button: ui.button) -> None:  # type: ignore[name-defined]
    """Toggle sidebar expanded/collapsed and persist preference."""
    current: bool = nicegui_app.storage.user.get("sidebar_expanded", True)
    expanded = not current
    nicegui_app.storage.user["sidebar_expanded"] = expanded
    drawer.props(f"mini={str((not expanded)).lower()}")
    drawer.update()
    toggle_button.props(f'icon="{"chevron_left" if expanded else "chevron_right"}"')
    toggle_button.update()
