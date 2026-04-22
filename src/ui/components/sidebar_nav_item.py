"""Sidebar nav-item renderer extracted to keep sidebar.py bounded and simple."""

from collections.abc import Callable

from nicegui import ui


def _nav_item_styles(active: bool, use_leave_guard: bool) -> tuple[str, str, str]:
    active_style = (
        "background-color:var(--ht-accent-glow); border-left:3px solid var(--ht-accent);"
        if active
        else "background-color:transparent; border-left:3px solid transparent;"
    )
    text_color = "var(--ht-accent)" if active else "var(--ht-text-primary)"
    guard_child_style = " pointer-events:none;" if use_leave_guard else ""
    return active_style, text_color, guard_child_style


def _build_click_handler(
    route: str,
    disabled: bool,
    use_leave_guard: bool,
    ui_module=ui,
) -> Callable[[], None] | None:
    if use_leave_guard:
        return None

    def _on_click_direct() -> None:
        if disabled:
            return
        ui_module.navigate.to(route)

    return _on_click_direct


def _apply_row_navigation(
    row: ui.row,
    click_handler: Callable[[], None] | None,
    use_leave_guard: bool,
    disabled: bool,
    guard_props: str,
    guard_target_props: str,
    guard_disabled_props: str,
) -> None:
    if use_leave_guard:
        row.props(guard_props)
        row.props(guard_disabled_props if disabled else f'{guard_target_props} role="link" tabindex="0"')
        return
    if click_handler is not None:
        row.on("click", click_handler)


def _apply_guard_child_props(
    icon_el: ui.icon,
    label_el: ui.label,
    disabled: bool,
    guard_props: str,
    guard_target_props: str,
    guard_disabled_props: str,
) -> None:
    icon_el.props(guard_props)
    label_el.props(guard_props)
    if disabled:
        icon_el.props(guard_disabled_props)
        label_el.props(guard_disabled_props)
        return
    icon_el.props(guard_target_props)
    label_el.props(guard_target_props)


def _nav_item(
    label: str,
    icon: str,
    route: str,
    active: bool,
    disabled: bool,
    use_leave_guard: bool,
    ui_module=ui,
) -> None:
    """Render a single sidebar navigation row."""
    active_style, text_color, guard_child_style = _nav_item_styles(active, use_leave_guard)
    click_handler = _build_click_handler(route, disabled, use_leave_guard, ui_module=ui_module)
    guard_props = 'data-ht-guard-nav="true"'
    guard_target_props = f'data-ht-nav-target="{route}"'
    guard_disabled_props = 'data-ht-nav-disabled="true" aria-disabled="true"'

    row = ui_module.row().classes(
        "items-center px-3 py-2 cursor-pointer w-full ht-nav-item rounded-r-[10px]"
    ).style(
        active_style + f" color:{text_color};"
        " transition:background-color var(--ht-transition-fast);"
    )
    _apply_row_navigation(
        row,
        click_handler,
        use_leave_guard,
        disabled,
        guard_props,
        guard_target_props,
        guard_disabled_props,
    )

    with row:
        icon_el = ui_module.icon(icon).style(f"color:{text_color}; font-size:1.25rem;{guard_child_style}")
        label_el = ui_module.label(label).style(
            f"font-weight:{'600' if active else '400'}; font-size:0.875rem;{guard_child_style}"
        )
        if use_leave_guard:
            _apply_guard_child_props(
                icon_el,
                label_el,
                disabled,
                guard_props,
                guard_target_props,
                guard_disabled_props,
            )
        if disabled:
            ui_module.badge("soon").classes("bg-[var(--ht-bg-base)] text-[var(--ht-text-secondary)]")