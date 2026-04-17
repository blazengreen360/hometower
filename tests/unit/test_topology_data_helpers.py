"""Unit tests for src/ui/services/topology_data_helpers.py."""
from src.ui.services.topology_data_helpers import (
    _extract_draft_elements,
    _extract_published_ids,
    merge_saved_layout,
    prune_orphaned_draft_layout,
)


class TestMergeSavedLayoutClasses:
    """Verify that merge_saved_layout restores CSS classes from saved layout."""

    def test_classes_merged_from_saved_layout(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "d1", "label": "Server"}, "group": "nodes"},
            {"data": {"id": "d2", "label": "Switch"}, "group": "nodes"},
        ]
        saved_layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "d1"}, "position": {"x": 10, "y": 20}, "classes": "container"},
                    {"data": {"id": "d2"}, "position": {"x": 30, "y": 40}},
                ],
            },
        }
        device_ids = {"d1", "d2"}

        merge_saved_layout(elements, saved_layout, device_ids)

        assert elements[0]["classes"] == "container"
        assert "classes" not in elements[1]

    def test_elements_without_saved_classes_unaffected(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "d1", "label": "Server"}, "group": "nodes"},
        ]
        saved_layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "d1"}, "position": {"x": 10, "y": 20}},
                ],
            },
        }
        device_ids = {"d1"}

        merge_saved_layout(elements, saved_layout, device_ids)

        assert elements[0].get("position") == {"x": 10, "y": 20}
        assert "classes" not in elements[0]

    def test_multiple_classes_preserved(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "d1", "label": "Server"}, "group": "nodes"},
        ]
        saved_layout: dict[str, object] = {
            "elements": [
                {"data": {"id": "d1"}, "position": {"x": 5, "y": 5}, "classes": "container collapsed"},
            ],
        }
        device_ids = {"d1"}

        merge_saved_layout(elements, saved_layout, device_ids)

        assert elements[0]["classes"] == "container collapsed"

    def test_positions_still_merged(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "d1", "label": "Server"}, "group": "nodes"},
        ]
        saved_layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "d1"}, "position": {"x": 100, "y": 200}, "classes": "container"},
                ],
            },
        }
        device_ids = {"d1"}

        merge_saved_layout(elements, saved_layout, device_ids)

        assert elements[0]["position"] == {"x": 100, "y": 200}
        assert elements[0]["classes"] == "container"

    def test_saved_position_marks_node_as_positioned_even_at_origin(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "d1", "label": "Server"}, "group": "nodes"},
        ]
        saved_layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "d1"}, "position": {"x": 0, "y": 0}},
                ],
            },
        }

        merge_saved_layout(elements, saved_layout, {"d1"})

        assert elements[0]["position"] == {"x": 0, "y": 0}
        assert elements[0]["data"]["_positioned"] is True

    def test_list_elements_keep_published_edges_after_prune_and_stale_node_filter(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "dev-1"}, "group": "nodes"},
        ]
        saved_layout: dict[str, object] = {
            "elements": [
                {"data": {"id": "dev-1"}, "position": {"x": 10, "y": 20}},
                {"data": {"id": "stale-1"}, "position": {"x": 99, "y": 88}},
                {
                    "group": "edges",
                    "data": {"id": "edge-live", "source": "dev-1", "target": "dev-1"},
                },
                {"data": {"id": "draft-1", "draft": True}, "position": {"x": 1, "y": 1}},
                {
                    "group": "edges",
                    "data": {
                        "id": "draft-edge-1",
                        "source": "draft-1",
                        "target": "dev-1",
                        "draft_edge": True,
                    },
                },
            ],
        }

        pruned = prune_orphaned_draft_layout(saved_layout)
        merge_saved_layout(elements, saved_layout, {"dev-1"})

        assert pruned == 1
        assert elements[0]["position"] == {"x": 10, "y": 20}
        saved_elements = saved_layout["elements"]
        assert isinstance(saved_elements, list)
        ids = [
            elem["data"]["id"]  # type: ignore[index]
            for elem in saved_elements
            if isinstance(elem, dict) and isinstance(elem.get("data"), dict)
        ]
        assert ids == ["dev-1", "edge-live"]


