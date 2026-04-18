"""Settings users page at /settings/users."""
import html
from typing import Optional

import httpx
from nicegui import app as nicegui_app
from nicegui import ui
from nicegui.elements.table import Table

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_insufficient_role, redirect_if_unauthenticated
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import secondary_button
from src.ui.design.table_patterns import create_standard_table
from src.ui.design.table_patterns import render_table_search_input
from src.ui.pages.settings_users_table import build_user_rows
from src.ui.pages.settings_users_table import SETTINGS_USERS_BODY_SLOT
from src.ui.pages.settings_users_table import SETTINGS_USERS_COLUMNS
from src.ui.pages.settings_page_helpers import show_destructive_confirmation
from src.ui.utils.formatting import LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT
from src.ui.utils.validation_feedback import friendly_error_message
from src.utils.logger import logger
from src.utils.settings import settings

_API = f"{settings.api_base_url}/api/users/"
_USER_FIELD_LABELS: dict[str, str] = {
    "username": "Username",
    "email": "Email",
    "password": "Password",
}
_USER_MESSAGE_OVERRIDES: dict[str, str] = {
    "email already registered": "Email already registered.",
    "password must be at least 8 characters": "Password must be at least 8 characters.",
}


def _auth_headers() -> dict[str, str]:
    token = nicegui_app.storage.user.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@ui.page("/settings/users")
