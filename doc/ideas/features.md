# Low-Effort, High-Impact Features

Quick wins requiring minimal development effort for **Hometower** (free hobby edition). Last updated: 2026-04-14

> **Note:** Hometower is free for hobbyists but not open source. Phase 2 (**LightTower**) will be the commercial, closed-source team edition with multi-user collaboration, auto-discovery, and enterprise features. These features are for Hometower's core experience.

## 10 Killer Features

### 1. Device Type Icons/Emojis in Canvas
- **What**: Map `DeviceType` enums to emoji or simple icon fonts in canvas visualization
- **Where**: `src/ui/components/canvas_styles.py`
- **Effort**: ~30 min
- **Impact**: Makes topologies instantly scannable; visual hierarchy
- **Dependencies**: None — purely styling

### 2. Dark Mode Toggle
- **What**: Add light/dark theme variants to design tokens, wire toggle in app shell
- **Where**: `src/ui/design/tokens.py` + `src/ui/components/app_shell.py`
- **Effort**: ~1 hour
- **Impact**: Accessibility + user preference satisfaction
- **Dependencies**: NiceGUI has built-in dark mode support

### 3. Device Status Visual Indicators
- **What**: Style canvas nodes differently (border color, opacity, badge) based on `DeviceStatus` enum
- **Where**: `src/ui/components/canvas_styles.py` + `src/ui/components/canvas.py`
- **Effort**: ~45 min
- **Impact**: At-a-glance device health overview
- **Dependencies**: `DeviceStatus` enum already exists in `src/models/types.py`

### 4. Quick Search Highlight on Canvas
- **What**: Add search box that filters/highlights canvas nodes using existing search domain logic
- **Where**: `src/ui/components/canvas_container.py` + reuse `src/domain/search.py`
- **Effort**: ~1 hour
- **Impact**: Instant device navigation on busy topologies
- **Dependencies**: `search_domain.py` already implemented

### 5. Canvas Labels Visibility Toggle
- **What**: Add toolbar button to toggle connection label rendering
- **Where**: `src/ui/components/canvas_js.py` + `src/ui/components/topology_edit_toggle.py`
- **Effort**: ~20 min
- **Impact**: Declutter dense topologies on demand
- **Dependencies**: Labels already supported by Cytoscape.js

### 6. Device Favorites/Pin System
- **What**: Add `is_favorite: bool` to Device model; star icon in detail panel; filter option in sidebar
- **Where**: `src/models/device.py` (migration), `src/ui/components/device_detail_panel.py`, service layer
- **Effort**: ~2 hours (includes Alembic migration)
- **Impact**: UX gold — quick access to frequently-used devices
- **Dependencies**: One schema change (backward compatible)

### 7. Topology Thumbnails in Workspace List
- **What**: Generate static preview image of each topology on save; display in workspace detail
- **Where**: `src/ui/pages/workspace_detail.py` + Cytoscape `.png()` export or dom-to-image library
- **Effort**: ~2 hours
- **Impact**: Visual browsing of workspaces; faster recall
- **Dependencies**: Cytoscape has native PNG export

### 8. Device Count Dashboard Widget
- **What**: Add stats card showing device/location/service totals
- **Where**: `src/ui/pages/dashboard.py`
- **Effort**: ~1 hour
- **Impact**: Quick system health overview on login
- **Dependencies**: Pure aggregation — reuse `topology_data.py` helpers

### 9. Bulk Tag Application
- **What**: Select multiple devices on canvas → context menu → apply tags to all
- **Where**: `src/ui/components/canvas_events.py` (selection) + new POST endpoint in `src/api/routers/tags.py`
- **Effort**: ~1.5 hours
- **Impact**: 10× faster tagging workflow
- **Dependencies**: `TagService` already supports bulk operations

### 10. Keyboard Shortcut Cheat Sheet Modal
- **What**: Document existing shortcuts from `canvas_shortcuts.py` in a `?` modal
- **Where**: `src/ui/components/canvas_shortcuts.py` (export list) + new dialog component
- **Effort**: ~45 min
- **Impact**: Discoverability + onboarding; zero backend work
- **Dependencies**: Shortcuts already defined

---

## Implementation Strategy

**Phase 1 (No Migration):** Features 1–5, 8, 10 (6 features, ~4 hours, zero schema changes)
**Phase 2 (With Migration):** Features 6–7, 9 (3 features, ~5.5 hours, one schema change)

**Total estimated effort:** ~9.5 hours across the team.

**Suggested ownership:**
- **UX-Designer**: 1, 2, 3, 5, 10
- **Feature-Engineer**: 4, 6, 7, 8, 9 (with UX-Designer pair on canvas work)
