"""Pure validation functions for connections — no I/O, no side effects."""
import uuid


def validate_no_self_loop(source_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """Raise ValueError if source and target are the same device."""
    if source_id == target_id:
        raise ValueError("Cannot connect a device to itself")
