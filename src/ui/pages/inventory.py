"""Inventory page route wrapper."""
from fastapi import Request
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.auth_guard import get_ui_role, redirect_if_unauthenticated
from src.ui.pages.inventory_page_controller import render_inventory_page


@ui.page("/inventory")
async def inventory_page(request: Request) -> None:
    """Inventory page - delegate rendering to the page controller."""
    if redirect_if_unauthenticated(current_path="/inventory"):
        return

    token = str(nicegui_app.storage.user.get("access_token", ""))
    user_role: Role | None = get_ui_role()
    initial_workspace_id = request.query_params.get("workspace_id")
    initial_search = request.query_params.get("search")
    initial_type = request.query_params.get("type")
    initial_status = request.query_params.get("status")
    if initial_workspace_id or initial_search or initial_type or initial_status:
        await render_inventory_page(
            token=token,
            user_role=user_role,
            initial_workspace_id=initial_workspace_id,
            initial_search=initial_search,
            initial_type=initial_type,
            initial_status=initial_status,
        )
        return
    await render_inventory_page(token=token, user_role=user_role)
