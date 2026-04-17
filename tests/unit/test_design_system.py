"""Unit tests for HT-027: Theme Engine Core.

Tests cover:
  - THEMES dict structure (all themes have same keys)
  - get_initial_theme_css output format
  - Backward-compatible COLOR_* aliases match dark theme values
  - build_theme_style_json returns valid JSON
  - Theme switcher presence in app_shell source
  - Login page injects theme CSS
  - STATIC_CSS_VARS keys use --ht- prefix
  - build_css_var_dict returns merged dict
  - updateCyTheme JS global registered in canvas
"""
import inspect
import json


class TestThemesDict:
    """THEMES has three palettes: dark, light, midnight — all with identical keys."""

    def _themes(self) -> dict[str, dict[str, str]]:
        from src.ui.design.tokens import THEMES
        return THEMES

    def test_has_dark_theme(self) -> None:
        assert "dark" in self._themes()

    def test_has_light_theme(self) -> None:
        assert "light" in self._themes()

    def test_has_midnight_theme(self) -> None:
        assert "midnight" in self._themes()

    def test_all_themes_have_same_keys(self) -> None:
        themes = self._themes()
        dark_keys = set(themes["dark"].keys())
        for name, palette in themes.items():
            assert set(palette.keys()) == dark_keys, (
                f"Theme '{name}' is missing keys: {dark_keys - set(palette.keys())}"
                f" or has extra keys: {set(palette.keys()) - dark_keys}"
            )

    def test_dark_theme_has_required_tokens(self) -> None:
        dark = self._themes()["dark"]
        required = [
            "bg_base", "bg_surface", "bg_surface_raised", "bg_sidebar",
            "accent", "accent_hover", "accent_glow",
            "text_primary", "text_secondary", "text_on_accent",
            "border",
            "success", "warning", "error",
            "shadow_sm", "shadow_md", "shadow_lg",
        ]
        for key in required:
            assert key in dark, f"Missing key '{key}' in dark theme"

    def test_all_themes_have_ipam_tokens(self) -> None:
        required = ["ipam_used", "ipam_free", "ipam_gateway", "ipam_conflict", "ipam_reserved"]
        for _, palette in self._themes().items():
            for key in required:
                assert key in palette

    def test_dark_accent_is_indigo(self) -> None:
        assert self._themes()["dark"]["accent"] == "#6366f1"

    def test_light_bg_base_is_slate50(self) -> None:
        assert self._themes()["light"]["bg_base"] == "#f8fafc"

    def test_midnight_accent_is_cyan(self) -> None:
        assert self._themes()["midnight"]["accent"] == "#00e5ff"


class TestStaticCssVars:
    """STATIC_CSS_VARS uses --ht- prefix and contains radius/transition/font tokens."""

    def _static(self) -> dict[str, str]:
        from src.ui.design.tokens import STATIC_CSS_VARS
        return STATIC_CSS_VARS

    def test_all_keys_use_ht_prefix(self) -> None:
        for key in self._static():
            assert key.startswith("--ht-"), f"Key '{key}' missing '--ht-' prefix"

    def test_has_radius_card(self) -> None:
        assert "--ht-radius-card" in self._static()

    def test_has_transition_fast(self) -> None:
        assert "--ht-transition-fast" in self._static()

    def test_has_font_body(self) -> None:
        assert "--ht-font-body" in self._static()

    def test_has_font_mono(self) -> None:
        assert "--ht-font-mono" in self._static()


