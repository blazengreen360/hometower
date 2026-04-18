"""Unit tests for inventory CSV export helpers (HT-087)."""

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

from src.models.types import DeviceStatus, DeviceType
from src.ui.pages.inventory_csv_export import (
    CSV_FILENAME,
    build_inventory_csv,
    build_inventory_csv_download_js,
)


def _fake_device(*, name: str, notes: str = "") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        type=DeviceType.Server,
        status=DeviceStatus.Active,
        ip="10.0.0.10",
        mac="aa:bb:cc:dd:ee:ff",
        location_name="Rack 1",
        notes=notes,
        tags=[],
        services=[],
        networks=[],
        updated_at=now,
    )


def test_build_inventory_csv_includes_required_primary_columns() -> None:
    csv_text = build_inventory_csv([_fake_device(name="Server Alpha", notes="Primary")])

    assert "Name,Status,Type,IP,MAC,Location,Notes" in csv_text
    assert "Server Alpha,Active,Server,10.0.0.10,aa:bb:cc:dd:ee:ff,Rack 1,Primary" in csv_text


def test_build_inventory_csv_prefixes_formula_like_cells_for_safety() -> None:
    csv_text = build_inventory_csv([_fake_device(name="=cmd", notes="@macro")])

    assert "'=cmd" in csv_text
    assert "'@macro" in csv_text


def test_build_inventory_csv_download_js_creates_blob_download() -> None:
    js = build_inventory_csv_download_js("Name,Status\nA,Active\n")

    assert CSV_FILENAME in js
    assert "new Blob" in js
    assert "anchor.download" in js
    assert "URL.createObjectURL" in js
