# Hometower — Interaction Patterns

> **Cross-references:** [components.md](components.md) · [pages.md](pages.md) for context · [themes.md](themes.md) for motion tokens

---

## 1. Animation Catalogue

All durations and easings are defined as CSS custom properties (see [themes.md § Motion Tokens](themes.md)).

| Interaction | Duration | Easing | Trigger |
|---|---|---|---|
| Sidebar expand/collapse | 200ms | `ease-out` | Collapse button click |
| Sidebar nav item hover | 150ms | `ease` | Mouse enter/leave |
| Card hover lift | 150ms | `ease` | Mouse enter/leave |
| Page fade-in | 200ms | `ease-out` | Route navigation |
| Panel slide-in (detail) | 220ms | `ease-out` | Node click in canvas |
| Panel slide-out | 180ms | `ease-in` | Click outside panel or × close |
| Dropdown open | 120ms | `ease-out` | Trigger click |
| Dropdown close | 100ms | `ease-in` | Click outside or Escape |
| Toast entrance (slide right) | 200ms | `ease-out` | `show_toast()` call |
| Toast exit (slide out) | 150ms | `ease-in` | Auto-dismiss or × click |
| Modal open (scale + fade) | 150ms | `ease-out` | `dialog.open()` |
| Modal close | 120ms | `ease-in` | `dialog.close()` or Escape |
| Button press | 80ms | `ease` | `mousedown` |
| Button release | 80ms | `ease-out` | `mouseup` |

**Reduced-motion:** When `prefers-reduced-motion: reduce` is active, all durations collapse to ≤ 50ms and transforms are removed. Opacity fades are retained (they do not cause vestibular discomfort).

---

## 2. Cytoscape.js Drag-and-Drop (Device Creation)

### 2.1 Palette → Canvas Drop

1. User picks up a device type card from the palette (`dragstart` fires, `dataTransfer.setData('deviceType', type)`)
2. User drags over the canvas — canvas listening for `dragover` (prevents default to allow drop)
3. User releases — `drop` handler fires:
   - Reads `dataTransfer.getData('deviceType')`
   - Converts `event.clientX/Y` to Cytoscape canvas coordinates via `cy.renderer().projectIntoViewport(x, y)`
   - Dispatches `ht:drop-device` custom event with `{ deviceType, x, y }`
4. Python handler calls `POST /api/devices` then `POST /api/diagram/elements` to add the node
5. Canvas adds the node element at the dropped position
6. New node is auto-selected → Detail panel slides in

**Visual feedback during drag:**
- Palette card shows `opacity: 0.6` while dragging
- Canvas shows a dashed-border drop zone outline when `dragover` is active (color: `--color-primary`, dashed)

### 2.2 Node Position Drag (Move Existing Node)

- `cy.on('dragfree', ...)` fires after user drags a node to a new position
- Position is debounced (300ms) then saved via `POST /api/diagram/`
- No visual indicator during drag — Cytoscape handles default drag rendering
- Undo: `Ctrl+Z` restores the previous position (see § 8)

---

## 3. Node and Edge Selection

### 3.1 Single Node Click

1. `cy.on('tap', 'node', ...)` fires
2. Previous selection cleared
3. Selected node: `border-color: var(--color-primary)`, `border-width: 3px`, accent glow `box-shadow: 0 0 8px var(--color-primary-30)`
4. Detail panel slides in from the right (220ms ease-out)
5. Detail panel header populates with device name + type badge
6. Python: side panel DOM updated via NiceGUI `ui.update()`

### 3.2 Single Edge Click

1. `cy.on('tap', 'edge', ...)` fires
2. Selected edge: `line-color: var(--color-primary)`, `width: 3px`
3. Connection detail panel replaces device detail panel (panel content swaps)

### 3.3 Multi-Select (Rubber-Band)

1. Click-drag on empty canvas area → rubber-band rectangle appears (`background: rgba(79, 70, 229, 0.1)`, `border: 1px solid var(--color-primary)`)
2. Release → all nodes within rectangle are selected (Cytoscape `boxSelect`)
3. Multi-select mode: detail panel shows "N devices selected" with bulk action buttons (Delete All, future)