class TestColorAliases:
    """Backward-compatible COLOR_* aliases point to dark theme values."""

    def _aliases(self) -> tuple[str, str, str, str, str, str, str, str, str]:
        from src.ui.design.tokens import (
            COLOR_ERROR,
            COLOR_PRIMARY,
            COLOR_PRIMARY_DARK,
            COLOR_SUCCESS,
            COLOR_SURFACE,
            COLOR_SURFACE_ALT,
            COLOR_TEXT,
            COLOR_TEXT_MUTED,
            COLOR_WARNING,
        )
        return (
            COLOR_PRIMARY, COLOR_PRIMARY_DARK, COLOR_SURFACE, COLOR_SURFACE_ALT,
            COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING,
        )

    def test_color_primary_matches_dark_accent(self) -> None:
        from src.ui.design.tokens import COLOR_PRIMARY, THEMES
        assert COLOR_PRIMARY == THEMES["dark"]["accent"]

    def test_color_primary_dark_matches_dark_accent_hover(self) -> None:
        from src.ui.design.tokens import COLOR_PRIMARY_DARK, THEMES
        assert COLOR_PRIMARY_DARK == THEMES["dark"]["accent_hover"]

    def test_color_surface_matches_dark_bg_surface(self) -> None:
        from src.ui.design.tokens import COLOR_SURFACE, THEMES
        assert COLOR_SURFACE == THEMES["dark"]["bg_surface"]

    def test_color_surface_alt_matches_dark_bg_surface_raised(self) -> None:
        from src.ui.design.tokens import COLOR_SURFACE_ALT, THEMES
        assert COLOR_SURFACE_ALT == THEMES["dark"]["bg_surface_raised"]

    def test_color_text_matches_dark_text_primary(self) -> None:
        from src.ui.design.tokens import COLOR_TEXT, THEMES
        assert COLOR_TEXT == THEMES["dark"]["text_primary"]

    def test_color_text_muted_matches_dark_text_secondary(self) -> None:
        from src.ui.design.tokens import COLOR_TEXT_MUTED, THEMES
        assert COLOR_TEXT_MUTED == THEMES["dark"]["text_secondary"]

    def test_color_error_matches_dark_error(self) -> None:
        from src.ui.design.tokens import COLOR_ERROR, THEMES
        assert COLOR_ERROR == THEMES["dark"]["error"]

    def test_color_success_matches_dark_success(self) -> None:
        from src.ui.design.tokens import COLOR_SUCCESS, THEMES
        assert COLOR_SUCCESS == THEMES["dark"]["success"]

    def test_color_warning_matches_dark_warning(self) -> None:
        from src.ui.design.tokens import COLOR_WARNING, THEMES
        assert COLOR_WARNING == THEMES["dark"]["warning"]

    def test_device_type_colors_still_present(self) -> None:
        from src.ui.design.tokens import DEVICE_TYPE_COLORS
        from src.models.types import DeviceType
        assert DeviceType.Server in DEVICE_TYPE_COLORS
        assert len(DEVICE_TYPE_COLORS) > 0

    def test_spacing_constants_still_present(self) -> None:
        from src.ui.design.tokens import SPACING_MD, SPACING_SM, SPACING_LG, SPACING_XS, SPACING_XL
        assert SPACING_MD == "16px"

    def test_font_constants_still_present(self) -> None:
        from src.ui.design.tokens import FONT_MONO, FONT_SM, FONT_MD, FONT_LG
        assert "Fira Mono" in FONT_MONO


class TestBuildCssVarDict:
    """build_css_var_dict combines theme tokens + static vars with --ht- prefix."""

    def _build(self, theme: str) -> dict[str, str]:
        from src.ui.design.theme_engine import build_css_var_dict
        return build_css_var_dict(theme)

    def test_all_keys_use_ht_prefix(self) -> None:
        result = self._build("dark")
        for key in result:
            assert key.startswith("--ht-"), f"Key '{key}' missing '--ht-' prefix"

    def test_bg_base_key_present(self) -> None:
        assert "--ht-bg-base" in self._build("dark")

    def test_accent_key_present(self) -> None:
        assert "--ht-accent" in self._build("dark")

    def test_static_radius_card_present(self) -> None:
        assert "--ht-radius-card" in self._build("dark")

    def test_unknown_theme_falls_back_to_dark(self) -> None:
        result_unknown = self._build("nonexistent")
        result_dark = self._build("dark")
        assert result_unknown["--ht-accent"] == result_dark["--ht-accent"]

    def test_light_theme_produces_light_values(self) -> None:
        result = self._build("light")
        from src.ui.design.tokens import THEMES
        assert result["--ht-bg-base"] == THEMES["light"]["bg_base"]

    def test_key_mapping_replaces_underscores_with_dashes(self) -> None:
        result = self._build("dark")
        # bg_surface → --ht-bg-surface (not --ht-bg_surface)
        assert "--ht-bg-surface" in result
        assert "--ht-text-primary" in result
        assert "--ht-shadow-sm" in result

    def test_ipam_css_vars_present(self) -> None:
        result = self._build("dark")
        assert "--ht-ipam-used" in result
        assert "--ht-ipam-conflict" in result


