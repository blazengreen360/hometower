"""App shell component — shared persistent layout for authenticated pages (HT-026).

Hides the NiceGUI ui.header() + ui.left_drawer() layout API so that swapping
NiceGUI layout primitives never touches any page file.

Also injects the HT-038 session-expiry fetch interceptor on every authenticated
page via ui.add_body_html().

Public API: ``app_shell`` context manager.
"""
import json
from contextlib import contextmanager
from collections.abc import Callable
from typing import Generator, Optional

from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.components.app_shell_assets import _GLOBAL_CSS
from src.ui.components.app_shell_assets import _SESSION_EXPIRY_JS
from src.ui.components.sidebar import render_sidebar
from src.ui.design.primitives import GLOBAL_UI_CSS
from src.ui.design.theme_engine import apply_theme_to_client, get_initial_theme_css, get_theme_js_helpers


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------
@contextmanager
def app_shell(
    title: str,
    current_route: str,
    breadcrumb: Optional[list[str]] = None,
    header_actions: Optional[Callable[[], None]] = None,
) -> Generator[None, None, None]:
    """Context manager that renders header + sidebar then yields for page content.

    Sets the global body background, injects the session-expiry JS interceptor,
    renders the persistent header and sidebar, then yields inside a flex column
    that fills the remaining viewport area.

    Usage inside an authenticated @ui.page function::

        with app_shell("Inventory", "/inventory", breadcrumb=["Inventory"]):
            # page-specific NiceGUI elements go here
            ...

    Sidebar expansion state is persisted in
    ``nicegui_app.storage.user["sidebar_expanded"]`` (NiceGUI server-side
    per-session storage — satisfies the "persists across page navigations"
    acceptance criterion from HT-026).
    """
    theme = nicegui_app.storage.user.get("theme", "dark")
    ui.add_head_html(get_initial_theme_css(theme))
    ui.add_head_html(get_theme_js_helpers())
    ui.add_head_html(GLOBAL_UI_CSS)
    ui.add_head_html(_GLOBAL_CSS)
    ui.query("body").style(
        "background-color:var(--ht-bg-surface); color:var(--ht-text-primary); margin:0;"
    )
    ui.query(".q-page").style("display:flex; flex-direction:column;")
    ui.query(".nicegui-content").style("flex:1; display:flex; flex-direction:column;")
    ui.add_body_html(f"<script>{_SESSION_EXPIRY_JS}</script>")
    mobile_drawer_opener = render_sidebar(current_route)
    _render_header(
        breadcrumb or [title],
        header_actions,
        mobile_drawer_opener,
    )
    with ui.column().classes("flex-1 w-full ht-page-content").style("min-height:0;"):
        yield


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
def _render_header(
    breadcrumb: list[str],
    header_actions: Optional[Callable[[], None]] = None,
    mobile_drawer_opener: Optional[Callable[[], None]] = None,
) -> None:
    """Render the top header bar: logo + breadcrumb on left, user menu on right."""
    with ui.header().style(
        "background-color:var(--ht-bg-surface); border-bottom:1px solid var(--ht-border);"
        " padding:0 16px; height:48px; display:flex; align-items:center;"
    ):
        if mobile_drawer_opener:
            ui.button(
                icon="menu",
                on_click=mobile_drawer_opener,
            ).props("flat dense round").classes("ht-mobile-drawer-open ht-sidebar-reopen q-mr-sm").style(
                "color:var(--ht-text-secondary)"
            )
        ui.link("Hometower", "/").style(
            "color:var(--ht-accent); font-weight:700; font-size:1.1rem;"
            " text-decoration:none; margin-right:16px;"
        )
        if breadcrumb:
            with ui.row().classes("items-center gap-1"):
                for i, crumb in enumerate(breadcrumb):
                    if i > 0:
                        ui.label("›").style("color:var(--ht-text-secondary)")
                    ui.label(crumb).style(
                        "color:var(--ht-text-secondary); font-size:0.875rem"
                    )
        ui.space()
        if header_actions:
            with ui.row().style("gap:8px; align-items:center; margin-right:8px;"):
                header_actions()
        _render_user_menu()


def _render_user_menu() -> None:
    """Render the top-right user dropdown (username + Change Password + Logout)."""
    username: str = nicegui_app.storage.user.get("username", "User")
    with ui.dropdown_button(username, auto_close=False).props("flat").style(
        "color:var(--ht-text-primary)"
    ):
        ui.item(
            "Change Password",
            on_click=lambda: ui.navigate.to("/settings/profile"),
        )
        ui.separator()
        # ── Theme submenu ────────────────────────────────────────────
        with ui.row().classes("px-4 py-1 items-center gap-2"):
            ui.label("Theme").style(
                "font-size:0.75rem; font-weight:600; color:var(--ht-text-secondary);"
                " text-transform:uppercase; letter-spacing:0.5px;"
            )
        for label, key in [("Dark", "dark"), ("Light", "light"), ("Midnight", "midnight")]:
            current = nicegui_app.storage.user.get("theme", "dark")
            ui.item(
                f"{'\u2713 ' if current == key else '  '}{label}",
                on_click=lambda k=key: _handle_theme_change(k),
            )
        ui.separator()
        ui.item("Logout", on_click=_do_logout)


async def _handle_theme_change(theme: str) -> None:
    """Persist theme selection and push CSS vars to the client."""
    from src.ui.components.canvas_styles import build_theme_style_json

    nicegui_app.storage.user["theme"] = theme
    await apply_theme_to_client(theme)
    styles_json = build_theme_style_json(theme)
    await ui.run_javascript(
        f"if (window.updateCyTheme) window.updateCyTheme({json.dumps(styles_json)})"
    )


def _do_logout() -> None:
    """Clear session storage and navigate to /login."""
    nicegui_app.storage.user.clear()
    ui.navigate.to("/login")


