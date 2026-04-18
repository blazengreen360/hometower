"""Design system constants — no hardcoded colors or spacing anywhere else in src/ui/.

HT-027: Extended with THEMES dict and STATIC_CSS_VARS for theme engine.
All existing COLOR_* constants are preserved as backward-compatible aliases
pointing to dark ("Control Room") theme values.
"""
from src.models.types import DeviceType

# ── Theme palettes (HT-027) ──────────────────────────────────────────────
THEMES: dict[str, dict[str, str]] = {
    "dark": {
        # Backgrounds
        "bg_base":           "#0f0f1a",
        "bg_surface":        "#1a1a2e",
        "bg_surface_raised": "#252540",
        "bg_sidebar":        "#161628",
        # Accent
        "accent":            "#6366f1",
        "accent_hover":      "#818cf8",
        "accent_glow":       "rgba(99, 102, 241, 0.12)",
        # Text
        "text_primary":      "#e2e8f0",
        "text_secondary":    "#94a3b8",
        "text_on_accent":    "#ffffff",
        # Border
        "border":            "rgba(255, 255, 255, 0.08)",
        # Semantic
        "success":           "#4ade80",
        "warning":           "#fbbf24",
        "error":             "#f87171",
        "ipam_used":         "#4ade80",
        "ipam_free":         "#475569",
        "ipam_gateway":      "#38bdf8",
        "ipam_conflict":     "#f87171",
        "ipam_reserved":     "#fbbf24",
        # Shadows (full box-shadow values)
        "shadow_sm":         "0 1px 2px rgba(0,0,0,0.3)",
        "shadow_md":         "0 4px 12px rgba(0,0,0,0.4)",
        "shadow_lg":         "0 8px 24px rgba(0,0,0,0.5)",
    },
    "light": {
        "bg_base":           "#f8fafc",
        "bg_surface":        "#ffffff",
        "bg_surface_raised": "#ffffff",
        "bg_sidebar":        "#f1f5f9",
        "accent":            "#4f46e5",
        "accent_hover":      "#4338ca",
        "accent_glow":       "rgba(79, 70, 229, 0.15)",
        "text_primary":      "#1e293b",
        "text_secondary":    "#64748b",
        "text_on_accent":    "#ffffff",
        "border":            "rgba(0, 0, 0, 0.08)",
        "success":           "#16a34a",
        "warning":           "#d97706",
        "error":             "#dc2626",
        "ipam_used":         "#16a34a",
        "ipam_free":         "#cbd5e1",
        "ipam_gateway":      "#0284c7",
        "ipam_conflict":     "#dc2626",
        "ipam_reserved":     "#d97706",
        "shadow_sm":         "0 1px 2px rgba(0,0,0,0.05)",
        "shadow_md":         "0 4px 12px rgba(0,0,0,0.08)",
        "shadow_lg":         "0 8px 24px rgba(0,0,0,0.12)",
    },
    "midnight": {
        "bg_base":           "#050510",
        "bg_surface":        "#0a0a1f",
        "bg_surface_raised": "#0f0f26",
        "bg_sidebar":        "#07070e",
        "accent":            "#00e5ff",
        "accent_hover":      "#67ffda",
        "accent_glow":       "rgba(0, 229, 255, 0.3)",
        "text_primary":      "#e0f7fa",
        "text_secondary":    "#80cbc4",
        "text_on_accent":    "#001020",
        "border":            "rgba(0, 229, 255, 0.15)",
        "success":           "#4ade80",
        "warning":           "#fbbf24",
        "error":             "#f87171",
        "ipam_used":         "#4ade80",
        "ipam_free":         "#334155",
        "ipam_gateway":      "#22d3ee",
        "ipam_conflict":     "#f87171",
        "ipam_reserved":     "#fbbf24",
        "shadow_sm":         "0 1px 2px rgba(0,0,0,0.6)",
        "shadow_md":         "0 4px 12px rgba(0,0,0,0.7)",
        "shadow_lg":         "0 8px 24px rgba(0,0,0,0.8)",
    },
}

# ── Static structural tokens (never theme-dependent) ─────────────────────
STATIC_CSS_VARS: dict[str, str] = {
    "--ht-radius-card":     "10px",
    "--ht-radius-input":    "8px",
    "--ht-radius-modal":    "12px",
    "--ht-radius-pill":     "9999px",
    "--ht-transition-fast": "150ms ease",
    "--ht-transition-norm": "200ms ease",
    "--ht-page-max":        "1180px",
    "--ht-font-body": (
        "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,"
        " 'Helvetica Neue', Arial, sans-serif"
    ),
    "--ht-font-body-lg":    "1rem",
    "--ht-font-title":      "1.05rem",
    "--ht-font-h1":         "clamp(1.85rem, 2vw + 1.15rem, 2.6rem)",
    "--ht-font-h2":         "clamp(1.35rem, 1vw + 1rem, 1.8rem)",
    "--ht-font-label":      "0.82rem",
    "--ht-font-caption":    "0.74rem",
    "--ht-font-mono": (
        "'Fira Mono', 'SF Mono', 'Cascadia Mono', 'Consolas', monospace"
    ),
}

# ── Backward-compatibility aliases (dark theme values) ───────────────────
# NOTE: Any component importing COLOR_* still compiles and runs correctly.
# Remove these aliases only after all COLOR_* references are migrated (Phase 4).
_dark = THEMES["dark"]
COLOR_PRIMARY      = _dark["accent"]             # #6366f1
COLOR_PRIMARY_DARK = _dark["accent_hover"]       # #818cf8
COLOR_SURFACE      = _dark["bg_surface"]         # #1a1a2e
COLOR_SURFACE_ALT  = _dark["bg_surface_raised"]  # #252540
COLOR_TEXT         = _dark["text_primary"]       # #e2e8f0
COLOR_TEXT_MUTED   = _dark["text_secondary"]     # #94a3b8
COLOR_ERROR        = _dark["error"]              # #f87171
COLOR_SUCCESS      = _dark["success"]            # #4ade80
COLOR_WARNING      = _dark["warning"]            # #fbbf24
DEFAULT_NETWORK_COLOR = "#3b82f6"

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

# --- Monospace font ---
FONT_MONO = "'Fira Mono', 'Courier New', monospace"

# --- Device type color chips ---
DEVICE_TYPE_COLORS: dict[DeviceType, str] = {
    DeviceType.Server: "#6366f1",
    DeviceType.Switch: "#22d3ee",
    DeviceType.Router: "#f59e0b",
    DeviceType.NAS: "#10b981",
    DeviceType.UPS: "#f97316",
    DeviceType.SBC: "#8b5cf6",
    DeviceType.Workstation: "#3b82f6",
    DeviceType.VM: "#a78bfa",
    DeviceType.LXC: "#34d399",
    DeviceType.Docker: "#60a5fa",
    DeviceType.Application: "#fb7185",
    DeviceType.VLAN: "#fbbf24",
    DeviceType.Subnet: "#e879f9",
}

# --- Device type Material Icon names ---
DEVICE_TYPE_ICONS: dict[DeviceType, str] = {
    DeviceType.Server: "dns",
    DeviceType.Switch: "device_hub",
    DeviceType.Router: "router",
    DeviceType.NAS: "storage",
    DeviceType.UPS: "battery_full",
    DeviceType.SBC: "developer_board",
    DeviceType.Workstation: "computer",
    DeviceType.VM: "cloud",
    DeviceType.LXC: "view_in_ar",
    DeviceType.Docker: "widgets",
    DeviceType.Application: "apps",
    DeviceType.VLAN: "lan",
    DeviceType.Subnet: "account_tree",
}
