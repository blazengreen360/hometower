"""Unit tests for topology canvas data loading resilience."""
import asyncio

from src.ui.services import topology_data


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


class _FailingClient:
    async def __aenter__(self) -> "_FailingClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(500)


class _PaginatedClient:
    async def __aenter__(self) -> "_PaginatedClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        params = kwargs.get("params")
        if url.endswith("/api/devices/"):
            page = int(params["page"]) if isinstance(params, dict) else 1
            if page == 1:
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {"id": f"dev-{i}", "name": f"Device {i}", "type": "Server"}
                            for i in range(100)
                        ]
                    },
                )
            if page == 2:
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": f"dev-{100 + i}",
                                "name": f"Device {100 + i}",
                                "type": "Server",
                            }
                            for i in range(50)
                        ]
                    },
                )
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": []})

        return _FakeResponse(404)


class _EscapingClient:
    async def __aenter__(self) -> "_EscapingClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": "dev-1",
                            "name": "<script>alert(1)</script>",
                            "type": "Server",
                            "status": "<b>Active</b>",
                            "ip": "10.0.0.<x>",
                            "mac": "aa:bb:<cc>",
                            "os": "<img src=x>",
                            "notes": "<svg onload=1>",
                        }
                    ]
                },
            )

        if url.endswith("/api/connections/"):
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": "edge-1",
                            "source_id": "dev-1",
                            "target_id": "dev-1",
                            "type": "Ethernet",
                            "label": "<img src=x onerror=alert(1)>",
                        }
                    ]
                },
            )

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": []})

        return _FakeResponse(404)


class _VersionedClient:
    async def __aenter__(self) -> "_VersionedClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": "dev-1",
                            "name": "Versioned Device",
                            "type": "Server",
                            "version": 7,
                        }
                    ]
                },
            )

        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": []})

        return _FakeResponse(404)


class _NetworkAwareClient:
    async def __aenter__(self) -> "_NetworkAwareClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        params = kwargs.get("params")

        if url.endswith("/api/devices/"):
            if isinstance(params, dict):
                assert params.get("include") == "networks"
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": "dev-1",
                            "name": "Router",
                            "type": "Router",
                            "networks": [
                                {
                                    "network_id": "net-1",
                                    "name": "Management",
                                    "color": "#3b82f6",
                                    "ip_address": "10.0.10.1",
                                },
                                {
                                    "network_id": "net-2",
                                    "name": "Storage",
                                    "color": "#22c55e",
                                    "ip_address": "10.0.20.1",
                                },
                            ],
                        }
                    ]
                },
            )

        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": []})

        return _FakeResponse(404)


class _MalformedNetworkPayloadClient:
    async def __aenter__(self) -> "_MalformedNetworkPayloadClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": "dev-1",
                            "name": "Router",
                            "type": "Router",
                            "networks": [
                                "bad",
                                {"network_id": "", "name": 123},
                            ],
                        }
                    ]
                },
            )

        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": []})

        return _FakeResponse(404)


class _StaleLayoutClient:
    async def __aenter__(self) -> "_StaleLayoutClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": "dev-1",
                            "name": "Device 1",
                            "type": "Server",
                        }
                    ]
                },
            )

        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": [{"id": "layout-1"}]})

        if url.endswith("/api/diagrams/layout-1"):
            return _FakeResponse(
                200,
                {
                    "cytoscape_json": {
                        "elements": {
                            "nodes": [
                                {
                                    "data": {"id": "dev-1"},
                                    "position": {"x": 10, "y": 20},
                                },
                                {
                                    "data": {"id": "missing-device"},
                                    "position": {"x": 30, "y": 40},
                                },
                            ]
                        },
                        "zoom": 1,
                        "pan": {"x": 0, "y": 0},
                    }
                },
            )

        return _FakeResponse(404)


