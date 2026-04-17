"""Inventory page route wrapper."""
from nicegui import app as nicegui_app
from nicegui import ui

from src.models.types import Role
from src.ui.components.auth_guard import get_ui_role, redirect_if_unauthenticated
from src.ui.pages.inventory_page_controller import render_inventory_page


@ui.page("/inventory")
async def inventory_page() -> None:
    """Inventory page - delegate rendering to the page controller."""
    if redirect_if_unauthenticated(current_path="/inventory"):
        return

    token = str(nicegui_app.storage.user.get("access_token", ""))
    user_role: Role | None = get_ui_role()
    await render_inventory_page(token=token, user_role=user_role)
