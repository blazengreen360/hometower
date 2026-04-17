"""Unit tests for the health check module.

Tests version string correctness and uptime tracking logic
without going through the full HTTP stack.
"""
import time
from unittest.mock import MagicMock, patch

import pytest


class TestVersionString:
    def test_version_file_exports_version(self) -> None:
        """__version__.py exports a non-empty __version__ string."""
        from src.__version__ import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_is_semantic(self) -> None:
        """Version follows major.minor.patch semver format."""
        import re

        from src.__version__ import __version__

        assert re.match(r"^\d+\.\d+\.\d+$", __version__), (
            f"Expected semver format, got: {__version__}"
        )


class TestUptimeTracking:
    def test_start_time_is_set_at_module_import(self) -> None:
        """Health router module records a start time on first import."""
        from src.api.routers.health import _start_time

        assert isinstance(_start_time, float)
        assert _start_time > 0

    def test_uptime_increases_over_time(self) -> None:
        """Uptime seconds grows as time progresses."""
        import time

        from src.api.routers.health import _start_time

        before = time.time() - _start_time
        time.sleep(0.01)
        after = time.time() - _start_time

        assert after > before
