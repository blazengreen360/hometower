# Hometower — Component Inventory

> **Cross-references:** [themes.md](themes.md) for token values · [pages.md](pages.md) for usage context · [interactions.md](interactions.md) for animation specs

All components are implemented using NiceGUI unless noted otherwise. Design tokens reference [themes.md](themes.md).

---

## 1. Button

**NiceGUI widget:** `ui.button`

### Variants

| Variant | Use case | Background | Border | Text |
|---|---|---|---|---|
| **Primary** | Main CTA (Sign In, Save) | `--color-primary` | None | `#ffffff` |
| **Secondary** | Alternative actions (Cancel, Export) | Transparent | `1px solid var(--color-primary)` | `--color-primary` |
| **Ghost** | Low-emphasis actions (Clear, Dismiss) | Transparent | None | `--color-text-muted` |
| **Destructive** | Irreversible actions (Delete) | Transparent | `1px solid var(--color-error)` | `--color-error` |

### States

| State | Visual change |
|---|---|
| Default | As described above |
| Hover | Primary: `background: var(--color-primary-dark)` · Others: 10% background tint |
| Active/Pressed | `transform: scale(0.97)`, `opacity: 0.85` |
| Disabled | `opacity: 0.4`, `cursor: not-allowed` |
| Focus | `outline: 2px solid var(--color-primary)`, `outline-offset: 2px` |
| Loading | Spinner icon replaces label; button disabled |

### Sizing

| Size | Height | Padding H | Font size |
|---|---|---|---|
| Small | 32px | 12px | `var(--font-sm)` |
| Default | 40px | 16px | `var(--font-md)` |
| Large | 48px | 20px | `var(--font-md)` |

**Touch target:** All buttons ≥ 44×44px on mobile (size is inflated by padding extension if needed).

### NiceGUI Notes

```python
ui.button("Save", on_click=handle_save).props("color=primary")
# Destructive:
ui.button("Delete", on_click=handle_delete).props("flat color=negative")
# Loading state:
btn = ui.button("Save")
btn.props("loading")  # shows spinner
```

Icon-only buttons must include `aria-label`:
```python
ui.button(icon="delete").props('aria-label="Delete device"')
```

---

## 2. Card

**NiceGUI widget:** `ui.card`

### Variants

| Variant | Use case |
|---|---|
| **Stat card** | Dashboard metrics (device count, etc.) |
| **Content card** | Settings sections, form containers |
| **Action card** | Clickable card linking to a route |

### Anatomy

```
┌─────────────────────────────────────────────┐
│  [optional header slot]                     │
│  ─────────────────────────────────────────  │
│  [body slot]                                │
│                                             │
│  [optional footer slot: action buttons]     │
└─────────────────────────────────────────────┘
```

### Tokens

| Token | Value |
|---|---|
| Background | `var(--color-surface-alt)` |
| Border-radius | `var(--radius-card)` = 8px |
| Border | `1px solid var(--color-border)` |
| Padding | `var(--spacing-md) var(--spacing-lg)` |
| Box-shadow | `var(--shadow-card)` |

**Hover state (Action card only):**
- `box-shadow: var(--shadow-card-hover)`
- `transform: translateY(-2px)`
- `transition: box-shadow 150ms ease, transform 150ms ease`

### NiceGUI Notes

```python
with ui.card().style("background: var(--color-surface-alt); border-radius: 8px"):
    ui.label("Title").classes("text-lg font-bold")
    # ... content
```

---

## 3. Input

### Variants

| Variant | NiceGUI widget | Use case |
|---|---|---|
| **Text input** | `ui.input` | Name, IP, email |
| **Password input** | `ui.input(password=True, password_toggle_button=True)` | Login, user creation |
| **Select / Dropdown** | `ui.select` | Device type, role, location |
| **Toggle / Switch** | `ui.switch` | Enable/disable settings |
| **Textarea** | `ui.textarea` | Notes, long-form input |

### States

