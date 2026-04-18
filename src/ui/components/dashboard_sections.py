"""Composable dashboard sections for HT-082."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import primary_button
from src.ui.design.primitives import render_stat_card
from src.ui.design.primitives import secondary_button

DashboardScopeChangeHandler = Callable[[str | None], Awaitable[None]]


def _as_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _as_float(value: object) -> float | None:
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    return None


def _as_text(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _route(value: object) -> str:
    return value if isinstance(value, str) and value else "/"


def _inventory_route_with_scope(route: str, workspace_id: str | None) -> str:
    if not workspace_id:
        return route
    parsed = urlsplit(route)
    if parsed.path != "/inventory":
        return route
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key == "workspace_id" for key, _ in pairs):
        return route
    scoped_query = urlencode([("workspace_id", workspace_id), *pairs], doseq=True, quote_via=quote)
    return urlunsplit(("", "", parsed.path, scoped_query, parsed.fragment))


def _monthly_cost_copy(power: dict[str, object]) -> str:
    monthly_cost = _as_float(power.get("estimated_monthly_cost"))
    currency = power.get("currency")
    if monthly_cost is not None and isinstance(currency, str) and currency:
        return f"{monthly_cost:.2f} {currency} / month"
    return "Rate not configured"


def _workspace_select_options(power: dict[str, object]) -> dict[str, str]:
    options = power.get("workspace_options", [])
    if not isinstance(options, list):
        return {"": "All Workspaces"}
    normalized: dict[str, str] = {}
    for option in options:
        if not isinstance(option, dict):
            continue
        key = str(option.get("id") or "")
        normalized[key] = _as_text(option.get("name"), "Workspace")
    return normalized or {"": "All Workspaces"}


def render_dashboard_summary_cards(ui_module: object, summary: dict[str, object]) -> None:
    with getattr(ui_module, "row")().classes("flex-wrap gap-4"):
        render_stat_card(ui_module, "Devices", str(_as_int(summary.get("devices"))))
        render_stat_card(ui_module, "Workspaces", str(_as_int(summary.get("workspaces"))))
        render_stat_card(ui_module, "Topologies", str(_as_int(summary.get("topologies"))))
        render_stat_card(ui_module, "Offline Devices", str(_as_int(summary.get("offline_devices"))))
        render_stat_card(ui_module, "Recent Edits", str(_as_int(summary.get("recent_edits"))))


def render_dashboard_breakdown_card(
    ui_module: object,
    breakdown: dict[str, object],
    workspace_id: str | None,
) -> None:
    with card_surface(getattr(ui_module, "card")()).classes("flex-1 min-w-[320px]"):
        with card_section(getattr(ui_module, "column")()):
            getattr(ui_module, "label")("Inventory Breakdown").classes("ht-section-caption")
            with getattr(ui_module, "row")().classes("w-full gap-4 flex-wrap"):
                _render_breakdown_group(ui_module, "Status", breakdown.get("status_counts"), workspace_id)
                _render_breakdown_group(ui_module, "Type", breakdown.get("type_counts"), workspace_id)


def render_dashboard_recent_activity_card(
    ui_module: object,
    recent_activity: object,
    relative_time: Callable[[object], str],
    workspace_id: str | None,
) -> None:
    with card_surface(getattr(ui_module, "card")()):
        with card_section(getattr(ui_module, "column")()):
            getattr(ui_module, "label")("Recent Activity").classes("ht-section-caption")
            if not isinstance(recent_activity, list) or not recent_activity:
                getattr(ui_module, "label")("No recent activity yet").classes("ht-muted-copy")
                return
            for item in recent_activity:
                if not isinstance(item, dict):
                    continue
                item_route = _inventory_route_with_scope(_route(item.get("route")), workspace_id)
                with getattr(ui_module, "row")().classes("w-full items-start justify-between gap-4"):
                    with getattr(ui_module, "column")().classes("gap-1"):
                        title_link = getattr(ui_module, "link")(
                            _as_text(item.get("title"), "Activity"),
                            item_route,
                        ).classes("ht-table-link text-[var(--ht-text-primary)]")
                        title_link.props(f'href="{item_route}" data-ht-route="{item_route}"')
                        title_link.on(
                            "click",
                            lambda _event, target=item_route: getattr(ui_module, "navigate").to(target),
                        )
                        getattr(ui_module, "label")(_as_text(item.get("subtitle"), "")).classes(
                            "ht-small-copy"
                        )
                    getattr(ui_module, "label")(relative_time(item.get("timestamp"))).classes(
                        "ht-small-copy"
                    )


def render_dashboard_primary_actions(
    ui_module: object,
    *,
    can_write: bool,
    inventory_route: str,
) -> None:
    with getattr(ui_module, "row")().classes("gap-3 flex-wrap"):
        if can_write:
            primary_button(
                getattr(ui_module, "button")(
                    "Add Device",
                    icon="add",
                    on_click=lambda: getattr(ui_module, "navigate").to("/topology"),
                )
            )
        inventory_button = secondary_button(
            getattr(ui_module, "button")(
                "View Inventory",
                icon="list",
                on_click=lambda: getattr(ui_module, "navigate").to(inventory_route),
            )
        )
        if can_write:
            secondary_button(
                getattr(ui_module, "button")(
                    "Manage Locations",
                    icon="location_on",
                    on_click=lambda: getattr(ui_module, "navigate").to("/settings/locations"),
                )
            )


def render_dashboard_power_card(
    ui_module: object,
    power: dict[str, object],
    on_workspace_change: DashboardScopeChangeHandler,
) -> None:
    workspace_options = _workspace_select_options(power)
    with card_surface(getattr(ui_module, "card")()).classes("flex-1 min-w-[320px]"):
        with card_section(getattr(ui_module, "column")()):
            getattr(ui_module, "label")("Power Usage").classes("ht-section-caption")
            getattr(ui_module, "label")(
                _as_text(power.get("selected_workspace_name"), "All Workspaces")
            ).classes("ht-page-eyebrow")
            getattr(ui_module, "label")(
                f"{_as_int(power.get('total_watts'))}W"
            ).classes("ht-page-title")
            getattr(ui_module, "label")(_monthly_cost_copy(power)).classes("ht-muted-copy")
            getattr(ui_module, "label")("Workspace Scope").classes("ht-small-copy")
            workspace_select = (
                getattr(ui_module, "select")(
                    workspace_options,
                    value=str(power.get("selected_workspace_id") or ""),
                    label="Workspace Scope",
                )
                .classes("w-full max-w-[320px]")
                .props("outlined dense options-dense stack-label")
            )

            async def _refresh_power(event: object) -> None:
                selected_value = str(getattr(event, "value", "") or "")
                await on_workspace_change(selected_value or None)

            workspace_select.on_value_change(_refresh_power)


def _render_breakdown_group(
    ui_module: object,
    title: str,
    items: object,
    workspace_id: str | None,
) -> None:
    with getattr(ui_module, "column")().classes("flex-1 min-w-[220px] gap-2"):
        getattr(ui_module, "label")(title).classes("ht-section-caption")
        if not isinstance(items, list) or not items:
            getattr(ui_module, "label")("No data yet").classes("ht-small-copy")
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            route = _inventory_route_with_scope(_route(item.get("route")), workspace_id)
            with getattr(ui_module, "row")().classes("w-full items-center justify-between gap-3"):
                link = getattr(ui_module, "link")(
                    _as_text(item.get("key"), "Unknown"),
                    route,
                ).classes("ht-table-link rounded-full")
                link.props(f'href="{route}" data-ht-route="{route}"')
                link.on(
                    "click",
                    lambda _event, target=route: getattr(ui_module, "navigate").to(target),
                )
                getattr(ui_module, "label")(str(_as_int(item.get("count")))).classes("ht-small-copy")
