"""Reusable breadcrumb component for hierarchical navigation."""
from nicegui import ui


def render_breadcrumb(
    crumbs: list[tuple[str, str]],
    use_leave_guard: bool = False,
) -> None:
    """Render a breadcrumb bar. Each crumb is (label, route).

    The last crumb is rendered as non-clickable text (current page).
    """
    with ui.row().classes("items-center gap-1").style(
        "font-size:0.85rem; color:var(--ht-text-secondary)"
    ):
        guard_marker_props = 'data-ht-guard-nav="true"'
        for i, (label, route) in enumerate(crumbs):
            if i > 0:
                ui.label("/").style("color:var(--ht-text-secondary); margin:0 4px")
            if i < len(crumbs) - 1:
                if use_leave_guard:
                    with ui.row().classes("items-center cursor-pointer").props(
                        f'{guard_marker_props} data-ht-nav-target="{route}" role="link" tabindex="0"'
                    ):
                        ui.label(label).style("color:var(--ht-accent); text-decoration:none; pointer-events:none").props(
                            f'{guard_marker_props} data-ht-nav-target="{route}"'
                        )
                else:
                    ui.link(label, route).style(
                        "color:var(--ht-accent); text-decoration:none"
                    )
            else:
                ui.label(label).style("color:var(--ht-text-primary); font-weight:600")