class _DraftsOnlyLayoutClient:
    """Layout exists but contains only draft nodes — zero published IDs."""

    async def __aenter__(self) -> "_DraftsOnlyLayoutClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {
                    "items": [
                        {"id": "dev-1", "name": "Device 1", "type": "Server"},
                        {"id": "dev-2", "name": "Device 2", "type": "Switch"},
                    ]
                },
            )

        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": [{"id": "layout-d"}]})

        if url.endswith("/api/diagrams/layout-d"):
            return _FakeResponse(
                200,
                {
                    "cytoscape_json": {
                        "elements": {
                            "nodes": [
                                {
                                    "data": {"id": "draft-abc", "draft": True},
                                    "position": {"x": 10, "y": 20},
                                    "classes": "draft",
                                },
                            ],
                            "edges": [
                                {
                                    "data": {
                                        "id": "draft-edge-1",
                                        "source": "draft-abc",
                                        "target": "draft-abc",
                                        "draft_edge": True,
                                    },
                                },
                            ],
                        },
                    }
                },
            )

        return _FakeResponse(404)


class _ListFormatLayoutClient:
    """Saved layouts may use legacy flat element lists with group-less nodes."""

    async def __aenter__(self) -> "_ListFormatLayoutClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {
                    "items": [
                        {"id": "dev-1", "name": "Device 1", "type": "Server"},
                    ]
                },
            )

        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})

        if url.endswith("/api/diagrams/"):
            return _FakeResponse(200, {"items": [{"id": "layout-list"}]})

        if url.endswith("/api/diagrams/layout-list"):
            return _FakeResponse(
                200,
                {
                    "cytoscape_json": {
                        "elements": [
                            {"data": {"id": "dev-1"}, "position": {"x": 11, "y": 22}},
                            {"data": {"id": "stale-1"}, "position": {"x": 33, "y": 44}},
                            {
                                "group": "edges",
                                "data": {"id": "edge-live", "source": "dev-1", "target": "dev-1"},
                            },
                            {"data": {"id": "draft-1", "draft": True}},
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
                },
            )

        return _FakeResponse(404)


class TestLoadCanvasData:
    def test_non_200_returns_empty_data_without_raising(self, monkeypatch) -> None:
        warnings: list[str] = []

        def fake_warning(message: str, **_: object) -> None:
            warnings.append(message)

        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _FailingClient(),
        )
        monkeypatch.setattr(topology_data.logger, "warning", fake_warning)

        elements, saved_layout = asyncio.run(topology_data.load_canvas_data("token"))

        assert elements == []
        assert saved_layout is None
        assert len(warnings) >= 1

    def test_paginates_devices_and_returns_all_items(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _PaginatedClient(),
        )

        elements, saved_layout = asyncio.run(topology_data.load_canvas_data("token"))

        device_elements = [elem for elem in elements if elem.get("group") != "edges"]
        assert len(device_elements) == 150
        assert saved_layout is None

    def test_escapes_user_supplied_node_and_edge_fields(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _EscapingClient(),
        )

        elements, _ = asyncio.run(topology_data.load_canvas_data("token"))

        node = next(elem for elem in elements if elem.get("group") != "edges")
        node_data = node["data"]
        assert node_data["label"] == "&lt;script&gt;alert(1)&lt;/script&gt;"
        assert node_data["raw_name"] == "<script>alert(1)</script>"
        assert node_data["status"] == "&lt;b&gt;Active&lt;/b&gt;"
        assert node_data["ip"] == "10.0.0.&lt;x&gt;"
        assert node_data["mac"] == "aa:bb:&lt;cc&gt;"
        assert node_data["os"] == "&lt;img src=x&gt;"
        assert node_data["notes"] == "&lt;svg onload=1&gt;"

        edge = next(elem for elem in elements if elem.get("group") == "edges")
        edge_data = edge["data"]
        assert edge_data["label"] == "&lt;img src=x onerror=alert(1)&gt;"
        assert edge_data["raw_label"] == "<img src=x onerror=alert(1)>"

    def test_load_canvas_data_includes_published_node_version(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _VersionedClient(),
        )

        elements, _ = asyncio.run(topology_data.load_canvas_data("token"))

        node = next(elem for elem in elements if elem.get("group") != "edges")
        node_data = node["data"]
        assert node_data["version"] == 7

    def test_load_canvas_data_requests_include_networks_and_maps_memberships(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _NetworkAwareClient(),
        )

        elements, _ = asyncio.run(topology_data.load_canvas_data("token"))

        node = next(elem for elem in elements if elem.get("group") != "edges")
        memberships = node["data"].get("network_memberships")
        assert isinstance(memberships, list)
        assert len(memberships) == 2
        first = memberships[0]
        assert first["network_id"] == "net-1"
        assert first["name"] == "Management"
        assert first["color"] == "#3b82f6"
        assert first["ip_address"] == "10.0.10.1"

    def test_load_canvas_data_ignores_malformed_network_payload_items(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _MalformedNetworkPayloadClient(),
        )

        elements, _ = asyncio.run(topology_data.load_canvas_data("token"))

        node = next(elem for elem in elements if elem.get("group") != "edges")
        memberships = node["data"].get("network_memberships")
        assert memberships == []

    def test_filters_stale_saved_layout_nodes(self, monkeypatch) -> None:
        debug_counts: list[int] = []

        def fake_debug(_message: str, **kwargs: object) -> None:
            count = kwargs.get("count")
            if isinstance(count, int):
                debug_counts.append(count)

        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _StaleLayoutClient(),
        )
        monkeypatch.setattr(topology_data.logger, "debug", fake_debug)

        _elements, saved_layout = asyncio.run(topology_data.load_canvas_data("token"))

        assert saved_layout is not None
        saved_elements = saved_layout["elements"]
        assert isinstance(saved_elements, dict)
        nodes = saved_elements["nodes"]
        assert isinstance(nodes, list)
        assert len(nodes) == 1
        assert nodes[0]["data"]["id"] == "dev-1"
        assert debug_counts == [1]

    def test_layout_with_only_drafts_loads_zero_published_devices(self, monkeypatch) -> None:
        """Draft ghosts are pruned from both returned elements and saved layout metadata."""
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _DraftsOnlyLayoutClient(),
        )

        elements, saved_layout = asyncio.run(topology_data.load_canvas_data("token"))

        assert saved_layout is not None
        assert elements == []
        assert saved_layout.get("_draft_pruned_count") == 1
        saved_elements = saved_layout["elements"]
        assert isinstance(saved_elements, dict)
        assert saved_elements["nodes"] == []
        assert saved_elements["edges"] == []

    def test_list_format_layout_keeps_published_edges_after_cleanup_and_merge(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _ListFormatLayoutClient(),
        )

        elements, saved_layout = asyncio.run(topology_data.load_canvas_data("token"))

        assert saved_layout is not None
        saved_elements = saved_layout["elements"]
        assert isinstance(saved_elements, list)
        saved_ids = [
            entry["data"]["id"]  # type: ignore[index]
            for entry in saved_elements
            if isinstance(entry, dict) and isinstance(entry.get("data"), dict)
        ]
        assert saved_ids == ["dev-1", "edge-live"]

        node = next(elem for elem in elements if elem.get("group") != "edges")
        assert node["position"] == {"x": 11, "y": 22}


