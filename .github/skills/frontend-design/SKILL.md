---
name: frontend-design
description: Production-grade frontend design system for Hometower. Evidence-based rules for data-dense UI, topology canvas UX, dark theme excellence, side panel patterns, micro-interactions, and NiceGUI-specific implementation. Read this before designing or reviewing any UI component, page layout, or canvas interaction.
---

# frontend-design

Hometower is a technical tool used by homelabbers who interact with it repeatedly and deeply. Every design decision must serve that user — dense information presented clearly, not simplified into something generic. The benchmark is tools like Linear, Grafana, VS Code, and Cloudcraft: high information density, confident dark aesthetic, no wasted motion.

Read the `design-system` skill first for token names and component conventions. This skill covers the *why* and *how* behind those conventions.

---

## 1. Data-Dense UI

### 8pt Grid — Non-Negotiable

Every spacing value must be a multiple of 8px. The existing token set (`SPACING_XS=4px`, `SPACING_SM=8px`, etc.) is correct — use it.

| Context | Spacing rule |
|---|---|
| Between inline elements (icon + label) | 4px (SPACING_XS) |
| Between form rows | 8px (SPACING_SM) |
| Between card sections | 16px (SPACING_MD) |
| Between page-level regions | 24–32px (SPACING_LG / SPACING_XL) |
| Internal padding ≤ external padding | Always — prevents visual confusion in dense layouts |

### Typography for Density

Data-dense interfaces have strict type roles. Do not improvise.

| Role | Size | Weight | Font | Use for |
|---|---|---|---|---|
| Page title | `clamp(1.35rem, 1vw + 1rem, 1.8rem)` | 600 | Body | Page H1 |
| Section header | `1.05rem` | 600 | Body | Card titles, panel headers |
| Body / table row | `0.875rem` | 400 | Body | Most content |
| Label / caption | `0.82rem` | 500 | Body | Form labels, column headers |
| Monospace data | `0.8rem` | 400 | Mono | IPs, MACs, ports, IDs, CIDRs |
| Timestamp / meta | `0.74rem` | 400 | Body | Timestamps, secondary metadata |

**Monospace is mandatory** for all technical identifiers. Monospace allows precise character width calculation — two IPs of different lengths occupy predictable space, tables stay aligned, scanning is faster. Use `font-[var(--ht-font-mono)]` via the design token.

### Information Hierarchy Rules

1. **Every element must earn its place.** No decorative elements without analytical purpose.
2. **No redundant data.** If the column header says "IP", the row value should not say "IP: 192.168.1.1".
3. **Use background shifts over visible gridlines.** Alternating row tints (`rgba(255,255,255,0.02)`) reduce noise vs. explicit borders. Reserve visible borders for structural separation only.
4. **Show summary first.** Device name, type icon, status chip — then IP, MAC, notes on demand. Progressive disclosure prevents cognitive overload.
5. **Color encodes only status.** Never use accent color for structural decoration. Color means: green=healthy, red=error, orange=warning, blue=info. Always pair with icon + text (never color alone — colorblind users exist).

---

## 2. Dark Theme Excellence

The current dark palette (`bg_base: #0f0f1a`, `bg_surface: #1a1a2e`, `bg_surface_raised: #252540`) is well-structured. Follow these rules when extending it.

### Elevation via Lightness, Not Shadows

Dark mode has no physical light source. Shadows are invisible against dark backgrounds. Elevation is conveyed by **lightness increments**:

| Layer | Lightness step | Token | Example use |
|---|---|---|---|
| Base | L:10 | `bg_base` | Page background |
| Surface | L:14 | `bg_surface` | Cards, panels |
| Raised | L:18 | `bg_surface_raised` | Drawers, popovers, modals |
| Overlay | L:22 | (no token — use sparingly) | Tooltip backgrounds |

Each step is +4 lightness points. Respect this rhythm. A component that breaks the sequence creates a visual hierarchy error even if it looks "close enough."

Use the shadow tokens (`shadow_sm`, `shadow_md`, `shadow_lg`) only for non-dark-mode compatibility or subtle depth cues at component edges — never as the primary elevation signal.

### Text Contrast Hierarchy

Never use pure white (`#ffffff`) on dark backgrounds — it causes optical halation (text appears to bleed into background). The existing tokens are correct:

