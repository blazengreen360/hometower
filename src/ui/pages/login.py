"""Login page — NiceGUI form at /login.

Credentials are submitted via a JavaScript fetch to POST /api/auth/login.
On success the server sets an HttpOnly cookie and returns a JSON body with
user_id, role, and token_exp. The response is stored in app.storage.user
and the browser is redirected to / (or to the ``next`` query param if valid).

HT-038: If ``?expired=1`` is in the URL an info banner is shown.  The
``?next=`` param (validated server-side) is used for post-login redirect.
"""
import json

from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.components.auth_guard import safe_next_path
from src.ui.design.primitives import GLOBAL_UI_CSS
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import primary_button
from src.ui.design.theme_engine import get_initial_theme_css, get_theme_js_helpers


@ui.page("/login")
async def login_page(expired: str = "", next: str = "") -> None:  # noqa: A002
    """Login page — no shell, no auth guard (public route)."""
    safe_redirect = safe_next_path(next) or "/"

    ui.add_head_html(get_initial_theme_css("dark"))
    ui.add_head_html(get_theme_js_helpers())
    ui.add_head_html(GLOBAL_UI_CSS)
    ui.query("body").style("background-color: var(--ht-bg-base); color: var(--ht-text-primary);")

    with ui.column().classes("ht-auth-shell"):
        with card_surface(ui.card()).classes("ht-auth-card"):
            with card_section(ui.column()).classes("items-stretch"):
                ui.label("Hometower").classes("ht-page-title text-center w-full")
                ui.label("Sign in to manage your homelab inventory, topology history, and workspace settings.").classes(
                    "ht-muted-copy text-center"
                )

                # HT-038: session expiry banner (shown when ?expired=1)
                if expired == "1":
                    with ui.element("div").classes("ht-banner ht-banner-info"):
                        ui.label("Your session expired. Please sign in again.").classes("ht-small-copy")

                ui.element("div").classes("ht-keyline")

                email_input = (
                    ui.input("Email", placeholder="admin@hometower.local")
                    .classes("w-full")
                    .props('outlined type="email" autocomplete="email"')
                )
                password_input = (
                    ui.input("Password", password=True, password_toggle_button=True)
                    .classes("w-full")
                    .props('outlined autocomplete="current-password"')
                )
                error_label = ui.label("").style(
                    "color: var(--ht-error); font-size: 0.875rem; min-height: 1.25rem;"
                )

        # Store element IDs so the JS can read values directly from the DOM.
        # This avoids relying on NiceGUI's lazy server-side value sync, which
        # may not have completed by the time the button click handler fires.
        email_id = f"c{email_input.id}"
        password_id = f"c{password_input.id}"

        async def handle_login() -> None:
            error_label.set_text("")

            # Read credentials from the DOM (client-side) rather than from
            # the server-side NiceGUI element .value which may be stale.
            code = f"""
                const emailEl = document.getElementById({json.dumps(email_id)});
                const passEl = document.getElementById({json.dumps(password_id)});
                const email = emailEl ? emailEl.value : '';
                const password = passEl ? passEl.value : '';
                if (!email || !password) return JSON.stringify({{error: 'empty'}});
                const response = await fetch('/api/auth/login', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{email: email, password: password}})
                }});
                const data = await response.json();
                if (response.ok) {{
                    return JSON.stringify({{
                        user_id: data.user_id,
                        role: data.role,
                        token_exp: data.token_exp,
                        access_token: data.access_token,
                        email: email
                    }});
                }}
                return JSON.stringify({{error: 'invalid'}});
            """
            result_raw = await ui.run_javascript(code)
            try:
                result = json.loads(result_raw) if isinstance(result_raw, str) else result_raw
            except (json.JSONDecodeError, TypeError):
                result = {"error": "unknown"}

            if isinstance(result, dict) and "role" in result:
                nicegui_app.storage.user["role"] = result["role"]
                nicegui_app.storage.user["user_id"] = result["user_id"]
                nicegui_app.storage.user["token_exp"] = result["token_exp"]
                nicegui_app.storage.user["access_token"] = result.get("access_token", "")
                nicegui_app.storage.user["username"] = result.get("email", "")
                ui.navigate.to(safe_redirect)
            elif isinstance(result, dict) and result.get("error") == "empty":
                error_label.set_text("Please enter email and password")
            else:
                error_label.set_text("Invalid email or password")

        password_input.on("keydown.enter", handle_login)

        primary_button(ui.button("Log in", on_click=handle_login).classes("w-full"))