### 3.4 Click on Empty Canvas

- Deselects all nodes/edges
- Detail panel slides out (180ms ease-in)

### 3.5 Hover on Node

- Tooltip after 600ms showing device type, IP address (if set)
- `cursor: pointer`

---

## 4. Detail Panel Switching

The right panel is a single container that swaps content based on selection type.

```
State machine:
  [hidden] ──(node click)──→ [device panel]
  [hidden] ──(edge click)──→ [connection panel]
  [device panel] ──(edge click)──→ [connection panel]
  [device panel] ──(canvas click)──→ [hidden]
  [connection panel] ──(node click)──→ [device panel]
  [connection panel] ──(canvas click)──→ [hidden]
```

**Panel transition:**
- Content fades out (100ms) then new content fades in (150ms)
- Width stays at 320px during swap; only content changes
- Panel stays open when switching between device-to-device by clicking different nodes

---

## 5. Inline Editing in Device Detail Panel

Fields are displayed as static text by default. Clicking a field value switches it to an input.

```
pihole                ← static display
─────────────────────
[pihole            ] ← on click: becomes input, shows Save/Cancel inline
```

1. Click on field value → input appears pre-filled, field highlighted
2. Edit value
3. Press Enter or click the ✓ save icon: `PATCH /api/devices/{id}`, show success toast
4. Press Escape or click × cancel: discard, revert to display
5. Blur (click outside without saving): prompts "Discard changes?" if value changed

**Accessible:** Input uses `aria-label` matching the field name. Status changes use `aria-live="polite"`.

---

## 6. Modal Flows

### 6.1 Add / Edit Location

```
[+ Add Location] button
    └─ dialog.open()
           ├─ Fields populate (empty for new, current values for edit)
           ├─ Conditional fields (lat/lng only if type=geo)
           ├─ [Cancel] → dialog.close(), no change
           ├─ [Save] → POST or PATCH API → success toast → dialog.close() → table refresh
           └─ Validation error → inline error labels, Save stays disabled
```

### 6.2 Delete Confirmation

```
[Delete] button (in table row)
    └─ confirmation dialog:
           "Delete 'device-name'?"
           "This action cannot be undone."
           ├─ [Cancel] → dialog.close()
           └─ [Delete] → DELETE API → success toast → dialog.close() → table row removed
```

