"""Shared UI primitives for HT-080.

Keeps common presentation helpers in one place so pages can compose a
consistent shell without re-styling every card, button, and table by hand.
"""
from typing import TypeVar

T = TypeVar("T")

GLOBAL_UI_CSS = """
<style id="ht-ui-primitives">
  .ht-page-shell { width:min(var(--ht-page-max), 100%); margin:0 auto; padding:28px 24px 40px; gap:24px; }
  .ht-page-header { gap:8px; }
  .ht-page-kicker { color:var(--ht-text-secondary); font-size:var(--ht-font-caption); font-weight:700; letter-spacing:0.18em; text-transform:uppercase; }
  .ht-page-title { color:var(--ht-text-primary); font-size:var(--ht-font-h1); font-weight:750; letter-spacing:-0.04em; line-height:1.02; }
  .ht-page-eyebrow { color:var(--ht-text-secondary); font-size:var(--ht-font-label); font-weight:650; letter-spacing:0.08em; text-transform:uppercase; }
  .ht-page-subtitle { max-width:72ch; color:var(--ht-text-secondary); font-size:var(--ht-font-body-lg); line-height:1.6; }
  .ht-section-title { color:var(--ht-text-primary); font-size:var(--ht-font-title); font-weight:700; letter-spacing:-0.02em; }
  .ht-section-caption { color:var(--ht-text-secondary); font-size:var(--ht-font-caption); font-weight:700; letter-spacing:0.14em; text-transform:uppercase; }
  .ht-muted-copy { color:var(--ht-text-secondary); font-size:var(--ht-font-body); line-height:1.55; }
  .ht-small-copy { color:var(--ht-text-secondary); font-size:var(--ht-font-caption); line-height:1.5; }
  .ht-card { position:relative; background:color-mix(in srgb, var(--ht-bg-surface-raised) 92%, transparent); border:1px solid var(--ht-border); border-radius:var(--ht-radius-card); box-shadow:var(--ht-shadow-sm); overflow:hidden; }
    .ht-card::before { content:''; position:absolute; inset:0 0 auto 0; height:1px; background:linear-gradient(90deg, transparent, color-mix(in srgb, var(--ht-accent) 55%, var(--ht-text-on-accent) 0%), transparent); opacity:0.65; pointer-events:none; }
  .ht-card-section { width:100%; padding:20px; gap:14px; }
  .ht-card-hover { transition:transform var(--ht-transition-norm), box-shadow var(--ht-transition-norm), border-color var(--ht-transition-norm); }
  .ht-card-hover:hover { transform:translateY(-1px); box-shadow:var(--ht-shadow-md); border-color:color-mix(in srgb, var(--ht-accent) 24%, var(--ht-border)); }
  .ht-stat-value { color:var(--ht-text-primary); font-size:clamp(1.8rem, 2.4vw, 2.6rem); font-weight:750; letter-spacing:-0.04em; line-height:1; }
  .ht-stat-label { color:var(--ht-text-secondary); font-size:var(--ht-font-caption); font-weight:700; letter-spacing:0.16em; text-transform:uppercase; }
  .ht-btn { min-height:42px; border-radius:var(--ht-radius-input); font-weight:650; letter-spacing:0.01em; padding-inline:14px; transition:transform var(--ht-transition-fast), box-shadow var(--ht-transition-fast), background-color var(--ht-transition-fast); }
  .ht-btn:hover { transform:translateY(-1px); }
  .ht-btn-primary { background:var(--ht-accent) !important; color:var(--ht-text-on-accent) !important; box-shadow:var(--ht-shadow-sm); }
  .ht-btn-primary:hover { box-shadow:var(--ht-shadow-md); }
  .ht-btn-secondary { background:color-mix(in srgb, var(--ht-bg-surface-raised) 78%, transparent) !important; color:var(--ht-text-primary) !important; border:1px solid var(--ht-border); }
  .ht-btn-danger { background:color-mix(in srgb, var(--ht-error) 12%, var(--ht-bg-surface-raised)) !important; color:var(--ht-error) !important; border:1px solid color-mix(in srgb, var(--ht-error) 35%, var(--ht-border)); }
    .ht-btn-icon { min-width:28px; min-height:28px; padding:0 !important; border-radius:var(--ht-radius-input); transition:background-color var(--ht-transition-fast), color var(--ht-transition-fast); }
    .ht-btn-icon-secondary { color:var(--ht-text-secondary) !important; }
    .ht-btn-icon-secondary:hover { background:color-mix(in srgb, var(--ht-bg-surface-raised) 82%, transparent) !important; color:var(--ht-text-primary) !important; }
  .ht-btn-icon-danger { color:var(--ht-error) !important; border-radius:var(--ht-radius-input); }
  .ht-btn-icon-danger:hover { background:color-mix(in srgb, var(--ht-error) 12%, transparent) !important; }
    .ht-btn-icon-on-accent { color:var(--ht-text-on-accent) !important; }
    .ht-btn-icon-on-accent:hover { background:color-mix(in srgb, var(--ht-text-on-accent) 12%, transparent) !important; }
    .ht-filter-chip { background:color-mix(in srgb, var(--ht-bg-surface-raised) 86%, transparent) !important; color:var(--ht-text-primary) !important; border:1px solid var(--ht-border) !important; transition:background-color var(--ht-transition-fast), border-color var(--ht-transition-fast), color var(--ht-transition-fast); }
    .ht-filter-chip:hover { border-color:color-mix(in srgb, var(--ht-chip-accent, var(--ht-accent)) 36%, var(--ht-border)) !important; }
    .ht-filter-chip-active { background:var(--ht-chip-accent, var(--ht-accent)) !important; color:var(--ht-text-on-accent) !important; border-color:color-mix(in srgb, var(--ht-chip-accent, var(--ht-accent)) 44%, var(--ht-border)) !important; }
  .ht-data-table { width:100%; border-radius:var(--ht-radius-card); overflow:hidden; box-shadow:var(--ht-shadow-sm); border:1px solid var(--ht-border); background:color-mix(in srgb, var(--ht-bg-surface-raised) 92%, transparent); }
  .ht-data-table .q-table__top,
  .ht-data-table .q-table__middle,
  .ht-data-table .q-table,
  .ht-data-table thead,
  .ht-data-table tbody,
  .ht-data-table tr,
  .ht-data-table th,
  .ht-data-table td { background:transparent; color:var(--ht-text-primary); }
  .ht-data-table thead th { color:var(--ht-text-secondary); font-size:var(--ht-font-caption); font-weight:700; letter-spacing:0.14em; text-transform:uppercase; border-bottom:1px solid var(--ht-border); }
  .ht-data-table tbody tr { transition:background-color var(--ht-transition-fast); }
  .ht-data-table tbody tr:hover { background:color-mix(in srgb, var(--ht-accent) 6%, var(--ht-bg-surface) 94%); }
  .ht-table-link { color:var(--ht-accent); text-decoration:none; font-weight:650; }
  .ht-table-link:hover { text-decoration:underline; }
  .ht-cell-empty { color:var(--ht-text-secondary); }
  .ht-progress-track { width:100%; height:8px; border-radius:var(--ht-radius-pill); background:color-mix(in srgb, var(--ht-bg-base) 55%, var(--ht-bg-surface)); overflow:hidden; }
    .ht-progress-bar { height:100%; border-radius:var(--ht-radius-pill); background:linear-gradient(90deg, color-mix(in srgb, var(--ht-accent) 78%, var(--ht-text-on-accent) 0%), var(--ht-accent)); }
  .ht-auth-shell { min-height:100vh; display:flex; align-items:center; justify-content:center; padding:28px; }
  .ht-auth-card { width:min(420px, 100%); }
  .ht-banner { width:100%; border-radius:var(--ht-radius-input); border:1px solid var(--ht-border); padding:10px 12px; }
  .ht-banner-info { background:color-mix(in srgb, var(--ht-success) 12%, var(--ht-bg-surface-raised)); border-color:color-mix(in srgb, var(--ht-success) 32%, var(--ht-border)); }
  .ht-banner-warn { background:color-mix(in srgb, var(--ht-warning) 12%, var(--ht-bg-surface-raised)); border-color:color-mix(in srgb, var(--ht-warning) 32%, var(--ht-border)); color:var(--ht-text-primary); }
  .ht-danger-copy { color:var(--ht-error); font-size:var(--ht-font-body); line-height:1.55; }
  .ht-form-error { color:var(--ht-error); font-size:0.84rem; min-height:1.25rem; }
  .ht-keyline { width:100%; height:1px; background:linear-gradient(90deg, transparent, var(--ht-border), transparent); }
  .q-field--outlined .q-field__control { border-radius:var(--ht-radius-input); background:color-mix(in srgb, var(--ht-bg-surface-raised) 86%, transparent); color:var(--ht-text-primary); }
  .q-field--outlined .q-field__control:before { border-color:var(--ht-border); }
  .q-field--outlined .q-field__control:hover:before { border-color:color-mix(in srgb, var(--ht-accent) 30%, var(--ht-border)); }
  .q-field--focused .q-field__control:after { border-color:var(--ht-accent); }
  .q-field__label, .q-field__native, .q-field__input, .q-field__marginal, .q-select__dropdown-icon { color:var(--ht-text-primary); }
  .q-checkbox__label, .q-radio__label, .q-toggle__label { color:var(--ht-text-primary); }
  .q-chip { border:1px solid color-mix(in srgb, var(--ht-border) 82%, transparent); }
</style>
"""