| State | Visual |
|---|---|
| Default | Underline or outline border `var(--color-border)` |
| Focus | Border/underline: `var(--color-primary)`, floating label rises |
| Error | Border/underline: `var(--color-error)`, error message below field |
| Disabled | `opacity: 0.5`, `cursor: not-allowed` |
| Valid | Border returns to default (no green — avoid relying on color alone) |

### Validation

- Inline validation: error message appears **immediately on blur** (not on form submit)
- Error message position: below the field, `font-size: var(--font-sm)`, `color: var(--color-error)`
- Required fields: asterisk `*` in the label
- Save/Submit button stays disabled until form is dirty **and** all required fields are valid

### NiceGUI Notes

```python
ip_input = ui.input("IP Address *", placeholder="192.168.1.10")
    .props('autocomplete="off" spellcheck="false"')
    .style("font-family: var(--font-mono)")

# Error display
error_label = ui.label("").style("color: var(--color-error); font-size: 0.875rem")

def on_blur():
    if not validate_ip(ip_input.value):
        error_label.set_text("Invalid IP address format")

ip_input.on("blur", on_blur)
```

---

## 4. Table

**NiceGUI widget:** `ui.table`

### Anatomy

```
┌────────────────────────────────────────────────────────────────────┐
│  [sort icon] Column A  │ Column B │ Column C  │ Column D │ Actions  │  ← header row, 40px, sticky
├────────────────────────────────────────────────────────────────────┤
│  [content]             │ [content]│ [content] │ [content]│ ✎ 🗑     │  ← data row, 48px
├────────────────────────────────────────────────────────────────────┤
│  …                                                                 │
└────────────────────────────────────────────────────────────────────┘
```

### Tokens

| Property | Value |
|---|---|
| Header row height | 40px |
| Header font | `font-size: var(--font-sm)`, weight 600, uppercase, muted |
| Data row height | 48px |
| Row hover bg | `var(--color-nav-hover-bg)` |
| Row selected bg | `var(--color-nav-active-bg)` |
| Cell padding | `0 var(--spacing-md)` |
| Border (between rows) | `1px solid var(--color-border)` |

### Sort Indicator

Sortable columns show an `unfold_more` icon by default. Active sort shows `arrow_upward` or `arrow_downward`. Icon size: 16px, inline with column label.

### Action Buttons in Rows

Edit (✎) and Delete (🗑) icons are 32×32px ghost buttons. Shown in an `Actions` column. On mobile they are hidden and accessible via row long-press or swipe gesture (future).

### Empty State (in table)

Spans full table width, centered:
```
[No matching icon, 32px]
"No results found"
[optional sub-text]
```

### NiceGUI Notes

```python
columns = [
    {"name": "type", "label": "Type", "field": "type", "sortable": True},
    {"name": "name", "label": "Name", "field": "name", "sortable": True},
    # ...
]
table = ui.table(columns=columns, rows=rows, row_key="id")
    .classes("w-full")
    .style("background: transparent")
```

---

## 5. Badge / Chip

Used for device types, tags, roles, and status indicators.

### Variants

| Variant | Shape | Color source | Usage |
|---|---|---|---|
| **Device type badge** | Pill (border-radius: 12px) | `DEVICE_TYPE_COLORS[type]` from tokens.py | Inventory table, detail panel |
| **Tag chip** | Pill | User-defined `Tag.color` | Device cards, filter bar |
| **Status badge** | Dot + label | Semantic tokens (success/warning/error) | Future device status |
| **Role badge** | Pill | Semantic (primary/success/muted) | User table |
| **"Soon" badge** | Small pill | `var(--color-warning-bg)` | Map nav item |

### Anatomy (Device type badge)

```
┌───────────────────┐
│ [icon 14px] Server │  height: 24px, padding: 0 8px, font-size: var(--font-xs)
└───────────────────┘
```

Colors for device types (from `tokens.py DEVICE_TYPE_COLORS`):

