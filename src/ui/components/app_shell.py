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

from src.ui.components.sidebar import render_sidebar
from src.ui.design.theme_engine import apply_theme_to_client, get_initial_theme_css, get_theme_js_helpers

# ---------------------------------------------------------------------------
# HT-038 — Session expiry fetch interceptor (injected on every shell page)
# ---------------------------------------------------------------------------
_SESSION_EXPIRY_JS = """
(function() {
    if (window._htFetchIntercepted) return;
    window._htFetchIntercepted = true;
    var _origFetch = window.fetch;
    window.fetch = function() {
        var args = arguments;
        return _origFetch.apply(this, args).then(function(response) {
            var url = (typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url)) || '';
            if (response.status === 401 && url.indexOf('/api/') !== -1) {
                _htShowExpiredOverlay();
            }
            return response;
        });
    };
    function _htShowExpiredOverlay() {
        if (document.getElementById('ht-session-expired-overlay')) return;
        var s = getComputedStyle(document.documentElement);
        var overlay = document.createElement('div');
        overlay.id = 'ht-session-expired-overlay';
        overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;'
            + 'background:rgba(0,0,0,0.85);display:flex;align-items:center;'
            + 'justify-content:center;z-index:99999;';
        var box = document.createElement('div');
        box.style.cssText = 'background:' + s.getPropertyValue('--ht-bg-surface').trim() + ';padding:32px;border-radius:8px;'
            + 'text-align:center;max-width:400px;';
        var msg = document.createElement('p');
        msg.innerText = 'Your session has expired. Please sign in again.';
        msg.style.cssText = 'color:' + s.getPropertyValue('--ht-text-primary').trim() + ';font-size:1rem;margin-bottom:16px;';
        var btn = document.createElement('button');
        btn.innerText = 'Sign In';
        btn.style.cssText = 'background:' + s.getPropertyValue('--ht-accent').trim() + ';'
            + 'color:' + s.getPropertyValue('--ht-text-on-accent').trim() + ';border:none;'
            + 'padding:10px 24px;border-radius:6px;cursor:pointer;font-size:1rem;';
        btn.onclick = function() {
            var next = encodeURIComponent(window.location.pathname);
            window.location.href = '/login?expired=1&next=' + next;
        };
        box.appendChild(msg);
        box.appendChild(btn);
        overlay.appendChild(box);
        document.body.appendChild(overlay);
    }
})();
"""


# ---------------------------------------------------------------------------
# Global CSS — injected once per authenticated page
# ---------------------------------------------------------------------------
_GLOBAL_CSS = """
<style id="ht-global">
  * { box-sizing: border-box; }
  body { font-family: var(--ht-font-body); }
  @keyframes htFadeIn { from { opacity: 0; } to { opacity: 1; } }
  .ht-page-content { animation: htFadeIn var(--ht-transition-fast); }
  .ht-nav-item:hover { background-color: var(--ht-bg-surface-raised); }
    .ht-mobile-drawer-open { display: none !important; }
    @media (max-width: 768px) {
        .ht-mobile-drawer-open { display: inline-flex !important; }
    }
</style>
"""


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
            ).props("flat dense round color=grey-5").classes("ht-mobile-drawer-open q-mr-sm")
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
    with ui.dropdown_button(username, auto_close=False).props("flat color=grey-4"):
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


