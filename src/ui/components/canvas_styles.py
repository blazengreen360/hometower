"""Shared Cytoscape style definitions for topology canvas.

HT-027: Added build_theme_style_json() for theme-aware style arrays.
CANVAS_STYLE_JS remains as a backward-compatible alias (dark theme).
"""
import json

from src.models.types import DeviceType
from src.ui.design.tokens import DEVICE_TYPE_COLORS, THEMES

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


def _build_selector_styles(
    element_type: str,
    key_name: str,
    styles_by_value: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    selectors: list[dict[str, object]] = []
    for value, style in styles_by_value.items():
        selectors.append({
            "selector": f'{element_type}[{key_name} = "{value}"]',
            "style": style,
        })
    return selectors


_CANVAS_STYLES_REMOVED = None  # removed in HT-027; replaced by build_theme_style_json


def build_theme_style_json(theme_name: str) -> str:
    """Return JSON-serialised Cytoscape style array for the given theme.

    Falls back to 'dark' if the theme name is unknown.
    Device type colours (DEVICE_TYPE_COLORS) are not theme-dependent.
    """
    t = THEMES.get(theme_name, THEMES["dark"])
    status_style_by_device_status: dict[str, dict[str, object]] = {
        "Offline": {"opacity": 0.5},
        "Maintenance": {"border-width": 3, "border-color": t["warning"]},
        "Planned": {"border-style": "dashed"},
        "Decommissioned": {"opacity": 0.3},
    }
    styles: list[dict[str, object]] = [
        {
            "selector": "node",
            "style": {
                "label":            "data(label)",
                "shape":            "data(shape)",
                "background-color": t["accent"],
                "color":            t["text_primary"],
                "text-valign":      "bottom",
                "text-halign":      "center",
                "font-family":      "Inter, sans-serif",
                "font-size":        "12px",
                "width":            48,
                "height":           48,
                "border-width":     1,
                "border-color":     t["border"],
            },
        },
        {
            "selector": "node:selected",
            "style": {
                "border-color": t["accent"],
                "border-width": 2,
            },
        },
        {
            "selector": "edge",
            "style": {
                "curve-style":        "bezier",
                "target-arrow-shape": "triangle",
                "line-color":         t["text_secondary"],
                "target-arrow-color": t["text_secondary"],
                "width":              2,
            },
        },
        {
            "selector": "edge:selected",
            "style": {
                "width":              4,
                "line-color":         t["accent"],
                "target-arrow-color": t["accent"],
            },
        },
    ]
    # Per-device-type colour rules (DEVICE_TYPE_COLORS is not theme-dependent)
    for dtype, colour in DEVICE_TYPE_COLORS.items():
        styles.append({
            "selector": f'node[device_type = "{dtype.value}"]',
            "style":    {"background-color": colour},
        })
    # Status and connection-type styles
    styles.extend(_build_selector_styles("node", "status", status_style_by_device_status))
    styles.extend(_build_selector_styles(
        "edge",
        "connection_type",
        {k: v for k, v in EDGE_STYLE_BY_CONNECTION_TYPE.items() if k != "Ethernet"},
    ))
    # Compound node styles — applies to any node that has children
    _compound_style: dict[str, object] = {
        "shape":              "roundrectangle",
        "background-opacity": 0.12,
        "border-width":       2,
        "border-style":       "dashed",
        "border-color":       t["border"],
        "padding":            "24px",
        "text-valign":        "top",
        "text-halign":        "center",
        "font-size":          "14px",
    }
    styles.append({"selector": ":parent",        "style": _compound_style})
    # node.container — empty container (no children yet)
    styles.append({"selector": "node.container",  "style": _compound_style})
    # node.collapsed — shrink compound when children are hidden
    styles.append({
        "selector": "node.collapsed",
        "style": {
            "padding":    "8px",
            "min-width":  "60px",
            "min-height": "60px",
        },
    })
    # Draft node styles (HT-051)
    styles.append({
        "selector": "node.draft",
        "style": {
            "border-width":     2,
            "border-style":     "dashed",
            "border-color":     t["warning"],
            "opacity":          1,
            "label":            "data(label)\nDraft",
            "text-wrap":        "wrap",
            "text-max-width":   "80px",
            "font-size":        "12px",
        },
    })
    styles.append({
        "selector": "node.draft-error",
        "style": {
            "border-color": t["error"],
            "border-width": 3,
        },
    })
    # Ghost placeholder styles (HT-075)
    styles.append({
        "selector": "node.ghost",
        "style": {
            "background-color": t["bg_surface_raised"],
            "border-width": 3,
            "border-style": "dashed",
            "border-color": t["warning"],
            "opacity": 0.78,
            "text-wrap": "wrap",
            "text-max-width": "110px",
            "color": t["text_secondary"],
        },
    })
    # Network filter/highlight styles (HT-022)
    styles.append({
        "selector": "node.ht-network-match",
        "style": {
            "border-width": 4,
            "border-color": "data(network_highlight_color)",
            "opacity": 1,
        },
    })
    styles.append({
        "selector": "node.ht-network-dim",
        "style": {
            "opacity": 0.2,
        },
    })
    styles.append({
        "selector": "edge.ht-network-match",
        "style": {
            "opacity": 1,
            "width": 3,
        },
    })
    styles.append({
        "selector": "edge.ht-network-dim",
        "style": {
            "opacity": 0.08,
        },
    })
    return json.dumps(styles)


# Backward-compatible alias — dark theme. Kept until canvas.py migration completes.
CANVAS_STYLE_JS: str = build_theme_style_json("dark")
