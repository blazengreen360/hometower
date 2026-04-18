"""Unit tests for device detail rich field helpers (HT-087)."""

from src.ui.components.device_panel_rich_fields import (
    build_quick_connect_links,
    sanitize_markdown_notes,
)


def test_sanitize_markdown_notes_escapes_raw_html() -> None:
    raw = "# Title\n<script>alert('xss')</script>"
    rendered = sanitize_markdown_notes(raw)

    assert "# Title" in rendered
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in rendered


def test_sanitize_markdown_notes_blocks_unsafe_markdown_protocols() -> None:
    raw = "[click](javascript:alert(1))"
    rendered = sanitize_markdown_notes(raw)

    assert "javascript:" not in rendered.lower()
    assert "](#" in rendered


def test_sanitize_markdown_notes_preserves_blockquote_markers() -> None:
    raw = "> Do **not** power cycle without a snapshot."
    rendered = sanitize_markdown_notes(raw)

    assert rendered.startswith("> ")
    assert "&gt; Do" not in rendered


def test_sanitize_markdown_notes_preserves_blockquote_and_escapes_html() -> None:
    raw = "> <script>alert(1)</script>"
    rendered = sanitize_markdown_notes(raw)

    assert rendered.startswith("> ")
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered


def test_build_quick_connect_links_for_ipv4() -> None:
    links = build_quick_connect_links("192.168.1.50")

    assert links == {
        "ssh": "ssh://192.168.1.50",
        "http": "http://192.168.1.50",
        "https": "https://192.168.1.50",
    }


def test_build_quick_connect_links_wraps_ipv6_host() -> None:
    links = build_quick_connect_links("2001:db8::1")

    assert links["ssh"] == "ssh://[2001:db8::1]"
    assert links["http"] == "http://[2001:db8::1]"
    assert links["https"] == "https://[2001:db8::1]"


def test_build_quick_connect_links_returns_empty_for_blank_ip() -> None:
    assert build_quick_connect_links("") == {}
    assert build_quick_connect_links(None) == {}