async def settings_users_page() -> None:
    """User management settings page — Admin only."""
    if redirect_if_unauthenticated(current_path="/settings/users"):
        return
    if redirect_if_insufficient_role(Role.Admin):
        return

    current_user_id: str = nicegui_app.storage.user.get("user_id", "")
    users: list[dict[str, object]] = []
    modal_mode = {"value": "create"}
    editing_id: dict[str, Optional[str]] = {"value": None}
    table: Table | None = None

    form: dict[str, str | bool] = {
        "username": "",
        "email": "",
        "password": "",
        "role": "Contributor",
        "is_active": True,
    }

    async def load_users() -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(_API, headers=_auth_headers())
            resp.raise_for_status()
            users.clear()
            users.extend(resp.json())
            if table is None:
                return
            table.rows = build_user_rows(users, current_user_id)
            table.update()
        except Exception as exc:
            logger.error("Failed to load users: {}", exc)
            ui.notify("Couldn't load users. Please refresh and try again.", type="negative")

    def _clear_form_error() -> None:
        error_label.set_text("")
        error_label.set_visibility(False)

    def _reset_form() -> None:
        form.update({"username": "", "email": "", "password": "", "role": "Contributor", "is_active": True})
        _clear_form_error()

    def open_create_modal() -> None:
        _reset_form()
        modal_mode["value"] = "create"
        editing_id["value"] = None
        modal_title.set_text("Create User")
        dialog.open()

    def open_edit_modal(row: dict[str, object]) -> None:
        _reset_form()
        form["username"] = str(row["username"])
        form["email"] = str(row["email"])
        form["role"] = str(row["role"])
        form["is_active"] = bool(row["is_active"])
        modal_mode["value"] = "edit"
        editing_id["value"] = str(row["id"])
        modal_title.set_text("Edit User")
        dialog.open()

    async def submit_form() -> None:
        _clear_form_error()
        if modal_mode["value"] == "create" and not str(form["password"]).strip():
            error_label.set_text("Password is required.")
            error_label.set_visibility(True)
            return
        payload: dict[str, str | bool] = {
            "username": form["username"],
            "email": form["email"],
            "role": form["role"],
            "is_active": form["is_active"],
        }
        if form["password"]:
            payload["password"] = form["password"]
        try:
            async with httpx.AsyncClient() as client:
                if modal_mode["value"] == "create":
                    resp = await client.post(
                        _API, json=payload, headers=_auth_headers()
                    )
                else:
                    resp = await client.patch(
                        f"{_API}{editing_id['value']}",
                        json=payload,
                        headers=_auth_headers(),
                    )
            if resp.status_code in (200, 201):
                dialog.close()
                ui.notify("Saved", type="positive")
                await load_users()
            else:
                message = friendly_error_message(
                    resp,
                    fallback="Couldn't save user. Please check the form and try again.",
                    field_labels=_USER_FIELD_LABELS,
                    message_overrides=_USER_MESSAGE_OVERRIDES,
                )
                error_label.set_text(message)
                error_label.set_visibility(True)
        except Exception as exc:
            logger.error("User save failed: {}", exc)
            error_label.set_text("Couldn't save user right now. Please try again.")
            error_label.set_visibility(True)

    def confirm_delete(user_id: str, username: str) -> None:
        async def do_delete() -> None:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.delete(
                        f"{_API}{user_id}", headers=_auth_headers()
                    )
                if resp.status_code == 204:
                    ui.notify(f"Deleted '{html.escape(username)}'", type="positive")
                    await load_users()
                else:
                    ui.notify(
                        friendly_error_message(
                            resp,
                            fallback="Couldn't delete user. Please try again.",
                        ),
                        type="negative",
                    )
            except Exception as exc:
                logger.error("User delete failed: {}", exc)
                ui.notify("Couldn't delete user right now. Please try again.", type="negative")

        show_destructive_confirmation(
            ui_module=ui,
            title=f"Delete '{html.escape(username)}'?",
            description=None,
            on_confirm=do_delete,
            min_width_class="min-w-[320px]",
        )

    def _on_delete(event: object) -> None:
        args = getattr(event, "args", {})
        if not isinstance(args, dict):
            return
        user_id = str(args.get("id", ""))
        if not user_id:
            return
        confirm_delete(user_id, str(args.get("username", "")))

    with app_shell("Users", "/settings/users", breadcrumb=["Settings", "Users"]):
        ui.add_body_html(LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT)
        with page_container(ui.column()):
            def _apply_search(value: str) -> None:
                if table is not None:
                    table.set_filter(value)

            with ui.row().classes("w-full items-end justify-between gap-4 flex-wrap"):
                render_page_intro(
                    ui,
                    "User Management",
                    "Create, edit, and deactivate accounts with explicit role control for Admin, Contributor, and Reader access.",
                    "Settings",
                )
                primary_button(ui.button("+ Add User", on_click=open_create_modal))
            with ui.row().classes("w-full justify-end"):
                render_table_search_input(
                    ui_module=ui,
                    placeholder="Search users",
                    on_change=_apply_search,
                )

            table = create_standard_table(ui_module=ui, columns=SETTINGS_USERS_COLUMNS, row_key="id", sort_by="username")
            table.add_slot("body", SETTINGS_USERS_BODY_SLOT)
            table.on("edit", lambda e: open_edit_modal(e.args))
            table.on("delete", _on_delete)

    with ui.dialog() as dialog, card_surface(ui.card()).classes("w-96"):
        with card_section(ui.column()):
            modal_title = ui.label("Create User").classes("ht-section-title")
            username_input = ui.input("Username").bind_value(form, "username").classes("w-full").props("outlined")
            email_input = ui.input("Email").bind_value(form, "email").classes("w-full").props("outlined")
            password_input = ui.input("Password", password=True).bind_value(form, "password").classes(
                "w-full"
            ).props("outlined")
            role_select = ui.select(
                ["Admin", "Contributor", "Reader"],
                label="Role",
            ).bind_value(form, "role").classes("w-full").props("outlined")
            active_checkbox = ui.checkbox("Active").bind_value(form, "is_active")
            error_label = ui.label("").style("color: var(--ht-error); min-height: 1.25rem;")
            error_label.set_visibility(False)
            for field_control in (
                username_input,
                email_input,
                password_input,
                role_select,
                active_checkbox,
            ):
                field_control.on_value_change(lambda _event: _clear_form_error())
            with ui.row().classes("gap-2 justify-end"):
                secondary_button(ui.button("Cancel", on_click=dialog.close))
                primary_button(ui.button("Save", on_click=submit_form))

    await load_users()
