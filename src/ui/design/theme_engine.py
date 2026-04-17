"""Theme engine — CSS custom property injection for HT-027.

Hides how CSS custom properties are built and injected into the browser.
If we switch from inline style injection to a CSS-in-JS approach, only
this file changes.

Public API
----------
build_css_var_dict(theme_name)   → dict of --ht-* prop → value
get_initial_theme_css(theme_name) → <style> block for ui.add_head_html()
get_theme_js_helpers()            → <script> block for ui.add_head_html()
apply_theme_to_client(theme_name) → async; calls ui.run_javascript()
"""
import json

from src.ui.design.tokens import STATIC_CSS_VARS, THEMES

_THEME_JS_TEMPLATE = """
(function() {
    if (window._htThemeJsLoaded) return;
    window._htThemeJsLoaded = true;

    window.htApplyThemeVars = function(vars) {
        var root = document.documentElement;
        Object.keys(vars).forEach(function(k) {
            root.style.setProperty(k, vars[k]);
        });
    };

    window._htThemeColors = function() {
        var s = getComputedStyle(document.documentElement);
        return {
            success:         s.getPropertyValue('--ht-success').trim(),
            error:           s.getPropertyValue('--ht-error').trim(),
            textPrimary:     s.getPropertyValue('--ht-text-primary').trim(),
            textSecondary:   s.getPropertyValue('--ht-text-secondary').trim(),
            bgSurfaceRaised: s.getPropertyValue('--ht-bg-surface-raised').trim(),
        };
    };
})();
"""


def build_css_var_dict(theme_name: str) -> dict[str, str]:
    """Return dict of all CSS custom property names → values for the named theme.

    Combines theme-specific tokens and static structural tokens.
    Falls back to 'dark' if the theme name is unknown.
    """
    theme = THEMES.get(theme_name, THEMES["dark"])
    dynamic: dict[str, str] = {
        f"--ht-{k.replace('_', '-')}": v
        for k, v in theme.items()
    }
    return {**STATIC_CSS_VARS, **dynamic}


def get_initial_theme_css(theme_name: str) -> str:
    """Return a <link> + <style> block for server-side injection via ui.add_head_html().

    Injects a <style id="ht-theme"> block that sets CSS custom properties on
    :root for the given theme. Uses system font stacks — no external font
    requests, so the Content-Security-Policy is never relaxed.
    """
    css_vars = build_css_var_dict(theme_name)
    props = "\n".join(
        f"  {k}: {v};"
        for k, v in css_vars.items()
    )
    style_tag = f'<style id="ht-theme">\n:root {{\n{props}\n}}\n</style>'
    return style_tag


def get_theme_js_helpers() -> str:
    """Return a <script> block defining window.htApplyThemeVars and window._htThemeColors.

    Must be injected once via ui.add_head_html(). The script is idempotent —
    a _htThemeJsLoaded guard prevents double execution.
    """
    return f"<script>{_THEME_JS_TEMPLATE}</script>"


async def apply_theme_to_client(theme_name: str) -> None:
    """Update CSS custom properties on the current page without reload.

    Awaited so JS exceptions propagate to the Python caller for logging.
    """
    from nicegui import ui  # local import avoids circular import at module load

    css_vars = build_css_var_dict(theme_name)
    await ui.run_javascript(f"htApplyThemeVars({json.dumps(css_vars)})")