def _apply_classes(element: T, classes: str) -> T:
    class_setter = getattr(element, "classes", None)
    if callable(class_setter):
        class_setter(classes)
    return element


def _apply_props(element: T, props: str) -> T:
    prop_setter = getattr(element, "props", None)
    if callable(prop_setter):
        prop_setter(props)
    return element


def page_container(element: T) -> T:
    return _apply_classes(element, "w-full ht-page-shell")


def card_surface(element: T) -> T:
    return _apply_classes(element, "w-full ht-card")


def card_section(element: T) -> T:
    return _apply_classes(element, "ht-card-section")


def primary_button(element: T) -> T:
    _apply_props(element, "unelevated no-caps")
    return _apply_classes(element, "ht-btn ht-btn-primary")


def secondary_button(element: T) -> T:
    _apply_props(element, "flat no-caps")
    return _apply_classes(element, "ht-btn ht-btn-secondary")


def danger_button(element: T) -> T:
    _apply_props(element, "flat no-caps")
    return _apply_classes(element, "ht-btn ht-btn-danger")


def secondary_icon_button(element: T) -> T:
    _apply_props(element, "flat dense round size=xs")
    return _apply_classes(element, "ht-btn-icon ht-btn-icon-secondary")


def danger_icon_button(element: T) -> T:
    _apply_props(element, "flat dense round size=xs")
    return _apply_classes(element, "ht-btn-icon ht-btn-icon-danger")


