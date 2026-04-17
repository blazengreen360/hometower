"""Unit tests for shared UI timestamp formatting helpers."""

from src.ui.utils.formatting import enrich_last_modified_rows
from src.ui.utils.formatting import format_last_modified_timestamp


def test_format_last_modified_timestamp_keeps_iso_for_browser_local_rendering() -> None:
    assert format_last_modified_timestamp("2026-04-12T13:39:49Z") == "2026-04-12T13:39:49Z"


def test_format_last_modified_timestamp_handles_missing_values() -> None:
    assert format_last_modified_timestamp(None) == "\u2014"
    assert format_last_modified_timestamp("") == "\u2014"


def test_format_last_modified_timestamp_falls_back_to_original_on_invalid_input() -> None:
    assert format_last_modified_timestamp("not-an-iso") == "not-an-iso"


def test_enrich_last_modified_rows_adds_sort_and_iso_keys_for_populated_and_missing_values() -> None:
    rows = enrich_last_modified_rows(
        [
            {"id": "1", "last_modified": "2026-04-12T13:39:49Z"},
            {"id": "2", "last_modified": None},
            {"id": "3"},
        ]
    )

    assert rows[0]["last_modified_sort"] == "2026-04-12T13:39:49Z"
    assert rows[0]["last_modified_iso"] == "2026-04-12T13:39:49Z"
    assert rows[0]["last_modified"] == "2026-04-12T13:39:49Z"

    assert rows[1]["last_modified_sort"] == ""
    assert rows[1]["last_modified_iso"] == ""
    assert rows[1]["last_modified"] == "\u2014"

    assert rows[2]["last_modified_sort"] == ""
    assert rows[2]["last_modified_iso"] == ""
    assert rows[2]["last_modified"] == "\u2014"