class TestGetInitialThemeCss:
    """get_initial_theme_css returns valid <style> tag with CSS vars."""

    def _get_css(self, theme: str = "dark") -> str:
        from src.ui.design.theme_engine import get_initial_theme_css
        return get_initial_theme_css(theme)

    def test_returns_string(self) -> None:
        assert isinstance(self._get_css(), str)

    def test_contains_style_tag(self) -> None:
        assert "<style" in self._get_css()

    def test_contains_root_selector(self) -> None:
        assert ":root" in self._get_css()

    def test_contains_ht_prefix_vars(self) -> None:
        assert "--ht-" in self._get_css()

    def test_no_external_font_links(self) -> None:
        """CSP compliance: no external font resources must be injected."""
        css = self._get_css()
        assert "fonts.googleapis.com" not in css
        assert "fonts.gstatic.com" not in css

    def test_font_body_var_uses_system_stack(self) -> None:
        """--ht-font-body must reference Inter via system font stack."""
        css = self._get_css()
        assert "Inter" in css
        assert "-apple-system" in css

    def test_dark_theme_contains_dark_accent(self) -> None:
        from src.ui.design.tokens import THEMES
        assert THEMES["dark"]["accent"] in self._get_css("dark")

    def test_light_theme_contains_light_bg_base(self) -> None:
        from src.ui.design.tokens import THEMES
        assert THEMES["light"]["bg_base"] in self._get_css("light")

    def test_style_tag_has_ht_theme_id(self) -> None:
        assert 'id="ht-theme"' in self._get_css()


class TestGetThemeJsHelpers:
    """get_theme_js_helpers returns script block with expected globals."""

    def _get_js(self) -> str:
        from src.ui.design.theme_engine import get_theme_js_helpers
        return get_theme_js_helpers()

    def test_returns_string(self) -> None:
        assert isinstance(self._get_js(), str)

    def test_contains_script_tag(self) -> None:
        assert "<script" in self._get_js()

    def test_defines_ht_apply_theme_vars(self) -> None:
        assert "htApplyThemeVars" in self._get_js()

    def test_defines_ht_theme_colors(self) -> None:
        assert "_htThemeColors" in self._get_js()

    def test_is_idempotent_guard(self) -> None:
        # Must have a guard against re-execution
        js = self._get_js()
        assert "_htThemeJsLoaded" in js


class TestBuildThemeStyleJson:
    """build_theme_style_json returns valid JSON Cytoscape style array."""

    def _build(self, theme: str = "dark") -> list[dict[str, object]]:
        from src.ui.components.canvas_styles import build_theme_style_json
        raw = build_theme_style_json(theme)
        return json.loads(raw)

    def test_returns_valid_json(self) -> None:
        from src.ui.components.canvas_styles import build_theme_style_json
        raw = build_theme_style_json("dark")
        assert isinstance(json.loads(raw), list)

    def test_contains_node_selector(self) -> None:
        styles = self._build("dark")
        selectors = [s["selector"] for s in styles]
        assert "node" in selectors

    def test_contains_edge_selector(self) -> None:
        styles = self._build("dark")
        selectors = [s["selector"] for s in styles]
        assert "edge" in selectors

    def test_node_selected_selector_present(self) -> None:
        styles = self._build("dark")
        selectors = [s["selector"] for s in styles]
        assert "node:selected" in selectors

    def test_dark_theme_uses_dark_accent(self) -> None:
        from src.ui.design.tokens import THEMES
        styles = self._build("dark")
        node_style = next(s["style"] for s in styles if s["selector"] == "node")
        assert node_style["background-color"] == THEMES["dark"]["accent"]

    def test_light_theme_uses_light_accent(self) -> None:
        from src.ui.design.tokens import THEMES
        styles = self._build("light")
        node_style = next(s["style"] for s in styles if s["selector"] == "node")
        assert node_style["background-color"] == THEMES["light"]["accent"]

    def test_canvas_style_js_backward_compat_alias(self) -> None:
        from src.ui.components.canvas_styles import CANVAS_STYLE_JS
        # Must still be a valid JSON string
        assert isinstance(json.loads(CANVAS_STYLE_JS), list)

    def test_unknown_theme_falls_back_to_dark(self) -> None:
        from src.ui.components.canvas_styles import build_theme_style_json
        from src.ui.design.tokens import THEMES
        raw = build_theme_style_json("bogus")
        styles = json.loads(raw)
        node_style = next(s["style"] for s in styles if s["selector"] == "node")
        assert node_style["background-color"] == THEMES["dark"]["accent"]

    def test_draft_nodes_are_not_dimmed(self) -> None:
        styles = self._build("dark")
        draft_style = next(s["style"] for s in styles if s["selector"] == "node.draft")
        assert draft_style["opacity"] == 1

    def test_draft_nodes_have_clear_text_label(self) -> None:
        styles = self._build("dark")
        draft_style = next(s["style"] for s in styles if s["selector"] == "node.draft")
        assert "Draft" in str(draft_style["label"])
        assert draft_style["font-size"] == "12px"