class TestPruneOrphanedDraftLayout:
    def test_prunes_draft_nodes_and_edges_from_dict_elements(self) -> None:
        layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "pub-1"}},
                    {"data": {"id": "draft-1", "draft": True}},
                ],
                "edges": [
                    {"data": {"id": "draft-edge-1", "draft_edge": True}},
                    {"data": {"id": "real-edge-1", "source": "pub-1", "target": "pub-1"}},
                ],
            },
        }

        pruned = prune_orphaned_draft_layout(layout)

        assert pruned == 1
        assert layout["elements"]["nodes"] == [{"data": {"id": "pub-1"}}]  # type: ignore[index]
        assert layout["elements"]["edges"] == [  # type: ignore[index]
            {"data": {"id": "real-edge-1", "source": "pub-1", "target": "pub-1"}},
        ]

    def test_prunes_draft_entries_from_flat_element_lists(self) -> None:
        layout: dict[str, object] = {
            "elements": [
                {"data": {"id": "pub-1"}},
                {"data": {"id": "draft-2", "draft": True}},
                {"group": "edges", "data": {"id": "draft-edge-2", "draft_edge": True}},
                {"group": "edges", "data": {"id": "real-edge-2", "source": "pub-1", "target": "pub-1"}},
            ],
        }

        pruned = prune_orphaned_draft_layout(layout)

        assert pruned == 1
        assert layout["elements"] == [  # type: ignore[index]
            {"data": {"id": "pub-1"}},
            {"group": "edges", "data": {"id": "real-edge-2", "source": "pub-1", "target": "pub-1"}},
        ]


class TestExtractPublishedIds:
    """Verify _extract_published_ids excludes draft elements."""

    def test_excludes_draft_ids(self) -> None:
        layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "aaa-111"}},
                    {"data": {"id": "draft-999", "draft": True}},
                    {"data": {"id": "bbb-222"}},
                ],
            },
        }
        result = _extract_published_ids(layout)
        assert result == {"aaa-111", "bbb-222"}

    def test_excludes_draft_flag_without_prefix(self) -> None:
        layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "some-id", "draft": True}},
                    {"data": {"id": "pub-id"}},
                ],
            },
        }
        result = _extract_published_ids(layout)
        assert result == {"pub-id"}

    def test_empty_layout_returns_empty(self) -> None:
        assert _extract_published_ids(None) == set()
        assert _extract_published_ids({}) == set()

    def test_only_drafts_returns_empty_set(self) -> None:
        """Layout with zero published IDs (only drafts) returns empty set."""
        layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "draft-aaa", "draft": True}},
                    {"data": {"id": "draft-bbb", "draft": True}},
                ],
            },
        }
        result = _extract_published_ids(layout)
        assert result == set()

    def test_list_format_elements(self) -> None:
        layout: dict[str, object] = {
            "elements": [
                {"data": {"id": "pub-1"}},
                {"data": {"id": "draft-abc", "draft": True}},
                {"group": "edges", "data": {"id": "e1"}},
            ],
        }
        result = _extract_published_ids(layout)
        assert result == {"pub-1"}


class TestExtractDraftElements:
    """Verify _extract_draft_elements returns only draft elements."""

    def test_returns_drafts_only(self) -> None:
        layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "aaa-111"}},
                    {"data": {"id": "draft-999", "draft": True}, "position": {"x": 10, "y": 20}},
                ],
            },
        }
        result = _extract_draft_elements(layout)
        assert len(result) == 1
        assert result[0]["data"]["id"] == "draft-999"  # type: ignore[index]

    def test_preserves_position(self) -> None:
        layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "draft-abc", "draft": True}, "position": {"x": 50, "y": 60}},
                ],
            },
        }
        result = _extract_draft_elements(layout)
        assert result[0].get("position") == {"x": 50, "y": 60}

    def test_empty_layout_returns_empty(self) -> None:
        assert _extract_draft_elements(None) == []
        assert _extract_draft_elements({}) == []

    def test_includes_draft_edges(self) -> None:
        layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {"data": {"id": "pub-1"}},
                ],
                "edges": [
                    {"data": {"id": "draft-edge-1", "draft_edge": True}},
                    {"data": {"id": "real-edge-1"}},
                ],
            },
        }
        result = _extract_draft_elements(layout)
        assert len(result) == 1
        assert result[0]["data"]["id"] == "draft-edge-1"  # type: ignore[index]

    def test_list_format_elements(self) -> None:
        layout: dict[str, object] = {
            "elements": [
                {"data": {"id": "pub-1"}},
                {"data": {"id": "draft-xyz", "draft": True}, "classes": "draft"},
            ],
        }
        result = _extract_draft_elements(layout)
        assert len(result) == 1
        assert result[0]["data"]["id"] == "draft-xyz"  # type: ignore[index]

    def test_includes_draft_edge_by_flag_only(self) -> None:
        """Edge with draft_edge flag but without draft- prefix is captured."""
        layout: dict[str, object] = {
            "elements": {
                "nodes": [{"data": {"id": "pub-1"}}],
                "edges": [
                    {"data": {"id": "edge-abc", "draft_edge": True}},
                    {"data": {"id": "edge-def"}},
                ],
            },
        }
        result = _extract_draft_elements(layout)
        assert len(result) == 1
        assert result[0]["data"]["id"] == "edge-abc"  # type: ignore[index]
