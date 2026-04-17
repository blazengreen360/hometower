"""Unit tests for dashboard page API URL wiring."""
import inspect
import re

from src.ui.pages.dashboard import dashboard_page


def test_dashboard_collection_api_urls_use_trailing_slashes() -> None:
    """Dashboard data fetches must target slash-terminated collection endpoints."""
    source = inspect.getsource(dashboard_page)
    urls = re.findall(r'client\.get\(\s*f"\{base\}(/api/[^"]+)"', source)

    assert "/api/devices/" in urls
    assert "/api/connections/" in urls
    assert "/api/locations/" in urls
    assert "/api/tags/" in urls
    assert "/api/power/summary" in urls
    assert "/api/devices" not in urls
    assert "/api/connections" not in urls
    assert "/api/locations" not in urls
    assert "/api/tags" not in urls
