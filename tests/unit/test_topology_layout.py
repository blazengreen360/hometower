"""Unit tests for topology layout helpers (resolve, ensure, breadcrumb)."""
import asyncio

from src.ui.services import topology_layout


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


# ---------------------------------------------------------------------------
# resolve_layout_id
# ---------------------------------------------------------------------------


class _ViewsExistClient:
    """GET /api/topologies/{id}/views/ returns one view."""

    async def __aenter__(self) -> "_ViewsExistClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/views/" in url:
            return _FakeResponse(200, {"items": [{"id": "view-1"}]})
        return _FakeResponse(404)


class _ViewsEmptyClient:
    """GET /api/topologies/{id}/views/ returns empty list."""

    async def __aenter__(self) -> "_ViewsEmptyClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/views/" in url:
            return _FakeResponse(200, {"items": []})
        return _FakeResponse(404)


class TestResolveLayoutId:
    def test_returns_layout_id_when_views_exist(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_layout.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _ViewsExistClient(),
        )

        result = asyncio.run(
            topology_layout.resolve_layout_id("topo-1", {"Authorization": "Bearer t"})
        )

        assert result == "view-1"

    def test_returns_none_when_no_views(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_layout.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _ViewsEmptyClient(),
        )

        result = asyncio.run(
            topology_layout.resolve_layout_id("topo-1", {"Authorization": "Bearer t"})
        )

        assert result is None


# ---------------------------------------------------------------------------
# ensure_layout
# ---------------------------------------------------------------------------


class _EnsureExistingClient:
    """Views endpoint returns an existing layout — no creation needed."""

    async def __aenter__(self) -> "_EnsureExistingClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/views/" in url:
            return _FakeResponse(200, {"items": [{"id": "existing-layout"}]})
        return _FakeResponse(404)

    async def post(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        raise AssertionError("Should not create when layout already exists")


class _EnsureCreateClient:
    """Views endpoint returns empty, POST creates a new layout."""

    def __init__(self) -> None:
        self.post_called = False

    async def __aenter__(self) -> "_EnsureCreateClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/views/" in url:
            return _FakeResponse(200, {"items": []})
        return _FakeResponse(404)

    async def post(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        self.post_called = True
        return _FakeResponse(201, {"id": "new-layout-99"})


class _EnsureFailClient:
    """Both views GET and POST fail."""

    async def __aenter__(self) -> "_EnsureFailClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/views/" in url:
            return _FakeResponse(200, {"items": []})
        return _FakeResponse(500)

    async def post(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(500)


class TestEnsureLayout:
    def test_returns_existing_layout(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_layout.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _EnsureExistingClient(),
        )

        result = asyncio.run(
            topology_layout.ensure_layout("topo-1", {"Authorization": "Bearer t"})
        )

        assert result == "existing-layout"

    def test_creates_new_layout_when_none_found(self, monkeypatch) -> None:
        client = _EnsureCreateClient()
        monkeypatch.setattr(
            topology_layout.httpx,
            "AsyncClient",
            lambda *args, **kwargs: client,
        )

        result = asyncio.run(
            topology_layout.ensure_layout("topo-1", {"Authorization": "Bearer t"})
        )

        assert result == "new-layout-99"

    def test_returns_none_on_api_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_layout.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _EnsureFailClient(),
        )

        result = asyncio.run(
            topology_layout.ensure_layout("topo-1", {"Authorization": "Bearer t"})
        )

        assert result is None


# ---------------------------------------------------------------------------
# fetch_breadcrumb_names
# ---------------------------------------------------------------------------


class _BreadcrumbSuccessClient:
    """Both workspace and topology detail return 200 with names."""

    async def __aenter__(self) -> "_BreadcrumbSuccessClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        if "/api/workspaces/" in url:
            return _FakeResponse(200, {"name": "My Lab"})
        if "/api/topologies/" in url:
            return _FakeResponse(200, {"name": "Core Network"})
        return _FakeResponse(404)


class _BreadcrumbFailClient:
    """Both workspace and topology detail return 500."""

    async def __aenter__(self) -> "_BreadcrumbFailClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def get(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(500)


class TestFetchBreadcrumbNames:
    def test_returns_names_on_success(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_layout.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _BreadcrumbSuccessClient(),
        )

        ws_name, topo_name = asyncio.run(
            topology_layout.fetch_breadcrumb_names(
                "ws-1", "topo-1", {"Authorization": "Bearer t"}
            )
        )

        assert ws_name == "My Lab"
        assert topo_name == "Core Network"

    def test_returns_empty_strings_on_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(
            topology_layout.httpx,
            "AsyncClient",
            lambda *args, **kwargs: _BreadcrumbFailClient(),
        )

        ws_name, topo_name = asyncio.run(
            topology_layout.fetch_breadcrumb_names(
                "ws-1", "topo-1", {"Authorization": "Bearer t"}
            )
        )

        assert ws_name == ""
        assert topo_name == ""
