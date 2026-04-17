"""Unit tests for src.domain.auth — validate_password_strength (HT-025)."""
import pytest

from src.domain.auth import validate_password_strength


class TestValidatePasswordStrength:
    def test_exactly_8_chars_passes(self) -> None:
        validate_password_strength("12345678")  # must not raise

    def test_9_chars_passes(self) -> None:
        validate_password_strength("123456789")

    def test_long_password_passes(self) -> None:
        validate_password_strength("a" * 64)

    def test_7_chars_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            validate_password_strength("1234567")

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            validate_password_strength("")

    def test_1_char_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            validate_password_strength("x")

    def test_unicode_8_chars_passes(self) -> None:
        # 8 unicode characters — length check is on len(), which counts code points
        validate_password_strength("päßwörd1")

    def test_unicode_short_raises(self) -> None:
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            validate_password_strength("pässw")
