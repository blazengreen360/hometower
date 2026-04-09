"""Login page — NiceGUI form at /login.

Credentials are submitted via a JavaScript fetch to POST /api/auth/login.
On success the JWT is stored in sessionStorage and app.storage.user, then
the browser is redirected to /.
"""
import json

from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.design.tokens import (
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SURFACE,
    COLOR_TEXT,
    SPACING_LG,
)


@ui.page("/login")
async def login_page() -> None:
    ui.query("body").style(f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT}")

    with ui.card().classes("absolute-center").style(
        f"width: 360px; padding: {SPACING_LG}; background-color: {COLOR_SURFACE};"
    ):
        ui.label("Hometower").classes("text-2xl font-bold text-center w-full").style(
            f"color: {COLOR_PRIMARY}"
        )
        ui.separator()

        email_input = (
            ui.input("Email", placeholder="admin@hometower.local")
            .classes("w-full")
            .props('type="email" autocomplete="email"')
        )
        password_input = (
            ui.input("Password", password=True, password_toggle_button=True)
            .classes("w-full")
            .props('autocomplete="current-password"')
        )
        error_label = ui.label("").classes("text-sm").style(
            f"color: {COLOR_ERROR}; min-height: 1.25rem"
        )

        async def handle_login() -> None:
            error_label.set_text("")
            # json.dumps ensures all special characters are properly escaped
            email_js = json.dumps(email_input.value)
            password_js = json.dumps(password_input.value)

            code = f"""
                const response = await fetch('/api/auth/login', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        email: {email_js},
                        password: {password_js}
                    }})
                }});
                const data = await response.json();
                if (response.ok) {{
                    sessionStorage.setItem('access_token', data.access_token);
                    return data.access_token;
                }}
                return null;
            """
            token = await ui.run_javascript(code)
            if token:
                nicegui_app.storage.user["access_token"] = token
                ui.navigate.to("/topology")
            else:
                error_label.set_text("Invalid email or password")

        ui.button("Log in", on_click=handle_login).classes("w-full").style(
            f"background-color: {COLOR_PRIMARY}; color: white;"
        )
