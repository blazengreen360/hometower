"""Settings — Profile / password change page at /settings/profile (HT-025)."""
import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import redirect_if_unauthenticated
from src.ui.components.toast import show_toast
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import page_container
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_page_intro
from src.ui.design.primitives import secondary_button
from src.ui.utils.validation_feedback import friendly_error_message
from src.utils.logger import logger
from src.utils.settings import settings

_PASSWORD_FIELD_LABELS: dict[str, str] = {
    "current_password": "Current password",
    "new_password": "New password",
    "confirm_password": "Confirm password",
}
_PASSWORD_MESSAGE_OVERRIDES: dict[str, str] = {
    "new password must be different from current password": "New password must be different from current password.",
    "password must be at least 8 characters": "Password must be at least 8 characters.",
}


@ui.page("/settings/profile")
async def settings_profile_page() -> None:
    """Password change settings page — any authenticated role."""
    if redirect_if_unauthenticated(current_path="/settings/profile"):
        return

    with app_shell("Profile", "/settings/profile", breadcrumb=["Settings", "Profile"]):
        with page_container(ui.column()):
            with ui.row().classes("items-start w-full gap-3"):
                secondary_button(ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/"),
                ).props("dense aria-label='Back'"))
                render_page_intro(
                    ui,
                    "Change Password",
                    "Update your credentials without leaving the authenticated shell. New passwords must meet the current policy.",
                    "Settings",
                )

            with card_surface(ui.card()).classes("max-w-2xl"):
                with card_section(ui.column()):
                    current_pw = ui.input(
                        label="Current Password",
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full").props("outlined")

                    new_pw = ui.input(
                        label="New Password",
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full").props("outlined")

                    confirm_pw = ui.input(
                        label="Confirm New Password",
                        password=True,
                        password_toggle_button=True,
                    ).classes("w-full").props("outlined")

                    error_lbl = ui.label("").style(
                        "color: var(--ht-error); font-size: 0.875rem; min-height: 1.2em;"
                    )
                    error_lbl.set_visibility(False)

                    def _show_error(message: str) -> None:
                        error_lbl.set_text(message)
                        error_lbl.set_visibility(True)

                    def _clear_error() -> None:
                        error_lbl.set_text("")
                        error_lbl.set_visibility(False)

                    current_pw.on_value_change(lambda _event: _clear_error())
                    new_pw.on_value_change(lambda _event: _clear_error())
                    confirm_pw.on_value_change(lambda _event: _clear_error())

                    async def _submit() -> None:
                        _clear_error()
                        if not str(current_pw.value or "").strip():
                            _show_error("Current password is required.")
                            return
                        if not str(new_pw.value or "").strip():
                            _show_error("New password is required.")
                            return
                        if not str(confirm_pw.value or "").strip():
                            _show_error("Please confirm your new password.")
                            return
                        if new_pw.value != confirm_pw.value:
                            _show_error("Passwords do not match.")
                            return
                        token = nicegui_app.storage.user.get("access_token", "")
                        try:
                            async with httpx.AsyncClient() as c:
                                r = await c.patch(
                                    f"{settings.api_base_url}/api/auth/me/password",
                                    json={
                                        "current_password": current_pw.value,
                                        "new_password": new_pw.value,
                                    },
                                    headers={"Authorization": f"Bearer {token}"},
                                    timeout=5.0,
                                )
                            if r.status_code == 204:
                                show_toast(type="success", title="Password updated")
                                current_pw.value = ""
                                new_pw.value = ""
                                confirm_pw.value = ""
                            else:
                                _show_error(
                                    friendly_error_message(
                                        r,
                                        fallback="Couldn't update password. Please try again.",
                                        field_labels=_PASSWORD_FIELD_LABELS,
                                        status_overrides={401: "Current password is incorrect."},
                                        message_overrides=_PASSWORD_MESSAGE_OVERRIDES,
                                    )
                                )
                        except httpx.HTTPError as exc:
                            _show_error("Couldn't update password right now. Please try again.")
                            logger.error("Password change request failed: {}", str(exc))
                        except Exception as exc:
                            _show_error("Couldn't update password right now. Please try again.")
                            logger.error("Password change failed unexpectedly: {}", str(exc))

                    primary_button(ui.button("Update Password", on_click=_submit).classes("w-full"))
