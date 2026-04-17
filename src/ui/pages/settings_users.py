"""Settings — Users management page at /settings/users.

Admin-only page. Renders a table of all users with create, edit, and delete actions.
"""
import html
from typing import Optional

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import (
    redirect_if_insufficient_role,
    redirect_if_unauthenticated,
)
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
    users: list[dict] = []
    modal_mode = {"value": "create"}
    editing_id: dict[str, Optional[str]] = {"value": None}

    form: dict = {
        "username": "",
        "email": "",
        "password": "",
        "role": "Contributor",
        "is_active": True,
    }

    def _to_rows(users_list: list[dict]) -> list[dict]:
        return [{**u, "is_self": u["id"] == current_user_id} for u in users_list]

    async def load_users() -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(_API, headers=_auth_headers())
            resp.raise_for_status()
            users.clear()
            users.extend(resp.json())
            table.rows = _to_rows(users)
            table.update()
        except Exception as exc:
            logger.error("Failed to load users: {}", exc)
            ui.notify("Couldn't load users. Please refresh and try again.", type="negative")

    def _clear_form_error() -> None:
        error_label.set_text("")
        error_label.set_visibility(False)

    def _reset_form() -> None:
        form.update(
            {
                "username": "",
                "email": "",
                "password": "",
                "role": "Contributor",
                "is_active": True,
            }
        )
        _clear_form_error()

    def open_create_modal() -> None:
        _reset_form()
        modal_mode["value"] = "create"
        editing_id["value"] = None
        modal_title.set_text("Create User")
        dialog.open()

    def open_edit_modal(row: dict) -> None:
        _reset_form()
        form["username"] = row["username"]
        form["email"] = row["email"]
        form["role"] = row["role"]
        form["is_active"] = row["is_active"]
        modal_mode["value"] = "edit"
        editing_id["value"] = row["id"]
        modal_title.set_text("Edit User")
        dialog.open()

    async def submit_form() -> None:
        _clear_form_error()
        if modal_mode["value"] == "create" and not str(form["password"]).strip():
            error_label.set_text("Password is required.")
            error_label.set_visibility(True)
            return
        payload: dict = {
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

    async def confirm_delete(user_id: str, username: str) -> None:
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

        with ui.dialog() as confirm_dlg, ui.card():
            ui.label(f"Delete '{html.escape(username)}'?").classes("font-bold")
            with ui.row():
                ui.button("Cancel", on_click=confirm_dlg.close).props("flat")

                async def _do_delete_and_close() -> None:
                    confirm_dlg.close()
                    await do_delete()

                ui.button(
                    "Delete", on_click=_do_delete_and_close
                ).props("color=negative")
        confirm_dlg.open()

    async def _on_delete(event: object) -> None:
        args = getattr(event, "args", {})
        if not isinstance(args, dict):
            return
        user_id = str(args.get("id", ""))
        if not user_id:
            return
        username = str(args.get("username", ""))
        await confirm_delete(user_id, username)

    # --- Layout ---
    with app_shell("Users", "/settings/users", breadcrumb=["Settings", "Users"]):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("User Management").classes("text-2xl font-bold")
            ui.button("+ Add User", on_click=open_create_modal).props("color=primary")

        columns: list[dict] = [
            {"name": "username", "label": "Username", "field": "username", "sortable": True},
            {"name": "email", "label": "Email", "field": "email", "sortable": True},
            {"name": "role", "label": "Role", "field": "role", "sortable": True},
            {"name": "is_active", "label": "Active", "field": "is_active"},
            {"name": "actions", "label": "Actions", "field": "actions"},
        ]
        table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")
        table.add_slot(
            "body",
            """
            <q-tr :props="props">
                <q-td key="username">{{ props.row.username }}</q-td>
                <q-td key="email">{{ props.row.email }}</q-td>
                <q-td key="role">{{ props.row.role }}</q-td>
                <q-td key="is_active">{{ props.row.is_active ? 'Yes' : 'No' }}</q-td>
                <q-td key="actions">
                    <q-btn flat dense icon="edit"
                        @click="() => $emit('edit', props.row)" />
                    <q-btn flat dense icon="delete" color="negative"
                        :disabled="props.row.is_self"
                        @click="() => $emit('delete', props.row)" />
                </q-td>
            </q-tr>
            """,
        )
        table.on("edit", lambda e: open_edit_modal(e.args))
        table.on("delete", _on_delete)

    # --- Modal dialog ---
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        modal_title = ui.label("Create User").classes("text-xl font-bold")
        username_input = ui.input("Username").bind_value(form, "username").classes("w-full")
        email_input = ui.input("Email").bind_value(form, "email").classes("w-full")
        password_input = ui.input("Password", password=True).bind_value(form, "password").classes(
            "w-full"
        )
        role_select = ui.select(
            ["Admin", "Contributor", "Reader"],
            label="Role",
        ).bind_value(form, "role").classes("w-full")
        active_checkbox = ui.checkbox("Active").bind_value(form, "is_active")
        error_label = (
            ui.label("").style("color: var(--ht-error); font-size: 0.875rem")
        )
        error_label.set_visibility(False)
        for field_control in (
            username_input,
            email_input,
            password_input,
            role_select,
            active_checkbox,
        ):
            field_control.on_value_change(lambda _event: _clear_form_error())
        with ui.row():
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=submit_form).props("color=primary")

    await load_users()
