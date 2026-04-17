"""Service domain logic — pure functions, no I/O (HT-023)."""
import uuid
from typing import Optional


def validate_port(port: Optional[int]) -> Optional[int]:
    """Return port unchanged or None. Raise ValueError if outside [1, 65535]."""
    if port is None:
        return None
    if not (1 <= port <= 65535):
        raise ValueError("Port must be between 1 and 65535")
    return port


def validate_no_dependency_cycle(
    proposed_service_id: uuid.UUID,
    proposed_depends_on_id: uuid.UUID,
    all_deps: list[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """Raise ValueError('Circular dependency detected') if the proposed edge creates a cycle.

    Self-dependency (proposed_service_id == proposed_depends_on_id) is also rejected.
    Uses BFS on the depends_on graph starting from proposed_depends_on_id.
    If proposed_service_id is reachable from proposed_depends_on_id → cycle.
    """
    if proposed_service_id == proposed_depends_on_id:
        raise ValueError("Circular dependency detected")

    # Build adjacency: service_id → {depends_on_id, ...}
    graph: dict[uuid.UUID, set[uuid.UUID]] = {}
    for src, dst in all_deps:
        graph.setdefault(src, set()).add(dst)

    # BFS from proposed_depends_on_id
    visited: set[uuid.UUID] = set()
    queue: list[uuid.UUID] = [proposed_depends_on_id]
    while queue:
        node = queue.pop(0)
        if node == proposed_service_id:
            raise ValueError("Circular dependency detected")
        if node in visited:
            continue
        visited.add(node)
        queue.extend(graph.get(node, set()))