| Type | Color |
|---|---|
| Server | `#6366f1` |
| Switch | `#22d3ee` |
| Router | `#f59e0b` |
| NAS | `#10b981` |
| UPS | `#f97316` |
| SBC | `#8b5cf6` |
| Workstation | `#3b82f6` |
| VM | `#a78bfa` |
| LXC | `#34d399` |
| Docker | `#60a5fa` |
| Application | `#fb7185` |
| VLAN | `#fbbf24` |
| Subnet | `#e879f9` |

### Overflow Handling (Tags)

When more than 3 tags exist, show 3 chips + a muted "+N more" chip. Hovering "+N more" shows a tooltip listing all tags.

---

## 6. Sidebar NavItem

**NiceGUI implementation:** Custom `ui.element('div')` with click handler.

See [app-shell.md § 3.3](app-shell.md) for full anatomy.

### States

| State | Visual |
|---|---|
| Default | Icon: `--color-nav-icon`, no background |
| Hover | Background: `--color-nav-hover-bg` |
| Active (current page) | Left border 3px `--color-primary`, bg: `--color-nav-active-bg`, icon: `--color-nav-icon-active` |
| Focus | `outline: 2px solid var(--color-primary)` inside the item |
| Disabled | `opacity: 0.4`, not clickable (used for "Soon" items — clicking shows coming-soon toast) |

### Accessibility

```python
nav_item.props('role="link" tabindex="0"')
nav_item.props(f'aria-label="{page_name}" aria-current="page"')  # aria-current only on active
```

---

## 7. Header UserMenu

**NiceGUI widget:** `ui.button` wrapping with a `ui.menu` dropdown.

### Avatar Chip

```
┌───────────────────┐
│  JA  ▸  Admin ▾  │  initials + role label + chevron
└───────────────────┘
```

- Initials: first letter of username, uppercase, `font-weight: 700`
- Background: `--color-primary` for Admin, `--color-success` for Contributor, `--color-surface-alt` for Reader
- Dropdown: 200px wide, right-aligned to the chip

### Dropdown Items

1. Display name (bold) + email (muted) — not clickable, acts as user info header
2. Separator
3. "Keyboard Shortcuts" → opens shortcut overlay (`?` key equivalent)
4. Separator
5. "Sign out" — `color: var(--color-error)`

### NiceGUI Notes

```python
with ui.button().props("flat"):
    ui.label(initials)
    with ui.menu():
        ui.menu_item("Sign out", on_click=handle_logout)
            .style("color: var(--color-error)")
```

---

## 8. Breadcrumb

**NiceGUI widget:** `ui.row` + `ui.label` + separator icons

### Anatomy

```
Settings  ›  Locations
```

- Separator: `chevron_right` icon, 16px, muted
- All segments except the last are clickable links
- Last segment: bold, normal text (current page)
- Font: `var(--font-sm)`

### NiceGUI Notes

```python
with ui.row().classes("items-center gap-1"):
    ui.link("Settings", "/settings/locations").style("color: var(--color-text-muted)")
    ui.icon("chevron_right").style("color: var(--color-text-muted); font-size: 16px")
    ui.label("Locations").classes("font-semibold")
```

---

## 9. Toast / Notification

**NiceGUI widget:** `ui.notify` (wrapped by `src/ui/components/toast.py`)

### API

```python
from src.ui.components.toast import show_toast

show_toast(type="success", title="Device saved", description="pihole updated")
show_toast(type="error",   title="Save failed",  description="Connection refused")
show_toast(type="warning", title="Unsaved changes")
show_toast(type="info",    title="Copied",        duration_ms=2000)
```

### Visual Spec

| Type | Icon | Accent color | Duration |
|---|---|---|---|
| Success | `check_circle` | `--color-success` | 4000ms |
| Error | `error` | `--color-error` | 6000ms (user must dismiss or wait) |
| Warning | `warning` | `--color-warning` | 5000ms |
| Info | `info` | `--color-primary` | 3000ms |

