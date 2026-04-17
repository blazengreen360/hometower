# Hometower — App Shell Specification

> **Cross-references:** [site-map.md](site-map.md) for routes · [components.md](components.md) for NavItem, Header, UserMenu, Breadcrumb · [themes.md](themes.md) for token values

---

## 1. Shell Overview

The app shell is the persistent UI frame that wraps all authenticated pages. It consists of three regions:

```
┌──────────────────────────────────────────────────────────────┐
│  HEADER  (full width, 56px tall)                             │
├───────────┬──────────────────────────────────────────────────┤
│           │                                                  │
│  SIDEBAR  │          CONTENT AREA                           │
│  240px    │          (flex 1, scrollable)                   │
│  expanded │                                                  │
│           │                                                  │
└───────────┴──────────────────────────────────────────────────┘
```

The Login and Access Denied pages render **outside** the shell (no sidebar, no header).

---

## 2. Header

### 2.1 Dimensions

| Property | Value |
|---|---|
| Height | 56px |
| Width | 100vw (full) |
| Position | `sticky top: 0` |
| Z-index | 20 (above content, below modals) |

### 2.2 Layout (left → right)

```
[ ≡ Collapse btn ] [ 🏠 Hometower logo + wordmark ] [ Breadcrumb ]  ──────────  [ Search ] [ User Menu ▾ ]
   44×44px           32px icon + text                 only on settings pages             48px icon btn
```

- **Collapse button:** 44×44px, icon `menu` (hamburger) when expanded, `menu_open` when collapsed. Toggles sidebar. Accessible: `aria-label="Toggle sidebar"`.
- **Logo:** Material icon `home` (32px, color: `--color-primary`) + wordmark "Hometower" in `font-size: var(--font-lg)`, `font-weight: 700`. Clicking navigates to `/`.
- **Breadcrumb:** Only rendered on `/settings/*` pages. See [components.md § Breadcrumb](components.md).
- **Search:** Icon button, `search` icon, 44×44px. Opens a full-width search bar inline or a command palette overlay (future HT feature). For now, reserved space.
- **User Menu:** Avatar chip (initials + role badge) + chevron-down. Dropdown on click. See § 2.3.

### 2.3 User Menu Dropdown

```
┌─────────────────────┐
│ ● John Admin        │  ← display name, role badge
│   admin@example.com │  ← email, muted
├─────────────────────┤
│   Profile           │  ← future
│   Keyboard Shortcuts│  ← opens shortcut overlay
├─────────────────────┤
│   Sign out          │  ← destructive item (color: --color-error)
└─────────────────────┘
```

- Min-width: 200px
- Z-index: 30 (above sticky header)
- Keyboard: `Escape` closes; arrow keys navigate items; `Enter` selects
- Accessible: `aria-expanded`, `aria-haspopup="menu"`, items use `role="menuitem"`

### 2.4 Header Colour Tokens

| Token | Purpose | Dark "Control Room" | Light "Blueprint" |
|---|---|---|---|
| `--color-header-bg` | Background | `#12121e` | `#ffffff` |
| `--color-header-border` | Bottom border | `#2a2a3e` | `#e2e8f0` |
| `--color-header-text` | Primary text | `#cdd6f4` | `#1e293b` |

---

## 3. Sidebar

### 3.1 Dimensions

| State | Width | Transition |
|---|---|---|
| Expanded | 240px | `width 200ms ease-out` |
| Collapsed (icon-only) | 64px | `width 200ms ease-out` |
| Mobile (< 768px) | 0px (hidden, full off-screen) | slide in as overlay |

### 3.2 Structure

```
┌────────────────────────┐
│  ← HEADER ALIGNS HERE  │   (56px reserved gap — sidebar starts below header)
├────────────────────────┤
│  Primary Nav           │
│  ─────────────────     │
│  [icon] Dashboard      │   48px row height
│  [icon] Topology       │
│  [icon] Inventory      │
│  [icon] Map  [Soon]    │
│                        │
│  ────── SETTINGS ──    │   ← group divider (Admin only)
│  [icon] Locations      │
│  [icon] Users          │
│  [icon] Data           │
│                        │
│  ← flex-grow spacer →  │
│                        │
├────────────────────────┤
│  [icon] Version vX.Y   │   ← footer, muted text
└────────────────────────┘
```

### 3.3 NavItem Anatomy

Each navigation row is 48px tall. Horizontal padding: 12px (collapsed) / 16px (expanded).