class TestTopologicalSortElements:
    """Finding 1 / Finding 4: topological ordering for compound nodes."""

    def test_empty_returns_empty(self) -> None:
        from src.ui.services.topology_data import _topological_sort_elements

        assert _topological_sort_elements([]) == []

    def test_single_root_preserved(self) -> None:
        from src.ui.services.topology_data import _topological_sort_elements

        node: dict[str, object] = {"data": {"id": "n1"}}
        result = _topological_sort_elements([node])
        assert result == [node]

    def test_root_before_child(self) -> None:
        from src.ui.services.topology_data import _topological_sort_elements

        parent: dict[str, object] = {"data": {"id": "p"}}
        child: dict[str, object] = {"data": {"id": "c", "parent": "p"}}
        result = _topological_sort_elements([child, parent])
        ids = [e["data"]["id"] for e in result]  # type: ignore[index]
        assert ids.index("p") < ids.index("c")

    def test_three_level_nesting_a_b_c(self) -> None:
        """A→B→C: must produce A before B before C regardless of input order."""
        from src.ui.services.topology_data import _topological_sort_elements

        a: dict[str, object] = {"data": {"id": "a"}}
        b: dict[str, object] = {"data": {"id": "b", "parent": "a"}}
        c: dict[str, object] = {"data": {"id": "c", "parent": "b"}}
        edge: dict[str, object] = {
            "group": "edges",
            "data": {"id": "e1", "source": "a", "target": "b"},
        }
        # Worst-case arrival order: deepest child first, edge in middle
        result = _topological_sort_elements([c, edge, b, a])
        node_ids = [
            e["data"]["id"]  # type: ignore[index]
            for e in result
            if e.get("group") != "edges"
        ]
        assert node_ids.index("a") < node_ids.index("b")
        assert node_ids.index("b") < node_ids.index("c")
        # Edge must end up in the non-node tail
        assert result[-1] is edge

    def test_multiple_roots_each_before_own_children(self) -> None:
        from src.ui.services.topology_data import _topological_sort_elements

        r1: dict[str, object] = {"data": {"id": "r1"}}
        r2: dict[str, object] = {"data": {"id": "r2"}}
        c1: dict[str, object] = {"data": {"id": "c1", "parent": "r1"}}
        c2: dict[str, object] = {"data": {"id": "c2", "parent": "r2"}}
        result = _topological_sort_elements([c1, c2, r1, r2])
        ids = [e["data"]["id"] for e in result]  # type: ignore[index]
        assert ids.index("r1") < ids.index("c1")
        assert ids.index("r2") < ids.index("c2")

    def test_edges_appended_after_all_nodes(self) -> None:
        from src.ui.services.topology_data import _topological_sort_elements

        node: dict[str, object] = {"data": {"id": "n1"}}
        edge: dict[str, object] = {
            "group": "edges",
            "data": {"id": "e1", "source": "n1", "target": "n1"},
        }
        result = _topological_sort_elements([edge, node])
        assert result[0] is node
        assert result[1] is edge

    def test_orphan_node_with_unknown_parent_treated_as_root(self) -> None:
        """Node with parent_id referencing a non-existent node must not crash."""
        from src.ui.services.topology_data import _topological_sort_elements

        orphan: dict[str, object] = {"data": {"id": "orphan", "parent": "ghost"}}
        result = _topological_sort_elements([orphan])
        assert len(result) == 1
        assert result[0] is orphan

    def test_all_input_nodes_are_preserved(self) -> None:
        from src.ui.services.topology_data import _topological_sort_elements

        nodes: list[dict[str, object]] = [{"data": {"id": str(i)}} for i in range(5)]
        result = _topological_sort_elements(nodes)
        assert len(result) == 5


