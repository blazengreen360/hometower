"""Unit tests for canvas_zoom component (HT-040)."""
from src.ui.components.canvas_zoom import _ZOOM_CONTROLS_JS, inject_zoom_controls


class TestZoomControlsJS:
    def test_zoom_in_uses_1_2_multiplier(self) -> None:
        assert "* 1.2" in _ZOOM_CONTROLS_JS

    def test_zoom_out_uses_1_2_divisor(self) -> None:
        assert "/ 1.2" in _ZOOM_CONTROLS_JS

    def test_fit_uses_40_padding(self) -> None:
        assert "fit(undefined, 40)" in _ZOOM_CONTROLS_JS

    def test_uses_window_underscore_cy(self) -> None:
        assert "window._cy" in _ZOOM_CONTROLS_JS

    def test_zoom_in_button_id(self) -> None:
        assert "ht-zoom-in" in _ZOOM_CONTROLS_JS

    def test_zoom_out_button_id(self) -> None:
        assert "ht-zoom-out" in _ZOOM_CONTROLS_JS

    def test_zoom_fit_button_id(self) -> None:
        assert "ht-zoom-fit" in _ZOOM_CONTROLS_JS

    def test_help_button_id(self) -> None:
        assert "ht-help-open" in _ZOOM_CONTROLS_JS

    def test_help_modal_overlay_id(self) -> None:
        assert "ht-help-overlay" in _ZOOM_CONTROLS_JS

    def test_help_modal_supports_drag_device_cards(self) -> None:
        assert "setData('deviceType'" in _ZOOM_CONTROLS_JS
        assert "Device Tools (drag to canvas)" in _ZOOM_CONTROLS_JS
        assert "closeHelpModal();" in _ZOOM_CONTROLS_JS

    def test_help_modal_hides_deprecated_creation_types(self) -> None:
        assert "VLAN" not in _ZOOM_CONTROLS_JS
        assert "Subnet" not in _ZOOM_CONTROLS_JS

    def test_inject_zoom_controls_is_callable(self) -> None:
        """Smoke test — verify the function is importable."""
        assert callable(inject_zoom_controls)

    def test_controls_positioned_bottom_right(self) -> None:
        assert "bottom:16px" in _ZOOM_CONTROLS_JS
        assert "right:16px" in _ZOOM_CONTROLS_JS

    def test_buttons_meet_minimum_touch_target(self) -> None:
        assert "width:44px" in _ZOOM_CONTROLS_JS
        assert "height:44px" in _ZOOM_CONTROLS_JS