```
╔════════════════════╗  ← active state: 3px left border (color: --color-primary)
║ ▐ [icon 20px] Label║     background: --color-nav-active-bg
╚════════════════════╝

Default: no border, background: transparent
Hover:   background: --color-nav-hover-bg (subtle tint)
```

| Property | Value |
|---|---|
| Icon size | 20×20px (Material Icons) |
| Icon-to-label gap | 12px |
| Label font | `var(--font-sm)`, weight 500 |
| Active indicator | 3px left border, color `--color-primary` |
| Active bg | `rgba(79, 70, 229, 0.12)` |
| Hover bg | `rgba(255, 255, 255, 0.05)` |
| Transition | `background 150ms ease` |
| Border-radius | 6px (right edge only, `border-radius: 0 6px 6px 0`) |

### 3.4 Collapsed Mode Behaviour

- Labels hidden, icons centred
- Hovering a NavItem shows a tooltip (right side, 8px offset) with the page name
- Tooltip uses [components.md § Tooltip](components.md)
- Collapse/expand button still visible at top

### 3.5 Group Divider

```css
/* SETTINGS separator */
font-size: var(--font-xs);   /* 0.7rem */
font-weight: 600;
letter-spacing: 0.08em;
text-transform: uppercase;
color: var(--color-text-muted);
padding: 8px 16px 4px;
margin-top: 8px;
```

In collapsed mode the divider label is hidden; a simple horizontal rule remains (1px, muted).

### 3.6 Mobile Overlay Behaviour (< 768px)

- Sidebar is offscreen (`transform: translateX(-240px)`) by default
- Toggle button in header slides it in with `transform: translateX(0)`, `z-index: 40`
- Semi-transparent backdrop (`rgba(0,0,0,0.5)`) behind the sidebar; clicking backdrop closes sidebar
- Animation: `transform 250ms ease-out`

### 3.7 Sidebar Colour Tokens

| Token | Purpose | Dark "Control Room" |
|---|---|---|
| `--color-sidebar-bg` | Background | `#12121e` |
| `--color-sidebar-border` | Right border | `#2a2a3e` |
| `--color-nav-active-bg` | Active item bg | `rgba(79, 70, 229, 0.12)` |
| `--color-nav-hover-bg` | Hover item bg | `rgba(255, 255, 255, 0.05)` |
| `--color-nav-icon` | Icon colour | `#a6adc8` |
| `--color-nav-icon-active` | Active icon | `#4f46e5` |

---

## 4. Content Area

### 4.1 Layout Behaviour

| Breakpoint | Content area padding | Max content width |
|---|---|---|
| Desktop (≥ 1024px) | `24px 32px` | Unconstrained (full) |
| Tablet (768–1023px) | `16px 20px` | Unconstrained |
| Mobile (< 768px) | `12px 16px` | Unconstrained |

The content area occupies `flex: 1` horizontally and `100%` of viewport height minus 56px header (overflow: auto for scrollable content).

Pages that use the full viewport (Topology) set `overflow: hidden` on the content area and manage their own internal scroll/pan.

### 4.2 Background Tokens

| Token | Dark "Control Room" | Light "Blueprint" |
|---|---|---|
| `--color-page-bg` | `#1a1a2e` | `#f1f5f9` |
| `--color-surface` | `#1e1e2e` | `#ffffff` |
| `--color-surface-alt` | `#27273a` | `#f8fafc` |

---

## 5. Responsive Breakpoints

| Name | Range | Sidebar | Header | Content changes |
|---|---|---|---|---|
| Mobile | < 768px | Hidden (overlay on toggle) | Collapse btn visible | Canvas touches, stat cards 1-col |
| Tablet | 768–1023px | Collapsed (icon-only, 64px) | Full | Stat cards 2-col, split panes available |
| Desktop | ≥ 1024px | Expanded (240px) | Full | Stat cards 4-col, three-panel topology |

---

## 6. ARIA Landmark Regions

The shell must define these ARIA landmarks for screen reader navigation:

```html
<header role="banner">          <!-- header strip -->
<nav role="navigation">         <!-- sidebar -->
<main role="main">              <!-- content area -->
```

The sidebar nav list uses `role="navigation"` with `aria-label="Main navigation"`. The settings sub-group uses `aria-label="Settings navigation"`.

---

## 7. Focus Management

- **Tab order:** Collapse button → Logo → Breadcrumb (if present) → Search → UserMenu → Sidebar NavItems (top to bottom) → Page content
- **Focus ring:** `outline: 2px solid var(--color-primary)` with `outline-offset: 2px` on all interactive elements
- No `:focus-visible` suppression — focus rings always visible for keyboard users