| Role | Token | Approx lightness | WCAG ratio on `bg_base` |
|---|---|---|---|
| Primary text | `text_primary` (#e2e8f0) | L:92 | ~13:1 ✅ |
| Secondary / muted | `text_secondary` (#94a3b8) | L:75 | ~7:1 ✅ |
| Disabled / ghost | Use at 50% opacity on `text_secondary` | ~L:55 | ≥3:1 ✅ |
| On-accent (button labels) | `text_on_accent` (#ffffff) | L:100 | Verified per accent |

WCAG 2.1 AA minimum: **4.5:1** for body text, **3:1** for large text (18pt+) and UI components. Always verify with a contrast checker when introducing a new color combination.

### Border and Divider Rules

- Primary border: `rgba(255, 255, 255, 0.08)` — 8% white opacity (the `border` token). Use for card edges and input outlines.
- Secondary dividers: `rgba(255, 255, 255, 0.04)` — more subtle, for within-card separation.
- Never use fully opaque borders on dark surfaces — they look painted on, not structural.
- Between two neutral zones at the same elevation: use lightness shift alone, no border.

### When to Use Color vs. Neutral

- **Neutral tones only** for navigation chrome, toolbars, sidebars, and structural containers.
- **Accent color** (`#6366f1`) for: primary CTA buttons, selected state, active nav item, focus rings.
- **Status colors** (success/warning/error) for: status chips, alert banners, validation feedback. Never for decoration.
- **Device type colors** (from `DEVICE_TYPE_COLORS`) for: node chips on canvas, type badges in inventory. These are data — not UI chrome.

---

## 3. Topology Canvas UX

The canvas is the primary interaction surface. Design for it first, not last.

### Node Design Principles

**What belongs on the node (always visible):**
- Device type icon (Material Symbol, 20px)
- Device name (12px, bold, centered below icon, max 20 chars then truncate + tooltip)
- Status indicator (4px dot, bottom-right, green/red/grey)

**What belongs on hover only:**
- IP address (tooltip or inline expand)
- Device type label
- Connection count

**What belongs in the properties panel:**
- Everything else. The canvas node is a summary, not a data sheet.

**At zoom < 40%:** Hide text labels entirely. Show icon + status dot only. Prevents label collision and improves legibility at overview scale.

### Selection and Interaction Model

| Action | Behaviour |
|---|---|
| Single click | Select node, open properties panel |
| Ctrl+click | Add to selection (multi-select) |
| Box drag on canvas | Marquee select all nodes inside box |
| Click empty canvas | Deselect all |
| Escape | Deselect all, close panel |
| Double-click node | Focus-zoom to 150% on that node |
| Right-click node | Context menu (edit, delete, connect) |

Selected nodes: accent glow border (`var(--accent_glow)`, 2px solid `var(--accent)`). Multi-selected: same style, count badge shown in toolbar.

### Edge Routing

- **Solid line** = physical connection (Ethernet, fibre)
- **Dashed line** = logical connection (VLAN, tunnel, VPN)
- Edge label: optional, 10px, `text_secondary` — show port numbers if set
- Avoid crossing edges where possible by using Cytoscape's `cose-bilkent` or `cola` layout
- Orthogonal routing (right-angle edges) reduces visual clutter vs. curved on dense graphs

### Performance Rules (50–100 nodes)

These are enforced thresholds, not suggestions:

1. **Use `cy.getElementById(id)` for node lookups** — O(1), never iterate all elements or use compound selectors.
2. **`hideEdgesOnViewport: true`** — reduces drag/pan cost significantly on ≥30 nodes.
3. **Viewport culling** — Cytoscape handles this natively; do not fight it by forcing all nodes into view.
4. **Batch DOM updates** — Wrap multi-node changes in `cy.batch(() => { ... })` to prevent re-layout thrashing.
5. **No bezier edges on dense graphs** — Use `curve-style: straight` or `taxi` for graphs > 50 edges. Bezier calculation is expensive at scale.
6. **Canvas over SVG renderer** — Cytoscape defaults to SVG; switch to canvas renderer (`renderer: { name: 'canvas' }`) for > 100 nodes. SVG degrades at ~2,000 elements; canvas sustains to 5,000.

### Minimap

Required when topology has > 15 nodes. The minimap shows:
- Viewport indicator (semi-transparent rectangle showing current view)
- All nodes as small dots (no labels at minimap scale)
- Clicking the minimap pans the main canvas to that position

Position: bottom-right, 160×100px, `bg_surface_raised` background, 8px corner radius.

### Zoom and Pan

- Zoom: `+`/`-` keys, Ctrl+scroll, pinch on touch
- Pan: Space+drag or middle-mouse drag
- Reset: `Ctrl+0` (fit all nodes to viewport)
- Zoom level displayed in toolbar: e.g., `75%`
- Zoom limits: min 15%, max 400%

---

## 4. Side Drawer / Properties Panel

The sliding properties panel is the primary editing surface. Design it to keep the canvas visible and the user in context.

### Layout

- **Position**: Right edge, slides in over the canvas (does not push/reflow)
- **Width**: 320px on ≥1280px screens; full-width on < 640px
- **Background**: `bg_surface_raised` (one elevation above canvas)
- **Border-left**: 1px `border` token
- **Open animation**: 200ms ease-out (fast appearance feels responsive)
- **Close animation**: 150ms ease-in

### Content Density

Inline label-input pairs, not stacked label-then-input. Saves ~40% vertical space:

```
Device Name    [Router-01            ]
IP Address     [192.168.1.1          ]
Device Type    [Router        ▾      ]
```

Row height: 36px. Between rows: 8px. Between sections: 16px with a subtle divider.

### Section Collapsing

Use `QExpansionItem` (Quasar). Rules:
- Collapse animation: `transform: scaleY()` (GPU-accelerated, not `max-height`)
- Easing: `cubic-bezier(0.4, 0, 0.2, 1)`, 150ms
- Expanded state: persisted per session in `nicegui_app.storage.user`
- Default: "Properties" section open, "Custom Fields" and "Connections" collapsed

### Inline Editing vs Modals

| Change type | UI pattern |
|---|---|
| Single field (name, IP, notes) | Inline — click to edit, blur/Enter to save |
| 2–4 related fields (VLAN config) | Inline group with Save/Cancel row |
| Destructive action (delete device) | Modal with explicit confirmation |
| Multi-step workflow (import, bulk edit) | Modal wizard |

**Inline auto-save**: 500ms debounce after blur. Show `Saved ✓` in the field for 1.5s. On failure, show inline error and restore previous value.

Never use a modal where inline editing works. Modal context-switch cost compounds across a session.

---

## 5. Micro-Interactions and Feedback

### Timing Reference

| Duration | Context |
|---|---|
| < 100ms | Feels instant — cursor change, hover highlight |
| 100–200ms | Button state change, ripple, focus ring |
| 200–300ms | Panel slide-in, dropdown open |
| 300–500ms | Page transition, notification entry |
| > 500ms | Only for deliberate emphasis (success animation) |

### Loading States

- **< 200ms**: No loading indicator. Show it and immediately hide it looks worse than nothing.
- **200ms–1s**: Animated progress bar (thin 2px line across the top of the loading element). Not a spinner.
- **> 1s**: Skeleton screens — render the structural layout (grey placeholder shapes) before data arrives. Never show a blank white rectangle.
- **> 5s**: Show "Taking longer than expected" + cancel/retry option. Do not leave users staring at an infinite spinner.

**Canvas-specific**: When loading a topology (fetching from API), show skeleton nodes at approximate positions, then replace with real nodes when data arrives. Prevents layout jump.

### Save and Mutation Feedback

**Optimistic UI**: Update the visual immediately on user action. Revert on backend failure with an inline error.

| Outcome | Visual |
|---|---|
| Saving | Button goes grey, label becomes "Saving…" |
| Saved | Button returns to normal, inline "✓ Saved" for 1.5s |
| Failed | Inline error next to field, restore previous value |
| Conflict | Only show a modal if the server state diverged since last load |

**Double-submit prevention**: Disable mutation buttons for 300ms after first click.

### Error Feedback

Place errors where they originate — next to the field that failed, not in a banner at the top of the page. Banner errors are for whole-page failures (auth expired, server unreachable).

Error message format: **specific and actionable**.
- Bad: "Invalid input"
- Good: "Invalid CIDR notation — expected format: 192.168.1.0/24"

Required fields: Show validation on blur, not on keystroke. Keystroke validation is too noisy for technical users who type fast.

### Drag Feedback (Canvas)

- **Cursor on node hover**: `grab`
- **Cursor during drag**: `grabbing`
- **Node opacity during drag**: 70% (ghosted, shows it's in motion)
- **Drop zone highlight**: 2px dashed `accent` border on valid drop targets
- **Snap-to-grid**: Quantize final position to nearest 8px grid point on mouse-up
- **Undo availability**: Every drag is undoable with Ctrl+Z. Show "Moved Router-01" in a transient toast if undo is available.

### Toast Notifications

- Position: Bottom-right, stacked if multiple
- Duration: 3s for success/info, 6s for warnings, persistent (manual dismiss) for errors
- Max width: 320px
- Content: `[Icon] Action completed. [Optional link]`
- Never auto-dismiss an error. The user must acknowledge it.

---

## 6. NiceGUI Implementation Constraints

NiceGUI = FastAPI backend + Vue/Quasar frontend over WebSockets. Python generates component structure; JavaScript handles rendering. Know the boundary.

### What Works Natively (prefer these)

- Layout: `ui.row`, `ui.column` (flexbox)
- All Quasar components: `QDrawer`, `QExpansionItem`, `QTable`, `QInput`, `QSelect`
- TailwindCSS utility classes via `.classes()`
- Event binding: Python callbacks on `on_click`, `on_change`, `on_value_change`
- Theme: dark mode via `ui.dark_mode()` + CSS variables
- Styling: `.style()`, `.props()`, `.classes()` — use all three when needed

### What Requires `ui.run_javascript()` or `ui.add_body_html()`

- Cytoscape.js canvas (all canvas interaction)
- Leaflet.js map
- Keyboard shortcut handlers with modifier keys
- Complex drag-drop with custom visual feedback
- Clipboard access
- Custom cursor styles during interaction

**Rule for JS bridges**: Python owns state. JavaScript owns rendering. Communication is one-directional at init (Python → JS via injected data), and event-driven back (JS → Python via REST call or NiceGUI's `ui.run_javascript` return value).

Do **not** mutate Vue-managed DOM nodes from JavaScript. This breaks WebSocket binding and causes state desync. If you need to update a NiceGUI component from a JS event, use a REST endpoint or `ui.run_javascript` to call a Python-side handler.

### Critical Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| Direct DOM mutation of NiceGUI components from JS | Breaks Vue reactivity | Call Python via REST; let NiceGUI re-render |
| Hardcoded hex in JS strings | Bypasses theme engine | Pass from Python: `f"color: '{tokens.ACCENT}'"` |
| `max-height` for collapse animations | Causes layout thrash | Use `transform: scaleY()` in CSS |
| `ui.button(onClick=...)` | Not valid NiceGUI API | Use `on_click=` |
| Tailwind color classes (`bg-blue-500`) | Bypasses design system | Use `bg-[var(--accent)]` |
| Spinner for loads > 200ms | Ambiguous progress | Use skeleton screens or progress bar |
| Modals for single-field edits | Context-switch cost | Inline editing |

### Animation in NiceGUI

- Use Quasar's built-in transitions (`q-transition`) for panel show/hide — they respect Vue's render cycle.
- Custom CSS animations are safe as long as they target non-Vue-managed properties.
- Avoid `setTimeout`-based animations in JS injected via `ui.run_javascript` — they don't coordinate with NiceGUI's render cycle and can produce visual tears.

### Performance Budget

| Metric | Target |
|---|---|
| Time to interactive (topology page) | < 2s on LAN |
| Canvas render (50 nodes) | < 100ms |
| Panel slide-in | < 250ms |
| API response for device update | < 200ms (backend) |
| Table scroll frame rate | 60fps minimum |

If a component misses these targets, investigate before adding visual complexity.

---

## 7. Interaction Consistency Rules

These rules apply everywhere, without exception:

1. **Primary action = one per view.** One primary (filled accent) button per panel/page. Everything else is secondary (outlined) or tertiary (text-only).
2. **Destructive actions are spatially separated.** Delete button is never adjacent to Save. Minimum 24px separation. Destructive = red icon + text, not icon-only.
3. **Keyboard access for every action.** Tab order is logical. Enter submits forms. Escape closes panels/modals. Arrow keys navigate lists and canvas.
4. **Empty states are informative.** Never show a blank panel. Show: what this section is for + the action to populate it. Use the `story-template` empty state patterns (HT-083 style).
5. **State is always visible.** A device in error state looks different from a healthy one without requiring the user to click it. Status is ambient, not on-demand.
6. **No orphaned interactions.** Every action has an observable outcome within 200ms. If the system is processing, show it. Silent processing is a bug.
