"""Workspace/Topology/View domain logic — pure functions, no I/O.

Only imports standard-library modules. No SQLModel, FastAPI, or network calls.
"""

MAX_NAME_LENGTH = 255


def validate_workspace_name(name: str) -> str:
    """Strip whitespace, reject empty or too-long names. Return stripped name."""
    stripped = name.strip()
    if not stripped:
        raise ValueError("Workspace name must not be empty")
    if len(stripped) > MAX_NAME_LENGTH:
        raise ValueError(
            f"Workspace name must not exceed {MAX_NAME_LENGTH} characters"
        )
    return stripped


def validate_topology_name(name: str) -> str:
    """Strip whitespace, reject empty or too-long names. Return stripped name."""
    stripped = name.strip()
    if not stripped:
        raise ValueError("Topology name must not be empty")
    if len(stripped) > MAX_NAME_LENGTH:
        raise ValueError(
            f"Topology name must not exceed {MAX_NAME_LENGTH} characters"
        )
    return stripped


def validate_view_name(name: str) -> str:
    """Strip whitespace, reject empty or too-long names. Return stripped name."""
    stripped = name.strip()
    if not stripped:
        raise ValueError("View name must not be empty")
    if len(stripped) > MAX_NAME_LENGTH:
        raise ValueError(
            f"View name must not exceed {MAX_NAME_LENGTH} characters"
        )
    return stripped
