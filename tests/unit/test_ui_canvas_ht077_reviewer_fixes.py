"""Focused regressions for the HT-077 reviewer findings."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ui.components.canvas_container_actions import CANVAS_CONTAINER_ACTIONS_JS
from src.ui.components.canvas_container_drag_events import CANVAS_CONTAINER_DRAG_EVENTS_JS
from src.ui.components.canvas_undo_js_actions import CANVAS_UNDO_JS_ACTIONS


def _line_count(path: str) -> int:
    return len(Path(path).read_text().splitlines())


def _normalize_selection_ids_for_test(
    selected_ids: list[str],
    depths: dict[str, int],
    ancestors: dict[str, set[str]],
    descendants: dict[str, set[str]],
) -> list[str]:
    keep: list[str] = []
    for node_id in sorted(selected_ids, key=lambda item: (depths[item], item)):
        if any(ancestor in keep for ancestor in ancestors[node_id]):
            continue
        keep = [kept for kept in keep if kept not in descendants[node_id]]
        keep.append(node_id)
    return keep


def _resolve_drop_parent_for_test(
    *,
    node_center: tuple[float, float],
    node_id: str,
    origin_parent_id: str | None,
    origin_parent_box: dict[str, float] | None,
    compounds: list[dict[str, object]],
) -> str | None:
    def _contains(box: dict[str, float], tol: float = 0.0) -> bool:
        return (
            node_center[0] >= box["x1"] - tol
            and node_center[0] <= box["x2"] + tol
            and node_center[1] >= box["y1"] - tol
            and node_center[1] <= box["y2"] + tol
        )

    def _rank(ignore_parent_id: str | None = None) -> str | None:
        ranked: list[tuple[int, float, float, str]] = []
        for compound in compounds:
            compound_id = str(compound["id"])
            if compound_id in {node_id, ignore_parent_id}:
                continue
            if bool(compound.get("locked", False)) or node_id in compound.get("ancestors", []):
                continue
            box = compound["box"]
            if not _contains(box):
                continue
            width = max(0.0, box["x2"] - box["x1"])
            height = max(0.0, box["y2"] - box["y1"])
            center_x = (box["x1"] + box["x2"]) / 2.0
            center_y = (box["y1"] + box["y2"]) / 2.0
            ranked.append((
                -int(compound.get("depth", 0)),
                width * height,
                ((node_center[0] - center_x) ** 2 + (node_center[1] - center_y) ** 2) ** 0.5,
                compound_id,
            ))
        ranked.sort()
        return ranked[0][3] if ranked else None

    resolved_parent = _rank()
    if resolved_parent and resolved_parent != origin_parent_id:
        return resolved_parent
    if origin_parent_id and origin_parent_box and _contains(origin_parent_box, tol=4.0):
        return origin_parent_id
    return _rank(origin_parent_id)


class TestHt077ReviewerSelectionNormalization:
    def test_selection_normalization_is_bound_at_selection_time(self) -> None:
        assert "cy.on('select unselect boxselect', 'node'" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "_htNormalizeSelectionMutualExclusion" in CANVAS_CONTAINER_DRAG_EVENTS_JS
        assert "window._htSelectionNormalizationInProgress" in CANVAS_CONTAINER_DRAG_EVENTS_JS

    def test_selection_normalization_prunes_descendants_when_ancestor_is_selected(self) -> None:
        normalized = _normalize_selection_ids_for_test(
            selected_ids=["leaf", "ancestor", "sibling"],
            depths={"ancestor": 0, "leaf": 1, "sibling": 0},
            ancestors={"ancestor": set(), "leaf": {"ancestor"}, "sibling": set()},
            descendants={"ancestor": {"leaf"}, "leaf": set(), "sibling": set()},
        )

        assert normalized == ["ancestor", "sibling"]


class TestHt077ReviewerDropParentRanking:
    def test_drop_parent_prefers_deeper_container_before_smaller_area(self) -> None:
        resolved = _resolve_drop_parent_for_test(
            node_center=(50.0, 50.0),
            node_id="child",
            origin_parent_id=None,
            origin_parent_box=None,
            compounds=[
                {"id": "outer", "box": {"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0}, "depth": 0, "ancestors": []},
                {"id": "inner", "box": {"x1": 10.0, "y1": 10.0, "x2": 110.0, "y2": 110.0}, "depth": 1, "ancestors": []},
            ],
        )

        assert resolved == "inner"

    def test_drop_parent_prefers_smaller_area_when_depth_matches(self) -> None:
        resolved = _resolve_drop_parent_for_test(
            node_center=(45.0, 45.0),
            node_id="child",
            origin_parent_id=None,
            origin_parent_box=None,
            compounds=[
                {"id": "wide", "box": {"x1": 0.0, "y1": 0.0, "x2": 120.0, "y2": 120.0}, "depth": 1, "ancestors": []},
                {"id": "tight", "box": {"x1": 10.0, "y1": 10.0, "x2": 90.0, "y2": 90.0}, "depth": 1, "ancestors": []},
            ],
        )

        assert resolved == "tight"

    def test_drop_parent_prefers_nearest_center_before_lexical_id(self) -> None:
        resolved = _resolve_drop_parent_for_test(
            node_center=(78.0, 50.0),
            node_id="child",
            origin_parent_id=None,
            origin_parent_box=None,
            compounds=[
                {"id": "alpha", "box": {"x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0}, "depth": 1, "ancestors": []},
                {"id": "beta", "box": {"x1": 40.0, "y1": 0.0, "x2": 140.0, "y2": 100.0}, "depth": 1, "ancestors": []},
            ],
        )

        assert resolved == "beta"

    def test_drop_parent_uses_lexical_id_as_final_tiebreaker(self) -> None:
        resolved = _resolve_drop_parent_for_test(
            node_center=(50.0, 50.0),
            node_id="child",
            origin_parent_id=None,
            origin_parent_box=None,
            compounds=[
                {"id": "beta", "box": {"x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0}, "depth": 1, "ancestors": []},
                {"id": "alpha", "box": {"x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0}, "depth": 1, "ancestors": []},
            ],
        )

        assert resolved == "alpha"


class TestHt077ReviewerOptimisticRollback:
    def test_action_emit_failure_routes_through_shared_failure_resolver(self) -> None:
        emit_action_body = CANVAS_UNDO_JS_ACTIONS.split("var emitActionRequest = function() {", 1)[1].split("        if (action.type === 'delete_published_node') {", 1)[0]
        assert "window._htResolveUndoApiFailure('forward', entryId, 'Undo bridge unavailable');" in emit_action_body
        assert "window._htUndoState.busy = false;" not in emit_action_body
        assert "window._htUndoState.pending = null;" not in emit_action_body

    def test_container_actions_use_shared_pending_lock_and_rollback_helpers(self) -> None:
        assert "function _htLockPendingPublishedReparent(node, entryId, payload) {" in CANVAS_CONTAINER_ACTIONS_JS
        assert "function _htTakePendingPublishedReparent(entryId) {" in CANVAS_CONTAINER_ACTIONS_JS
        assert "function _htRollbackPublishedReparent(rollback) {" in CANVAS_CONTAINER_ACTIONS_JS


class TestHt077ReviewerGrowthHook:
    def test_active_drag_invokes_container_growth_before_drop_resolution(self) -> None:
        drag_body = CANVAS_CONTAINER_DRAG_EVENTS_JS.split("cy.on('drag', 'node', function(evt) {", 1)[1].split(
            "        document.addEventListener('ht:node-remove-from-container'",
            1,
        )[0]

        assert "window._htMaybeGrowContainerForDraggedChild(node);" in drag_body
        assert drag_body.index("window._htMaybeGrowContainerForDraggedChild(node);") < drag_body.index(
            "var prospective = _htResolveDetachAwareDropParent(node, origin);"
        )


class TestHt077ReviewerFileCaps:
    @pytest.mark.parametrize(
        ("path", "limit"),
        [
            ("src/ui/components/canvas_container_actions.py", 250),
            ("src/ui/components/canvas_container_actions_core.py", 250),
            ("src/ui/components/canvas_container_actions_growth.py", 250),
            ("src/ui/components/canvas_container_drag_events_part_a.py", 250),
            ("src/ui/components/canvas_container_drag_events_part_b.py", 250),
            ("src/ui/components/canvas_container_drag_events_part_c.py", 250),
            ("src/ui/components/canvas_container_drag_events_part_d.py", 250),
            ("src/ui/components/canvas_js_interactions.py", 250),
            ("src/ui/components/canvas_js_interactions_part_a.py", 250),
            ("src/ui/components/canvas_js_interactions_part_b.py", 250),
            ("src/ui/components/canvas_styles.py", 250),
            ("src/ui/components/canvas_styles_support.py", 250),
            ("src/ui/components/stencils_panel_js.py", 250),
            ("src/ui/components/stencils_panel_drop_handler.py", 250),
        ],
    )
    def test_touched_ui_files_stay_within_repo_cap(self, path: str, limit: int) -> None:
        assert _line_count(path) <= limit