class TestMergeSavedLayout:
    def test_merge_saved_layout_preserves_api_loaded_version(self) -> None:
        elements: list[dict[str, object]] = [
            {"data": {"id": "dev-1", "label": "Device 1", "version": 9}}
        ]
        saved_layout: dict[str, object] = {
            "elements": {
                "nodes": [
                    {
                        "data": {"id": "dev-1", "version": 1},
                        "position": {"x": 11, "y": 12},
                        "classes": "container",
                    }
                ]
            }
        }

        topology_data.merge_saved_layout(elements, saved_layout, {"dev-1"})

        assert elements[0]["data"]["version"] == 9
        assert elements[0]["position"] == {"x": 11, "y": 12}
        assert elements[0]["classes"] == "container"


class TestCollapsedStateCanvasJs:
    """Finding 2 / Finding 4: collapsed-node persistence in JS template."""

    def test_get_canvas_json_returns_collapsed_nodes_field(self) -> None:
        from src.ui.components.canvas_js import CANVAS_INIT_JS_TEMPLATE

        assert "collapsedNodes" in CANVAS_INIT_JS_TEMPLATE

    def test_get_canvas_json_collects_collapsed_flag(self) -> None:
        from src.ui.components.canvas_js import CANVAS_INIT_JS_TEMPLATE

        assert "_collapsed" in CANVAS_INIT_JS_TEMPLATE
        assert "collapsedNodes.push(n.id())" in CANVAS_INIT_JS_TEMPLATE

    def test_canvas_init_restores_collapsed_class_on_load(self) -> None:
        from src.ui.components.canvas_js import CANVAS_INIT_JS_TEMPLATE

        assert "n.data('_collapsed')" in CANVAS_INIT_JS_TEMPLATE
        assert "n.addClass('collapsed')" in CANVAS_INIT_JS_TEMPLATE

    def test_collapse_toggle_triggers_autosave(self) -> None:
        from src.ui.components.canvas_container_events import CANVAS_CONTAINER_EVENTS_JS

        assert "window.scheduleAutosave(800);" in CANVAS_CONTAINER_EVENTS_JS
        assert "_htAutosaveTimer" not in CANVAS_CONTAINER_EVENTS_JS