Destructive delete button is **red**, spatially separated from Cancel by at least 16px. This intentional distance increases acquisition time (Fitts's Law) to prevent accidental clicks.

### 6.3 Import Data

```
[Browse…] or drag-and-drop file → file type validation (JSON only)
    ├─ Valid file → preview summary: "48 devices, 12 connections found"
    │       └─ [Import] → POST /api/data/import → progress indicator → summary toast
    └─ Invalid file → inline error "Only .json files are supported"
```

---

## 7. Keyboard Shortcuts

### 7.1 Global Shortcuts (available on all pages)

| Key | Action |
|---|---|
| `?` | Open keyboard shortcuts overlay |
| `Escape` | Close active modal / dropdown / panel |
| `Ctrl+/` (macOS: `⌘/`) | Focus global search |

### 7.2 Canvas Shortcuts (active when canvas has focus)

| Key | Action |
|---|---|
| `Delete` / `Backspace` | Delete selected node(s) or edge |
| `Ctrl+A` (⌘A) | Select all nodes |
| `Ctrl+Z` (⌘Z) | Undo last action |
| `Ctrl+Shift+Z` / `Ctrl+Y` (⌘⇧Z) | Redo |
| `Ctrl+C` (⌘C) | Copy selected node(s) |
| `Ctrl+V` (⌘V) | Paste node(s) at cursor position |
| `+` / `=` | Zoom in |
| `-` | Zoom out |
| `0` | Reset zoom to fit all nodes |
| `F` | Fit all nodes to screen |
| `G` | Apply grid layout |
| `D` | Apply dagre (hierarchical) layout |
| Arrow keys | Nudge selected node(s) by 10px |
| `Shift+Arrow` | Nudge by 1px (fine control) |

### 7.3 Form Shortcuts

| Key | Action |
|---|---|
| `Enter` | Submit form (if valid) |
| `Escape` | Cancel / close modal |
| `Tab` | Next field |
| `Shift+Tab` | Previous field |

### 7.4 Keyboard Shortcuts Overlay

Triggered by `?` key or UserMenu "Keyboard Shortcuts" item. Renders as a modal with a two-column list grouped by context (Global, Canvas, Forms). Closes on Escape.

---

## 8. Undo / Redo

Limited to topology canvas operations. Managed client-side by a command stack.

**Supported actions:**
- Node position change (drag)
- Node creation (palette drop / paste)
- Node deletion
- Edge creation
- Edge deletion

**Implementation approach:**
```
commandStack = []   // undo stack
redoStack = []      // redo stack
MAX_HISTORY = 50

push(command):    commandStack.push(command); redoStack = []
undo():           cmd = commandStack.pop(); cmd.undo(); redoStack.push(cmd)
redo():           cmd = redoStack.pop(); cmd.apply(); commandStack.push(cmd)
```

Each command is an object with `{ apply(), undo() }` methods that call the relevant API (`POST`, `DELETE`, `PATCH /api/devices`, `PATCH /api/diagram`).

**Visual feedback:** Toast "Undid: node created" / "Redid: node deleted" appears for 2 seconds (info type).

---

## 9. Right-Click Context Menu (Canvas)

Triggered by right-click on a node or edge. Dismissed by clicking outside or pressing Escape.

### Node Context Menu

```
┌──────────────────┐
│  Edit            │  → opens inline editing for the selected node's name
│  Duplicate       │  → creates a copy offset by (20px, 20px)
│  Connect to…     │  → enters edge-drawing mode
│  ─────────────── │
│  Delete          │  → destructive, color: --color-error
└──────────────────┘
```

### Edge Context Menu

```
┌──────────────────┐
│  Edit Label      │
│  ─────────────── │
│  Delete          │  → color: --color-error
└──────────────────┘
```

### Menu Specs

- Menu container: `background: var(--color-surface-alt)`, `border: 1px solid var(--color-border)`, `border-radius: 6px`, `box-shadow: var(--shadow-menu)`, `min-width: 140px`
- Menu item: 32px tall, `padding: 0 16px`, `font-size: var(--font-sm)`, hover: `background: var(--color-nav-hover-bg)`
- Destructive item: hover background uses `var(--color-error-bg)` tint
- Positioning: appears at cursor position, flips if it would overflow viewport
- Z-index: 9999 (must appear above all other elements)
- Keyboard: arrow keys move focus between items, Enter selects, Escape closes

---

## 10. Edge Drawing Mode

Activated by "Connect to…" from context menu or by hovering near the edge of a node (port handles appear).

1. User clicks "Connect to…" → canvas enters drawing mode, cursor changes to `crosshair`
2. Hovering over other nodes highlights them as potential targets
3. User clicks a target node → edge is created
4. `POST /api/connections` with `{ source_id, target_id, type: "Ethernet" }`
5. Prompt: connection detail panel opens to allow setting type and label
6. Escape cancels drawing mode

---

## 11. Topology Layout Algorithms

The layout bar (`topology_layout_bar.py`) provides quick-apply layout buttons:

| Button | Algorithm | Best for |
|---|---|---|
| Grid | Uniform grid | Many devices, no hierarchy |
| Dagre | Hierarchical tree | Network with clear parent/child |
| Concentric | Rings by centrality | Hub-and-spoke topology |
| Breadthfirst | BFS tree | Layer-by-layer topology |
| Fit | Fit to viewport | After any layout, reset zoom |

Layout applies with a 500ms animation (`cy.layout({ animate: true, animationDuration: 500 })`), then positions are saved to `DiagramLayout` via `POST /api/diagram/`.

---

## 12. Copy-to-Clipboard (IP/MAC Values)

IP addresses and MAC addresses display a clipboard icon (16px, muted) on hover.

```
192.168.1.10  📋
```

Interaction:
1. Click clipboard icon → `navigator.clipboard.writeText(value)`
2. Show info toast "Copied to clipboard" for 2000ms
3. Icon briefly changes to `check` (200ms) then reverts to `content_copy`

This applies in: inventory table, device detail panel, connection detail panel.
