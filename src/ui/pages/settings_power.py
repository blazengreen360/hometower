"""Settings — Power configuration page at /settings/power."""

from __future__ import annotations

import html

import httpx
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.app_shell import app_shell
from src.ui.components.auth_guard import (
    redirect_if_insufficient_role,
    redirect_if_unauthenticated,
)
from src.ui.components.toast import show_toast
from src.utils.logger import logger
from src.utils.settings import settings

_POWER_SETTINGS_API = f"{settings.api_base_url}/api/power/settings"


def _auth_headers() -> dict[str, str]:
    token = nicegui_app.storage.user.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _normalize_currency(value: str) -> str | None:
    cleaned = value.strip().upper()
    return cleaned or None


def _parse_cost_input(value: str) -> float | str | None:
    cleaned = value.strip()
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return cleaned


def _extract_error_detail(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
    except Exception:
        return f"Request failed ({resp.status_code})"

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                msg = first.get("msg")
                if isinstance(msg, str) and msg.strip():
                    return msg
    return f"Request failed ({resp.status_code})"


@ui.page("/settings/power")
async def settings_power_page() -> None:
    """Admin-only settings page for electricity rate and currency."""
    if redirect_if_unauthenticated(current_path="/settings/power"):
        return
    if redirect_if_insufficient_role(Role.Admin):
        return

    with app_shell("Power", "/settings/power", breadcrumb=["Settings", "Power"]):
        with ui.column().classes("w-full max-w-3xl gap-4"):
            ui.label("Power Settings").style(
                "font-size:1.5rem; font-weight:700; color:var(--ht-text-primary);"
            )
            ui.label(
                "Configure electricity cost used for dashboard and map power estimates."
            ).style("font-size:0.9rem; color:var(--ht-text-secondary);")

            with ui.card().classes("w-full").style(
                "background:var(--ht-bg-surface-raised); border:1px solid var(--ht-border);"
                " border-radius:var(--ht-radius-card);"
            ):
                with ui.column().classes("w-full gap-3 p-4"):
                    with ui.row().classes("w-full gap-3 items-end"):
                        cost_input = (
                            ui.input("Cost per kWh", value="")
                            .props("type=number min=0 step=0.0001")
                            .classes("w-56")
                        )
                        currency_input = (
                            ui.input("Currency", value="")
                            .props("maxlength=3")
                            .classes("w-36")
                        )

                    ui.label("Formula: monthly kWh = total watts x 24 x 30.44 / 1000").style(
                        "font-size:0.8rem; color:var(--ht-text-secondary);"
                    )
                    ui.label(
                        "Costs are estimates and depend on devices with known power values."
                    ).style("font-size:0.8rem; color:var(--ht-text-secondary);")

                    updated_label = ui.label("Last updated: unknown").style(
                        "font-size:0.8rem; color:var(--ht-text-secondary);"
                    )
                    error_label = ui.label("").style(
                        "font-size:0.85rem; color:var(--ht-error);"
                    )
                    error_label.set_visibility(False)

                    def _clear_error() -> None:
                        error_label.set_text("")
                        error_label.set_visibility(False)

                    def _set_error(message: str) -> None:
                        error_label.set_text(message)
                        error_label.set_visibility(True)

                    def _set_form_values(
                        *,
                        cost_per_kwh: object,
                        currency: object,
                        updated_at: object,
                    ) -> None:
                        cost_input.set_value("" if cost_per_kwh is None else str(cost_per_kwh))
                        currency_input.set_value(
                            "" if currency is None else str(currency).upper()
                        )
                        if isinstance(updated_at, str) and updated_at.strip():
                            updated_label.set_text(f"Last updated: {updated_at}")
                        else:
                            updated_label.set_text("Last updated: never")

                    async def _load_settings() -> None:
                        _clear_error()
                        try:
                            async with httpx.AsyncClient() as client:
                                response = await client.get(
                                    _POWER_SETTINGS_API,
                                    headers=_auth_headers(),
                                    timeout=8.0,
                                )
                        except httpx.HTTPError as exc:
                            logger.error("Power settings load failed: {}", str(exc))
                            _set_error("Unable to load power settings")
                            return

                        if response.status_code != 200:
                            _set_error(html.escape(_extract_error_detail(response)))
                            return

                        payload = response.json()
                        body = payload if isinstance(payload, dict) else {}
                        _set_form_values(
                            cost_per_kwh=body.get("cost_per_kwh"),
                            currency=body.get("currency"),
                            updated_at=body.get("updated_at"),
                        )

                    async def _save_settings() -> None:
                        _clear_error()
                        raw_cost = str(cost_input.value or "").strip()
                        normalized_currency = _normalize_currency(
                            str(currency_input.value or "")
                        )

                        if raw_cost == "" and normalized_currency is None:
                            payload: dict[str, object] = {
                                "cost_per_kwh": None,
                                "currency": None,
                            }
                        else:
                            payload = {
                                "cost_per_kwh": _parse_cost_input(raw_cost),
                                "currency": normalized_currency,
                            }

                        try:
                            async with httpx.AsyncClient() as client:
                                response = await client.put(
                                    _POWER_SETTINGS_API,
                                    json=payload,
                                    headers=_auth_headers(),
                                    timeout=8.0,
                                )
                        except httpx.HTTPError as exc:
                            logger.error("Power settings save failed: {}", str(exc))
                            _set_error("Unable to save power settings")
                            show_toast(type="error", title="Power settings save failed")
                            return

                        if response.status_code != 200:
                            message = _extract_error_detail(response)
                            _set_error(html.escape(message))
                            show_toast(
                                type="error",
                                title="Power settings save failed",
                                description=message,
                            )
                            return

                        payload_out = response.json()
                        body = payload_out if isinstance(payload_out, dict) else {}
                        _set_form_values(
                            cost_per_kwh=body.get("cost_per_kwh"),
                            currency=body.get("currency"),
                            updated_at=body.get("updated_at"),
                        )
                        show_toast(type="success", title="Power settings saved")

                    def _clear_form() -> None:
                        cost_input.set_value("")
                        currency_input.set_value("")
                        updated_label.set_text("Last updated: unsaved changes")
                        _clear_error()
                        show_toast(
                            type="info",
                            title="Fields cleared",
                            description="Click Save settings to persist the cleared values.",
                        )

                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Clear", on_click=_clear_form).props("flat")
                        ui.button("Save settings", on_click=_save_settings).props(
                            "color=primary"
                        )

            await _load_settings()
