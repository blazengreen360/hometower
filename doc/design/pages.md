# Hometower — Page Wireframe Specifications

> **Cross-references:** [site-map.md](site-map.md) for routes · [app-shell.md](app-shell.md) for shell · [components.md](components.md) for components · [interactions.md](interactions.md) for interaction patterns

---

## 1. Login (`/login`)

The Login page renders **outside the app shell** — no sidebar, no header.

### 1.1 Wire Layout

```
┌────────────────────────────────────────────────────────────┐
│                  bg: --color-page-bg (full screen)         │
│                                                            │
│          ┌─────────────────────────────┐                  │
│          │  ░ Hometower Logo            │  360px card      │
│          │  🏠  Hometower              │  centered        │
│          │  ─────────────────────────  │  horizontally    │
│          │  Email ____________________  │  and             │
│          │  Password _________________  │  vertically      │
│          │                              │                  │
│          │  [ error label (hidden)  ]   │                  │
│          │  [ Sign In ]  (primary btn)  │                  │
│          └─────────────────────────────┘                  │
└────────────────────────────────────────────────────────────┘
```

### 1.2 States

| State | Description |
|---|---|
| Default | Empty form, error label hidden, Sign In enabled |
| Loading | Button shows spinner, fields disabled |
| Error | Error label shows "Invalid email or password" in `--color-error` |
| Success | Redirect to `/` |

### 1.3 Design Notes

- Card: 360px wide, `padding: var(--spacing-lg)`, `border-radius: var(--radius-card)`, `background: var(--color-surface-alt)`, `box-shadow: var(--shadow-card)`
- App name in `--color-primary`, `font-size: var(--font-xl)`, `font-weight: 700`, centered
- Form fields use `ui.input` with floating labels
- Sign In button: full-width primary button (see [components.md § Button](components.md))
- Error label: `min-height: 1.25rem` to prevent layout jump when it appears
- `autocomplete="email"` and `autocomplete="current-password"` on respective inputs
- Enter key on password field submits the form
- No registration link — admin-provisioned users only

### 1.4 Accessibility

- `<form>` element with `aria-label="Login"`
- Submit on Enter (both fields)
- Error label uses `role="alert"` so screen readers announce it immediately
- Focus starts on the email field on page load

---

## 2. Dashboard (`/`)

New page (HT-026). Central landing after login.

### 2.1 Wire Layout

```
┌─── SHELL HEADER (56px) ──────────────────────────────────────────┐
├─── SIDEBAR ────┬─── CONTENT AREA ─────────────────────────────────┤
│                │  Dashboard                      [+ Add Device]  │
│   primary nav  │  ─────────────────────────────────────────────  │
│                │                                                  │
│                │  ┌────┐ ┌────┐ ┌────┐ ┌────┐                  │
│                │  │ D  │ │ C  │ │ L  │ │ T  │   ← stat cards   │
│                │  │    │ │    │ │    │ │    │     4-col desktop │
│                │  └────┘ └────┘ └────┘ └────┘                  │
│                │                                                  │
│                │  Recent Activity             Quick Actions      │
│                │  ─────────────────────       ───────────────   │
│                │  [device icon] event…  time  [ Topology      ] │
│                │  [device icon] event…  time  [ Inventory     ] │
│                │  [device icon] event…  time  [ + Add Device  ] │
│                │  [device icon] event…  time                    │
└────────────────┴──────────────────────────────────────────────────┘
```

### 2.2 Stat Cards

| Card | Icon | Metric | Link |
|---|---|---|---|
| **Devices** | `dns` | Total device count | `/inventory` |
| **Connections** | `cable` | Total connection count | `/topology` |
| **Locations** | `location_on` | Total location count | `/settings/locations` |
| **Device Types** | `category` | Count of distinct types in use | `/inventory` |

**Card anatomy (48px × full-width of grid cell):**

```
┌─────────────────────────────────┐
│ [icon 24px]          [number]  │  ← icon left, stat right (large: var(--font-2xl))
│              [label text]       │  ← smaller label below number, --color-text-muted
└─────────────────────────────────┘
```