# ---------------------------------------------------------------------------
# layout_id parameter tests
# ---------------------------------------------------------------------------


class _LayoutIdSuccessClient:
    """Serves devices/connections normally and returns a specific diagram by id."""

    def __init__(self, layout_id: str = "layout-abc") -> None:
        self._layout_id = layout_id

    async def __aenter__(self) -> "_LayoutIdSuccessClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {"items": [{"id": "dev-1", "name": "Host", "type": "Server"}]},
            )
        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})
        if url.endswith(f"/api/diagrams/{self._layout_id}"):
            return _FakeResponse(
                200,
                {
                    "cytoscape_json": {
                        "elements": {
                            "nodes": [
                                {"data": {"id": "dev-1"}, "position": {"x": 5, "y": 6}}
                            ]
                        },
                        "zoom": 2,
                        "pan": {"x": 0, "y": 0},
                    }
                },
            )
        # Should NOT hit the list endpoint when layout_id is given
        if url.endswith("/api/diagrams/"):
            raise AssertionError("Should not list diagrams when layout_id is provided")
        return _FakeResponse(404)


class _LayoutIdFailClient:
    """Diagram detail returns 404 for the requested layout_id."""

    async def __aenter__(self) -> "_LayoutIdFailClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if url.endswith("/api/devices/"):
            return _FakeResponse(
                200,
                {"items": [{"id": "dev-1", "name": "Host", "type": "Server"}]},
            )
        if url.endswith("/api/connections/"):
            return _FakeResponse(200, {"items": []})
        if "/api/diagrams/" in url and not url.endswith("/api/diagrams/"):
            return _FakeResponse(404)
        return _FakeResponse(404)


class TestLoadCanvasDataLayoutId:
    """Tests for the layout_id parameter in load_canvas_data."""

    def test_layout_id_fetches_specific_diagram(self, monkeypatch) -> None:
        layout_id = "layout-abc"
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _LayoutIdSuccessClient(layout_id),
        )

        elements, saved_layout = asyncio.run(
            topology_data.load_canvas_data("token", layout_id=layout_id)
        )

        assert len(elements) >= 1
        assert saved_layout is not None
        assert saved_layout["zoom"] == 2

    def test_layout_id_non_200_returns_empty(self, monkeypatch) -> None:
        warnings: list[str] = []

        def fake_warning(message: str, **_: object) -> None:
            warnings.append(message)

        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _LayoutIdFailClient(),
        )
        monkeypatch.setattr(topology_data.logger, "warning", fake_warning)

        elements, saved_layout = asyncio.run(
            topology_data.load_canvas_data("token", layout_id="missing-layout")
        )

        assert elements == []
        assert saved_layout is None
        assert len(warnings) >= 1

    def test_empty_layout_id_falls_back_to_list(self, monkeypatch) -> None:
        """Empty string layout_id should use the list-all-diagrams path."""
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _StaleLayoutClient(),
        )

        elements, saved_layout = asyncio.run(
            topology_data.load_canvas_data("token", layout_id="")
        )

        # _StaleLayoutClient lists diagrams and returns layout-1
        assert saved_layout is not None
        assert len(elements) >= 1


