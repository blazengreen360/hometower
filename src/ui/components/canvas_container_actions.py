"""Container detach and growth helpers for the topology canvas (HT-077)."""

from src.ui.components.canvas_container_actions_core import (
    CANVAS_CONTAINER_ACTIONS_CORE_JS,
)
from src.ui.components.canvas_container_actions_growth import (
    CANVAS_CONTAINER_ACTIONS_GROWTH_JS,
)
from src.ui.components.canvas_container_actions_pending import (
    CANVAS_CONTAINER_ACTIONS_PENDING_JS,
)


CANVAS_CONTAINER_ACTIONS_JS = (
    CANVAS_CONTAINER_ACTIONS_CORE_JS
    + CANVAS_CONTAINER_ACTIONS_PENDING_JS
    + CANVAS_CONTAINER_ACTIONS_GROWTH_JS
)