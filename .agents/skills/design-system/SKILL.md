---
name: design-system
description: Hometower's design token system — CSS variable names, semantic token rules, Tailwind interop syntax, icon/shape mappings, and component visual conventions. Read this when building or auditing any UI component.
---

# design-system

Hometower uses a custom theme engine via CSS variables in `src/ui/design/tokens.py`.

## Token Usage Rules

1. **Zero hardcoded colors** — never use `#hex`, `rgb()`, `red`, `blue`, or Tailwind color classes (`bg-blue-500`) for structural elements
2. **Semantic tokens only** — `var(--bg_surface)`, `var(--text_primary)`, `var(--accent)`, `var(--error)`, `var(--border)`
3. **Tailwind interop** — use arbitrary value syntax: `.classes("bg-[var(--bg_surface)] text-[var(--text_primary)] border-[var(--border)]")`
4. **Icons** — use `DEVICE_TYPE_ICONS` mappings from `tokens.py`. Material Symbols only.
5. **Monospace** — IPs, MACs, ports, technical identifiers: `font-[var(--ht-font-mono)]`

## Key CSS Variables

| Variable | Purpose |
|---|---|
| `--bg_surface` | Default background |
| `--bg_surface_raised` | Elevated panels (detail drawers) |
| `--text_primary` | Primary text |
| `--text_secondary` | Secondary/muted text |
| `--accent` | Primary action color |
| `--accent_glow` | Selected node glow |
| `--error` | Error states |
| `--border` | Border color |
| `--ht-font-mono` | Monospace font stack |

## Component Visual Conventions

**Canvas (Cytoscape.js):**
- Takes remaining vertical space `h-full`
- Device nodes use `DEVICE_SHAPES` mapped from `tokens.py`
- Selected nodes get glowing border (`var(--accent_glow)`)
- Edge styles: Solid = physical connection, Dashed = logical connection

**Device Properties Panel:**
- Sliding drawer from right edge
- Background: `var(--bg_surface_raised)` to lift off canvas
- Inline edit for simple strings, not modals
- Custom fields: dense key-value grid

**Inventory List:**
- Virtual scroll for large lists (`ui.table` or AgGrid)
- Persistent search/filter bar at top
- Row click opens slide-in detail panel, not new page

**Map View (Leaflet):**
- OpenStreetMap tiles (dark variant in dark mode)
- Marker clusters for dense locations
- Bounding box auto-fits all locations on load

## Anti-Patterns

- `text-red-500` → use `text-[var(--error)]`
- `bg-gray-800` → use `bg-[var(--bg_surface)]`
- Hardcoded hex in JS strings → interpolate from Python: `f"color: '{tokens.PRIMARY}'"`
- `ui.button(onClick=...)` → not valid NiceGUI, use `ui.button(on_click=...)`
