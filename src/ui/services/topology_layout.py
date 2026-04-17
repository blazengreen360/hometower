"""Helpers for resolving a topology's DiagramLayout id and breadcrumb names."""
import httpx

from src.utils.logger import logger
from src.utils.settings import settings

_API = settings.api_base_url
_EMPTY_CANVAS: dict[str, object] = {"elements": {"nodes": [], "edges": []}}


async def fetch_breadcrumb_names(
    workspace_id: str, topology_id: str, headers: dict[str, str],
) -> tuple[str, str]:
    """Return (workspace_name, topology_name) for breadcrumb rendering."""
    ws_name = ""
    topo_name = ""
    try:
        async with httpx.AsyncClient() as http:
            ws_resp = await http.get(
                f"{_API}/api/workspaces/{workspace_id}",
                headers=headers, timeout=10.0,
            )
            if ws_resp.status_code == 200:
                ws_name = ws_resp.json().get("name", "")
            topo_resp = await http.get(
                f"{_API}/api/topologies/{topology_id}",
                headers=headers, timeout=10.0,
            )
            if topo_resp.status_code == 200:
                topo_name = topo_resp.json().get("name", "")
    except Exception as exc:
        logger.error("Breadcrumb name load error: {}", str(exc))
    return ws_name, topo_name

async def resolve_layout_id(topology_id: str, headers: dict[str, str]) -> str | None:
    """Fetch the first DiagramLayout id for a topology."""
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{_API}/api/topologies/{topology_id}/views/",
                headers=headers, timeout=10.0,
            )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                return str(items[0]["id"])
    except Exception as exc:
        logger.error("Resolve layout error: {}", str(exc))
    return None


async def ensure_layout(topology_id: str, headers: dict[str, str]) -> str | None:
    """Return layout_id for a topology, auto-creating one if needed."""
    layout_id = await resolve_layout_id(topology_id, headers)
    if layout_id:
        return layout_id
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{_API}/api/topologies/{topology_id}/views/",
                json={"name": "Default", "cytoscape_json": _EMPTY_CANVAS},
                headers=headers, timeout=10.0,
            )
        if resp.status_code == 201:
            return str(resp.json()["id"])
    except Exception as exc:
        logger.error("Auto-create layout error: {}", str(exc))
    return None