- Card: `background: var(--color-surface-alt)`, `border-radius: var(--radius-card)`, `padding: var(--spacing-md) var(--spacing-lg)`
- Icon: `color: var(--color-primary)`, left-aligned
- Number: `font-size: var(--font-2xl)`, `font-weight: 700`, right of icon
- Label: `font-size: var(--font-sm)`, `color: var(--color-text-muted)`, below number
- Hover: `box-shadow: var(--shadow-card-hover)`, `transform: translateY(-2px)`, `transition: 150ms ease`
- Click navigates to the linked route

**Grid breakpoints:**

| Breakpoint | Columns |
|---|---|
| Mobile (< 768px) | 1 |
| Tablet (768–1023px) | 2 |
| Desktop (≥ 1024px) | 4 |

### 2.3 Recent Activity List

- Shows last 10 device create/update events (chronological, newest first)
- Each row: device type icon · device name (bold) · action ("created" / "updated") · relative timestamp (right-aligned, muted)
- Row height: 40px
- Separator: 1px `var(--color-border)` between rows
- Clicking a row navigates to `/inventory` (filtered by device name — future enhancement)

### 2.4 Quick Actions

Vertical stack of secondary buttons:
- "Open Topology" → `/topology`
- "View Inventory" → `/inventory`
- "+ Add Device" → opens Add Device modal (future)

