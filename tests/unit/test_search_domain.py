"""Unit tests for search domain functions (HT-020)."""
import pytest

from src.domain.search import ParsedQuery, parse_query, to_sql_like


class TestToSqlLike:
    def test_star_becomes_percent(self) -> None:
        assert to_sql_like("192.168.*") == "192.168.%"

    def test_percent_escaped(self) -> None:
        assert to_sql_like("100%") == r"100\%"

    def test_underscore_escaped(self) -> None:
        assert to_sql_like("my_host") == r"my\_host"

    def test_percent_and_underscore_escaped(self) -> None:
        assert to_sql_like("100%_test") == r"100\%\_test"

    def test_no_special_chars_unchanged(self) -> None:
        assert to_sql_like("ubuntu") == "ubuntu"

    def test_star_with_escape(self) -> None:
        result = to_sql_like("192.168._*")
        assert result == r"192.168.\_%" 

    def test_only_star(self) -> None:
        assert to_sql_like("*") == "%"

    def test_multiple_stars(self) -> None:
        assert to_sql_like("*.*.*.0") == "%.%.%.0"


class TestParseQuery:
    def test_empty_string(self) -> None:
        pq = parse_query("")
        assert pq.is_empty()
        assert pq.free_text == ""

    def test_single_type_operator(self) -> None:
        pq = parse_query("type:server")
        assert pq.types == ["server"]
        assert pq.is_empty() is False

    def test_type_case_insensitive_operator(self) -> None:
        pq = parse_query("TYPE:Server")
        assert pq.types == ["Server"]

    def test_tag_operator(self) -> None:
        pq = parse_query("tag:production")
        assert pq.tags == ["production"]

    def test_ip_operator(self) -> None:
        pq = parse_query("ip:192.168.*")
        assert pq.ip_patterns == ["192.168.*"]

    def test_os_operator(self) -> None:
        pq = parse_query("os:Ubuntu")
        assert pq.os_patterns == ["Ubuntu"]

    def test_location_operator(self) -> None:
        pq = parse_query("location:rack1")
        assert pq.location_patterns == ["rack1"]

    def test_service_operator(self) -> None:
        pq = parse_query("service:plex")
        assert pq.service_patterns == ["plex"]

    def test_free_text_only(self) -> None:
        pq = parse_query("my server")
        assert pq.free_text == "my server"
        assert pq.is_empty() is False

    def test_unknown_operator_falls_to_free_text(self) -> None:
        pq = parse_query("parent:rack1")
        assert "parent:rack1" in pq.free_text
        assert pq.location_patterns == []

    def test_network_operator_falls_to_free_text(self) -> None:
        pq = parse_query("network:10.0.0.0/8")
        assert "network:10.0.0.0/8" in pq.free_text

    def test_multiple_type_values_or(self) -> None:
        pq = parse_query("type:server type:vm")
        assert pq.types == ["server", "vm"]

    def test_combined_operators_and(self) -> None:
        pq = parse_query("type:server tag:production")
        assert pq.types == ["server"]
        assert pq.tags == ["production"]

    def test_mixed_operators_and_free_text(self) -> None:
        pq = parse_query("type:server myhost")
        assert pq.types == ["server"]
        assert pq.free_text == "myhost"

    def test_quoted_value(self) -> None:
        pq = parse_query('tag:"my tag"')
        assert pq.tags == ["my tag"]

    def test_empty_operator_value_ignored(self) -> None:
        pq = parse_query("type:")
        assert pq.types == []
        assert pq.is_empty()

    def test_whitespace_only(self) -> None:
        pq = parse_query("   ")
        assert pq.is_empty()

    def test_is_empty_false_with_free_text(self) -> None:
        pq = parse_query("hello")
        assert not pq.is_empty()


class TestParsedQueryIsEmpty:
    def test_default_is_empty(self) -> None:
        pq = ParsedQuery()
        assert pq.is_empty()

    def test_with_types_not_empty(self) -> None:
        pq = ParsedQuery(types=["server"])
        assert not pq.is_empty()

    def test_with_free_text_not_empty(self) -> None:
        pq = ParsedQuery(free_text="hello")
        assert not pq.is_empty()

    def test_all_empty_lists_is_empty(self) -> None:
        pq = ParsedQuery(types=[], tags=[], ip_patterns=[], free_text="")
        assert pq.is_empty()
