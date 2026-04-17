"""Access Denied page at /403.

Shown when a user's role is insufficient to access a resource.
"""
from nicegui import ui


@ui.page("/403")
async def access_denied_page() -> None:
    """Minimal 403 Access Denied page."""
    ui.query("body").style("background-color: var(--ht-bg-surface); color: var(--ht-text-primary)")
    with ui.column().classes("absolute-center items-center gap-4"):
        ui.label("403 \u2014 Access Denied").style(
            "font-size: 1.5rem; font-weight: 700; color: var(--ht-error)"
        )
        ui.label("You do not have permission to view this page.").style(
            "color: var(--ht-text-primary)"
        )
        ui.button("Go to Home", on_click=lambda: ui.navigate.to("/topology")).style(
            "background-color: var(--ht-accent); color: var(--ht-text-on-accent);"
        )