class TestAppShellThemeSwitcher:
    """app_shell source includes theme switching logic."""

    def _source(self) -> str:
        import src.ui.components.app_shell as mod
        return inspect.getsource(mod)

    def test_theme_items_in_user_menu(self) -> None:
        src = self._source()
        assert "dark" in src and "light" in src and "midnight" in src

    def test_handle_theme_change_defined(self) -> None:
        src = self._source()
        assert "_handle_theme_change" in src

    def test_apply_theme_to_client_called(self) -> None:
        src = self._source()
        assert "apply_theme_to_client" in src

    def test_theme_persisted_to_storage(self) -> None:
        src = self._source()
        assert "storage.user" in src and "theme" in src

    def test_get_initial_theme_css_called_in_shell(self) -> None:
        src = self._source()
        assert "get_initial_theme_css" in src

    def test_get_theme_js_helpers_called_in_shell(self) -> None:
        src = self._source()
        assert "get_theme_js_helpers" in src

    def test_css_vars_used_not_color_constants(self) -> None:
        src = self._source()
        # body style should use CSS vars, not hardcoded COLOR_SURFACE
        assert "var(--ht-bg-surface)" in src or "var(--ht-bg-base)" in src

    def test_header_uses_css_vars(self) -> None:
        src = self._source()
        assert "var(--ht-border)" in src


class TestLoginPageTheme:
    """Login page injects dark theme CSS vars."""

    def _source(self) -> str:
        import src.ui.pages.login as mod
        return inspect.getsource(mod)

    def test_get_initial_theme_css_called(self) -> None:
        assert "get_initial_theme_css" in self._source()

    def test_uses_css_var_for_body_bg(self) -> None:
        src = self._source()
        assert "var(--ht-" in src

    def test_dark_theme_passed_to_login(self) -> None:
        src = self._source()
        # login always uses dark theme
        assert 'get_initial_theme_css("dark")' in src or "get_initial_theme_css('dark')" in src


class TestUpdateCyThemeJsGlobal:
    """canvas.py registers window.updateCyTheme global for runtime theme switching."""

    def _source(self) -> str:
        import src.ui.components.canvas as mod
        import src.ui.components.canvas_js as mod_js
        import src.ui.components.canvas_js_utils as mod_js_utils
        return inspect.getsource(mod) + inspect.getsource(mod_js) + inspect.getsource(mod_js_utils)

    def test_update_cy_theme_defined(self) -> None:
        assert "updateCyTheme" in self._source()

    def test_canvas_bg_uses_css_var(self) -> None:
        src = self._source()
        assert "var(--ht-bg-base)" in src or "var(--ht-bg-surface)" in src

    def test_render_canvas_uses_build_theme_style_json(self) -> None:
        from src.ui.components.canvas import render_canvas
        src = inspect.getsource(render_canvas)
        assert "build_theme_style_json" in src
