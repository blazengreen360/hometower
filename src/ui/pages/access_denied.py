"""Access Denied page at /403.

Shown when a user's role is insufficient to access a resource.
"""
from nicegui import ui

from src.ui.design.primitives import GLOBAL_UI_CSS
from src.ui.design.primitives import card_section
from src.ui.design.primitives import card_surface
from src.ui.design.primitives import primary_button


@ui.page("/403")
async def access_denied_page() -> None:
    """Minimal 403 Access Denied page."""
    ui.add_head_html(GLOBAL_UI_CSS)
    ui.query("body").style("background-color: var(--ht-bg-surface); color: var(--ht-text-primary)")
    with ui.column().classes("ht-auth-shell"):
        with card_surface(ui.card()).classes("ht-auth-card"):
            with card_section(ui.column()).classes("items-center text-center"):
                ui.label("403 — Access Denied").classes("ht-page-title")
                ui.label("You do not have permission to view this page.").classes("ht-muted-copy")
                primary_button(ui.button("Go to Home", on_click=lambda: ui.navigate.to("/topology")))
