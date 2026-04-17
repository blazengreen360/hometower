"""Compatibility facade for device detail panel section renderers."""

from src.ui.components.device_detail_attachments_section import render_attachments_section
from src.ui.components.device_detail_connections_section import render_connections_section
from src.ui.components.device_detail_custom_fields_section import render_custom_fields_section
from src.ui.components.device_detail_networks_section import render_networks_section
from src.ui.components.device_detail_tags_section import render_tags_section

__all__ = [
    "render_attachments_section",
    "render_tags_section",
    "render_custom_fields_section",
    "render_connections_section",
    "render_networks_section",
]
