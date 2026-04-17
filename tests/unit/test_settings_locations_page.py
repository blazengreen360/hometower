"""Unit tests for settings locations page helpers."""

from src.ui.pages.settings_locations import _format_coord_for_form


def test_format_coord_for_form_preserves_zero_float() -> None:
    assert _format_coord_for_form(0.0) == "0.0"


def test_format_coord_for_form_preserves_zero_int() -> None:
    assert _format_coord_for_form(0) == "0"


def test_format_coord_for_form_returns_empty_for_none() -> None:
    assert _format_coord_for_form(None) == ""