### 2.5 Empty State (zero devices)

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│              [dns icon, 64px, --color-text-muted]            │
│          No devices in your inventory yet.                   │
│   Add your first device to start building your topology.     │
│                                                              │
│              [ + Add Your First Device ]                     │
└──────────────────────────────────────────────────────────────┘
```

Replaces the stat cards + activity list when the device count is 0.

---

## 3. Topology (`/topology`)

### 3.1 Wire Layout

Three-panel layout fills the content area entirely (no internal scroll).

```
┌─── SHELL HEADER (56px) ──────────────────────────────────────────────┐
├──── SIDEBAR ──┬──PALETTE ──┬──── CANVAS ──────────┬── DETAIL PANEL ──┤
│               │  160px     │  flex: 1              │  0px (hidden)    │
│  primary nav  │  ─────────  │  (Cytoscape.js)       │  OR 320px  open  │
│               │  Devices   │                        │  slides in       │
│               │  ─────────  │  [empty: "Drag a      │  from right      │
│               │  [Server]  │  device from the       │                  │
│               │  [Switch]  │  palette to begin"]    │                  │
│               │  [Router]  │                        │                  │
│               │  …         │  ┌──layout bar──────┐  │                  │
│               │            │  │ [grid][dagre][…] │  │                  │
│               │            │  └──────────────────┘  │                  │
└───────────────┴────────────┴──────────────────────────┴──────────────────┘
```

### 3.2 Panel Dimensions

| Panel | Width | Notes |
|---|---|---|
| Device palette | 160px fixed | Scrollable vertically if many types |
| Canvas | `flex: 1` | Cytoscape.js fills this area, `overflow: hidden` |
| Detail panel | 0px (closed) / 320px (open) | Slides in from right, canvas does NOT shrink |
| Layout bar | Fixed at canvas bottom | 40px tall toolbar strip |

The detail panel overlaps the canvas at smaller viewports rather than pushing it. At desktop widths (≥ 1024px), canvas simply remains `flex: 1` and the panel sits alongside.

### 3.3 Canvas Empty State

```
[Centered on canvas background]
   [device_hub icon, 48px, muted]
   "Start building your topology"
   "Drag a device type from the left panel, or click +"
   [ + Add Device ]  (secondary button)
```

### 3.4 Detail Panel Tabs

When a node is selected:
- **Device tab:** Identity (name, type, IP, MAC, OS), Location, Tags, Custom Fields, Notes
- **Connections tab:** List of connections to/from this device

When an edge is selected:
- Connection detail panel (single-tab): source → target, connection type, label

See [interactions.md § Panel Switching](interactions.md).

### 3.5 Layout Bar

Fixed strip at canvas bottom (inside canvas area). Contains algorithm buttons from `topology_layout_bar.py`. Buttons are 36px tall icon+label chips.

### 3.6 Read-Only Mode

If the user role is Reader, the palette is hidden and canvas interaction is limited to pan/zoom/click. Node editing is disabled. Visual indicator: header shows `[Read Only]` badge next to page title.

### 3.7 Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| Mobile (< 768px) | Palette hidden (swipe-up drawer); detail panel full-screen when open |
| Tablet (768–1023px) | Palette collapsible (toggle button); detail panel overlaps canvas |
| Desktop (≥ 1024px) | Three panels visible simultaneously |

---

## 4. Inventory (`/inventory`)

### 4.1 Wire Layout

```
┌─── SHELL HEADER (56px) ──────────────────────────────────────────┐
├──── SIDEBAR ─────┬──── CONTENT AREA ────────────────────────────┤
│                  │  Inventory                    [ + Add Device ]│
│   primary nav    │  ────────────────────────────────────────────│
│                  │  [Filter bar: type chips + tag chips + search]│
│                  │                                               │
│                  │  ┌──────────────────────────────────────────┐│
│                  │  │ ⬜ │ Type │ Name  │ IP  │ Loc │Tags│Upd  ││
│                  │  ├──────────────────────────────────────────┤│
│                  │  │ 🖥️  │Server│pihole │10…  │Rack1│…  │2h   ││
│                  │  │ 🔀  │Switch│sw-01  │10…  │Rack1│…  │5d   ││
│                  │  │ …   │      │       │     │    │   │     ││
│                  │  └──────────────────────────────────────────┘│
│                  │  Showing 25 of 47 devices   [← 1  2  3 →]   │
└──────────────────┴───────────────────────────────────────────────┘
```

### 4.2 Filter Bar

Positioned above the table. Horizontal scroll if chips overflow.

```
[ All Types ▾ ] [Server ×] [Switch ×] [Router ×]   [Tag: homelab ×]   [🔍 Search…        ]
```

- Type filter chips: multi-select, active chips show device-type color + × remove button
- Tag filter chips: same pattern, user-defined tag highlight colors
- Search: real-time text filter (≥ 1 character triggers filter), searches name + IP + MAC
- "Clear All" link appears when any filter is active (right side of bar)

### 4.3 Table Columns

| Column | Width | Content | Sortable |
|---|---|---|---|
| Type icon | 40px | Colored icon chip (no label) | No |
| Type | 100px | Device type text badge | Yes |
| Name | flex: 1 | Plain text, bold | Yes |
| IP Address | 130px | Monospace font | Yes |
| Location | 120px | Location name or "—" | Yes |
| Tags | 140px | Up to 3 tag chips + "+N more" | No |
| Updated | 80px | Relative time (e.g. "2h ago") | Yes |

- Row height: 48px
- Selected row: `background: var(--color-nav-active-bg)`
- Hover row: `background: var(--color-nav-hover-bg)`
- Clicking a row: navigates to device detail (future: inline expand)
- IP + MAC values in monospace font with copy-to-clipboard icon on hover

### 4.4 Pagination

Below the table, right-aligned:

```
Showing 1–25 of 47 devices       [ ← Prev ]  [ 1 ]  [ 2 ]  [ 3 ]  [ Next → ]
```

Page size: 25 devices per page (default). No page size selector in v1.

### 4.5 Empty State (after filter)

```
[filter_none icon, 40px, muted]
"No devices match your filters."
[ Clear Filters ]  (secondary button)
```

### 4.6 Responsive Table Behaviour

| Breakpoint | Behaviour |
|---|---|
| Mobile (< 768px) | Table scrolls horizontally; Type, IP, Tags columns hidden; only icon, Name, Updated visible |
| Tablet (768–1023px) | Tags column hidden; remaining columns visible in horizontal scroll |
| Desktop (≥ 1024px) | All columns visible |

---

## 5. Map (`/map`) — Placeholder

### 5.1 Placeholder State

Page is reserved for HT-008. It renders inside the shell with:

```
[map icon, 64px, --color-text-muted]
"Map View — Coming Soon"
"Devices with GPS coordinates will appear here as an interactive map."
[ View Inventory Instead ]  (secondary button → /inventory)
```

- No Leaflet.js loaded on this placeholder page
- Nav badge on sidebar NavItem: `"Soon"` chip in `--color-warning` background

---

## 6. Settings: Locations (`/settings/locations`)

### 6.1 Wire Layout

```
┌──── CONTENT AREA ──────────────────────────────────────────────┐
│  Settings › Locations                       [ + Add Location ] │
│  ──────────────────────────────────────────────────────────    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Name          │  Type   │  Devices  │  Parent   │  ✎ 🗑  │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  Rack-01       │  rack   │  12       │  —        │  ✎ 🗑  │ │
│  │  Server Room A │  geo    │  0        │  —        │  ✎ 🗑  │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 6.2 Add / Edit Location Modal

Fields: Name (required), Type (rack | geo), Lat / Lng (only shown if Type = geo), Rack/Row (only shown if Type = rack), Parent Location (dropdown).

Cancel + Save buttons: right-aligned. Save disabled until form is valid and dirty. See [components.md § Modal](components.md).

---

## 7. Settings: Users (`/settings/users`)

### 7.1 Wire Layout

```
┌──── CONTENT AREA ──────────────────────────────────────────────┐
│  Settings › Users                              [ + Add User ]  │
│  ──────────────────────────────────────────────────────────    │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Username        │  Email           │  Role    │  ✎ 🗑  │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  admin           │  admin@home…     │  Admin   │  ✎ 🗑  │ │
│  │  alice           │  alice@home…     │  Contrib  │  ✎ 🗑  │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 Role Badge

- Admin: `--color-primary` chip
- Contributor: `--color-success` chip
- Reader: `--color-text-muted` chip

### 7.3 Add / Edit User Modal

Fields: Username (required), Email (required), Password (required for new; optional for edit — blank = no change), Role (select). Password field has show/hide toggle.

Delete: shows confirmation modal "Delete user alice? This cannot be undone." with Cancel + Delete (destructive) buttons.

---

## 8. Settings: Data (`/settings/data`)

### 8.1 Wire Layout

```
┌──── CONTENT AREA ──────────────────────────────────────────────┐
│  Settings › Data                                               │
│  ──────────────────────────────────────────────────────────    │
│  Export                                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  [ Export JSON ]  [ Export CSV ]                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Import                                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Drag & drop a JSON file, or  [ Browse… ]               │   │
│  │  ⚠ Importing will merge with existing data.             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Danger Zone                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  [ Delete All Devices ]   (destructive, outline-red)    │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

- Delete All Devices: opens confirmation modal with typed confirmation ("type DELETE to confirm")
- Card sections have `border: 1px solid var(--color-border)` separation
- Danger Zone card uses `border-color: var(--color-error)` with a subtle error tint background

---

## 9. Access Denied (`/access-denied`)

Renders **outside the shell** (no sidebar, no header).

```
┌────────────────────────────────────────────────────────────┐
│                  bg: --color-page-bg (full screen)         │
│                                                            │
│          ┌─────────────────────────────┐                  │
│          │  🔒  403                    │                  │
│          │  Access Denied              │  centered card   │
│          │  ─────────────────────────  │  360px wide      │
│          │  You don't have permission  │                  │
│          │  to view this page. Contact │                  │
│          │  your administrator.        │                  │
│          │                              │                  │
│          │  [ Go to Dashboard ]         │                  │
│          └─────────────────────────────┘                  │
└────────────────────────────────────────────────────────────┘
```

- Icon: `lock` Material icon, 48px, `--color-error`
- "403" label: `font-size: var(--font-2xl)`, bold, muted
- "Access Denied": `font-size: var(--font-xl)`, normal weight
- "Go to Dashboard" button: secondary (not primary — user might need to log in as a different account)
