"""Support helpers for canvas Cytoscape style generation."""

from urllib.parse import quote

from src.models.types import DeviceType
from src.ui.design.tokens import DEVICE_TYPE_COLORS, DEVICE_TYPE_ICONS, THEMES

EDGE_STYLE_BY_CONNECTION_TYPE: dict[str, dict[str, object]] = {
    "Ethernet": {"line-style": "solid", "width": 2},
    "WiFi": {"line-style": "dashed"},
    "Fibre": {"width": 4},
    "iSCSI": {"line-style": "dotted"},
    "NFS": {"line-style": "dotted"},
    "VM": {
        "line-style": "dashed",
        "line-color": DEVICE_TYPE_COLORS[DeviceType.VM],
        "target-arrow-color": DEVICE_TYPE_COLORS[DeviceType.VM],
    },
    "Other": {"width": 1, "opacity": 0.7},
}


def build_selector_styles(
    element_type: str,
    key_name: str,
    styles_by_value: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "selector": f'{element_type}[{key_name} = "{value}"]',
            "style": style,
        }
        for value, style in styles_by_value.items()
    ]


def _container_watermark_uri(icon_name: str, fill_color: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        "<text x='50%' y='54%' text-anchor='middle' dominant-baseline='middle' "
        f"font-family='Material Icons' font-size='72' fill='{fill_color}' fill-opacity='0.15'>{icon_name}</text>"
        "</svg>"
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def build_container_icon_styles(theme_name: str) -> list[dict[str, object]]:
    fill_color = THEMES.get(theme_name, THEMES["dark"])["text_secondary"]
    styles: list[dict[str, object]] = []
    for device_type, icon_name in DEVICE_TYPE_ICONS.items():
        watermark_style = {
            "background-image": _container_watermark_uri(icon_name, fill_color),
            "background-fit": "contain",
            "background-width": "70%",
            "background-height": "70%",
            "background-position-x": "50%",
            "background-position-y": "55%",
            "background-image-opacity": 0.15,
            "background-clip": "node",
        }
        styles.append({
            "selector": f':parent[device_type = "{device_type.value}"]',
            "style": watermark_style,
        })
        styles.append({
            "selector": f'node.container[device_type = "{device_type.value}"]',
            "style": watermark_style,
        })
    return styles