"""Design system constants — no hardcoded colors or spacing anywhere else in src/ui/."""
from src.models.types import DeviceType

# --- Colour palette ---
COLOR_PRIMARY = "#4f46e5"        # Indigo-600 — brand accent
COLOR_PRIMARY_DARK = "#4338ca"   # Indigo-700 — hover state
COLOR_SURFACE = "#1e1e2e"        # Dark canvas background
COLOR_SURFACE_ALT = "#27273a"    # Cards and panels
COLOR_TEXT = "#cdd6f4"           # Primary text on dark backgrounds
COLOR_TEXT_MUTED = "#a6adc8"     # Secondary / placeholder text
COLOR_ERROR = "#f38ba8"          # Error / destructive
COLOR_SUCCESS = "#a6e3a1"        # Success / confirmation
COLOR_WARNING = "#f9e2af"        # Warning

# --- Spacing (CSS values) ---
SPACING_XS = "4px"
SPACING_SM = "8px"
SPACING_MD = "16px"
SPACING_LG = "24px"
SPACING_XL = "32px"

# --- Typography ---
FONT_SM = "0.875rem"
FONT_MD = "1rem"
FONT_LG = "1.25rem"
FONT_XL = "1.5rem"
FONT_2XL = "2rem"

# --- Device shapes for Cytoscape.js ---
DEVICE_SHAPES: dict[DeviceType, str] = {
    DeviceType.Server: "rectangle",
    DeviceType.Switch: "diamond",
    DeviceType.Router: "triangle",
    DeviceType.NAS: "hexagon",
    DeviceType.UPS: "round-rectangle",
    DeviceType.SBC: "round-rectangle",
    DeviceType.Workstation: "rectangle",
    DeviceType.VM: "ellipse",
    DeviceType.LXC: "ellipse",
    DeviceType.Docker: "round-rectangle",
    DeviceType.Application: "round-rectangle",
    DeviceType.VLAN: "barrel",
    DeviceType.Subnet: "barrel",
}

# String-keyed alias for lookups against API response values (e.g. "Server", "Switch").
DEVICE_SHAPE_BY_VALUE: dict[str, str] = {k.value: v for k, v in DEVICE_SHAPES.items()}