class _EditorStateSuccessClient:
    async def __aenter__(self) -> "_EditorStateSuccessClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/editor-state" in url:
            return _FakeResponse(
                200,
                {
                    "source": "draft",
                    "has_unsaved_changes": True,
                    "current_diagram_id": "diagram-1",
                    "current_diagram_version": 3,
                    "draft_version": 7,
                    "cytoscape_json": {
                        "elements": {
                            "nodes": [
                                {"data": {"id": "dev-1"}, "position": {"x": 12, "y": 18}}
                            ],
                            "edges": [],
                        },
                        "zoom": 1,
                        "pan": {"x": 0, "y": 0},
                    },
                },
            )
        if "/api/diagrams/" in url:
            raise AssertionError("Editor-state path should not call diagram endpoints")
        if "/api/devices/" in url or "/api/connections/" in url:
            raise AssertionError("Editor-state path should not call inventory endpoints")
        return _FakeResponse(404)


class _EditorStateFailClient:
    async def __aenter__(self) -> "_EditorStateFailClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/editor-state" in url:
            return _FakeResponse(404)
        return _FakeResponse(500)


class _EditorStateGhostClient:
    async def __aenter__(self) -> "_EditorStateGhostClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/editor-state" in url:
            ghost_id = "00000000-0000-0000-0000-000000000777"
            return _FakeResponse(
                200,
                {
                    "source": "current",
                    "has_unsaved_changes": False,
                    "current_diagram_id": "diagram-ghost",
                    "current_diagram_version": 5,
                    "draft_version": None,
                    "cytoscape_json": {
                        "elements": {
                            "nodes": [
                                {
                                    "data": {
                                        "id": ghost_id,
                                        "label": "Old NAS (Deleted from inventory)",
                                        "ghost": True,
                                        "ghost_reason": "deleted_from_inventory",
                                        "ghost_status": "Deleted from inventory",
                                        "ghost_device_id": ghost_id,
                                        "ghost_original_name": "Old NAS",
                                        "ghost_original_type": "NAS",
                                        "editable": False,
                                    },
                                    "classes": "ghost",
                                    "position": {"x": 101, "y": 202},
                                }
                            ],
                            "edges": [],
                        },
                        "restore_summary": {
                            "ghost_count": 1,
                            "ghost_device_ids": [ghost_id],
                            "message": "Deleted devices were preserved as ghost placeholders instead of recreated into inventory.",
                            "ghost_recovery": {
                                "can_reconcile": True,
                                "allowed_actions": [
                                    "recreate_as_new_device",
                                    "map_to_existing_device",
                                ],
                            },
                        },
                    },
                },
            )
        return _FakeResponse(404)


class TestLoadCanvasDataEditorState:
    def test_topology_id_loads_editor_state_without_inventory_merge(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _EditorStateSuccessClient(),
        )

        elements, saved_layout = asyncio.run(
            topology_data.load_canvas_data("token", topology_id="topo-1")
        )

        assert len(elements) == 1
        assert elements[0]["data"]["id"] == "dev-1"
        assert saved_layout is not None
        assert saved_layout["_editor_state_source"] == "draft"
        assert saved_layout["_has_unsaved_changes"] is True
        assert saved_layout["_current_diagram_id"] == "diagram-1"
        assert saved_layout["_current_diagram_version"] == 3
        assert saved_layout["_draft_version"] == 7

    def test_editor_state_non_200_returns_empty(self, monkeypatch) -> None:
        warnings: list[str] = []

        def fake_warning(message: str, **_: object) -> None:
            warnings.append(message)

        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _EditorStateFailClient(),
        )
        monkeypatch.setattr(topology_data.logger, "warning", fake_warning)

        elements, saved_layout = asyncio.run(
            topology_data.load_canvas_data("token", topology_id="topo-2")
        )

        assert elements == []
        assert saved_layout is None
        assert len(warnings) >= 1

    def test_editor_state_preserves_ghost_metadata_and_restore_summary(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_data.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _EditorStateGhostClient(),
        )

        elements, saved_layout = asyncio.run(
            topology_data.load_canvas_data("token", topology_id="topo-ghost")
        )

        assert saved_layout is not None
        summary = saved_layout.get("restore_summary")
        assert isinstance(summary, dict)
        assert summary.get("ghost_count") == 1

        assert len(elements) == 1
        node = elements[0]
        assert node.get("classes") == "ghost"
        node_data = node.get("data")
        assert isinstance(node_data, dict)
        assert node_data.get("ghost") is True
        assert node_data.get("editable") is False