def on_accent_icon_button(element: T) -> T:
    _apply_props(element, "flat dense round size=xs")
    return _apply_classes(element, "ht-btn-icon ht-btn-icon-on-accent")


def set_filter_chip_state(element: T, accent: str, active: bool) -> T:
    style_setter = getattr(element, "style", None)
    if callable(style_setter):
        style_setter(f"--ht-chip-accent:{accent};")
    _apply_classes(element, "ht-filter-chip")
    class_setter = getattr(element, "classes", None)
    if not callable(class_setter):
        return element
    if active:
        class_setter(add="ht-filter-chip-active", remove="ht-filter-chip-inactive")
    else:
        class_setter(add="ht-filter-chip-inactive", remove="ht-filter-chip-active")
    return element


def table_surface(element: T) -> T:
    _apply_props(element, "flat bordered separator=horizontal")
    return _apply_classes(element, "w-full ht-data-table")


def render_page_intro(
    ui_module: object,
    title: str,
    description: str,
    kicker: str | None = None,
) -> None:
    with getattr(ui_module, "column")().classes("ht-page-header"):
        if kicker:
            getattr(ui_module, "label")(kicker).classes("ht-page-kicker")
        getattr(ui_module, "label")(title).classes("ht-page-title")
        getattr(ui_module, "label")(description).classes("ht-page-subtitle")


def render_stat_card(ui_module: object, label: str, value: str) -> None:
    with card_surface(getattr(ui_module, "card")()).classes("min-w-[150px] flex-1 ht-card-hover"):
        with card_section(getattr(ui_module, "column")()).classes("items-start"):
            getattr(ui_module, "label")(value).classes("ht-stat-value")
            getattr(ui_module, "label")(label).classes("ht-stat-label")