- Position: top-right
- Dismiss: manual × button always shown
- Max-width: 360px
- Multi-line: title bold, description muted below
- Animation: slide in from right (`transform: translateX(0)` from `translateX(100%)`, 200ms ease-out)
- Exit: slide out to right, 150ms
- `aria-live="polite"` region for screen readers (error uses `aria-live="assertive"`)
- Stack: up to 3 toasts visible; oldest dismissed first when 4th appears

---

## 10. Tooltip

**NiceGUI widget:** `ui.tooltip` (as child of target element)

### Spec

- Background: `rgba(30, 30, 46, 0.95)` (dark) / `rgba(255, 255, 255, 0.95)` (light) with border
- Font: `var(--font-sm)`, `--color-text`
- Padding: `4px 8px`
- Border-radius: 4px
- Max-width: 200px
- Delay: 600ms hover delay before show (prevents flickering on cursor pass-through)
- Animation: fade in 100ms
- Position: above target by default, flips if no space

### Usage in Sidebar (collapsed mode)

Tooltip shows full page name when hovering an icon-only NavItem. Position: right side of sidebar, 8px offset.

```python
with ui.element("div"):  # NavItem
    ui.icon("dns")
    ui.tooltip("Dashboard")
```

---

## 11. Modal / Dialog

**NiceGUI widget:** `ui.dialog`

### Spec

- Backdrop: `rgba(0, 0, 0, 0.6)`, `backdrop-filter: blur(2px)`
- Dialog container: `background: var(--color-surface-alt)`, `border-radius: var(--radius-card)`, `padding: var(--spacing-lg)`
- Width: 480px default, 600px for complex forms, 360px for confirmations
- Z-index: 30 (above sticky header)
- Animation: scale from 0.95 → 1.0 + fade in, 150ms ease-out

### Anatomy

```
┌─────────────────────────────────────────────┐
│  Modal Title                     ×          │  ← header: title left, close right
│  ─────────────────────────────────────────  │
│                                             │
│  [content slot — form fields / message]     │
│                                             │
│  ─────────────────────────────────────────  │
│                       [ Cancel ] [ Save ]   │  ← footer: actions right-aligned
└─────────────────────────────────────────────┘
```

- Close (×): icon button, top-right, `aria-label="Close dialog"`
- Escape key closes modal
- Focus trap: Tab cycles only within modal while open
- Initial focus: first interactive element in content slot
- Confirmation modals (delete): two-button only, no form fields. Delete button is Destructive variant.

### NiceGUI Notes

```python
with ui.dialog() as dialog, ui.card():
    ui.label("Add Location").classes("text-lg font-bold")
    # ... form fields ...
    with ui.row().classes("w-full justify-end gap-2 mt-4"):
        ui.button("Cancel", on_click=dialog.close)
        ui.button("Save", on_click=handle_save).props("color=primary")
```

---

## 12. Empty State

Used when a page, table, or section has no data.

### Variants

| Context | Icon | Primary text | Secondary text | CTA |
|---|---|---|---|---|
| Canvas (no devices) | `device_hub` | "Start building your topology" | "Drag a device from the palette, or click +" | "+ Add Device" |
| Inventory (no devices) | `dns` | "No devices yet" | "Add your first device to start your inventory" | "+ Add Device" |
| Inventory (after filter) | `filter_none` | "No devices match your filters" | — | "Clear Filters" |
| Map placeholder | `map` | "Map View — Coming Soon" | "Devices with coordinates will appear here" | "View Inventory" |
| Dashboard (zero devices) | `dns` | "No devices in your inventory yet" | "Add your first device to start building your topology" | "+ Add Your First Device" |

### Anatomy

```
┌──────────────────────────────────────────────┐
│                                              │
│     [icon: 48–64px, --color-text-muted]      │
│                                              │
│     Primary text (--color-text, font-lg)     │
│     Secondary text (--color-text-muted, sm)  │
│                                              │
│          [ CTA Button ]                      │
│                                              │
└──────────────────────────────────────────────┘
```

- Centered in its container
- Vertical padding: `var(--spacing-xl)` above and below
- Icon color: `--color-text-muted` (never use a distracting color for empty states)
- No illustration images — icon-only to keep things minimal and maintainable
