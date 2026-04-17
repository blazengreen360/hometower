# RFC: Premium Design System & Theme Engine (HT-027)

## 1. Overview

Hometower needs a visual overhaul to look like a polished infrastructure tool rather than a
prototype. This RFC introduces a **three-theme engine** (dark / light / midnight) driven by
CSS custom properties, a fully expanded token system (shadows, radii, transitions, typography),
and a component-level migration strategy that converts every hardcoded `COLOR_*` reference to
`var(--ht-*)` CSS variables. Theme selection is persisted in `app.storage.user['theme']` and
switches without page reload.

**Design language: "Clean Ops"** — airy whitespace, card-based surfaces, clean solid panels,
1px borders, minimal shadows, smooth 150–200 ms transitions. No glassmorphism.

**Parnas hidden decision per new module:**
- `src/ui/design/tokens.py` — hides the palette values for each named theme
- `src/ui/design/theme_engine.py` — hides how CSS custom properties are built and injected
  into the browser; if we switch from inline style injection to a CSS-in-JS approach, only
  this file changes
- `src/ui/components/canvas_styles.py` (extended) — hides how Cytoscape.js style arrays are
  built from a theme dict; if we swap Cytoscape for another canvas library, only this file
  changes

---

## 2. Data Model Changes

None. Theme preference is stored in NiceGUI server-side session storage
(`app.storage.user['theme']`), not in PostgreSQL. No Alembic migration is needed.

---

## 3. Domain Logic

None. Theme selection is a presentation concern. `src/domain/` is untouched.

---

## 4. Service Layer

None. No new service methods.

---

## 5. API Layer

None. No new endpoints.

---

## 6. UI Layer

This section is the complete implementation contract.

---

### 6.1 Token Architecture — `src/ui/design/tokens.py`

**Rewrite** this file. It must contain: three complete theme dictionaries, shared structural
tokens, device-type dicts (unchanged), and backward-compatibility `COLOR_*` aliases.

#### 6.1.1 Theme dictionaries — `THEMES`

```python
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
        # Shadows (full box-shadow values)
        "shadow_sm":         "0 1px 2px rgba(0,0,0,0.3)",
        "shadow_md":         "0 4px 12px rgba(0,0,0,0.4)",
        "shadow_lg":         "0 8px 24px rgba(0,0,0,0.5)",
    },
    "light": {
        "bg_base":           "#f8fafc",
        "bg_surface":        "#ffffff",
        "bg_surface_raised": "#ffffff",   # shadow differentiates, not bg
        "bg_sidebar":        "#f1f5f9",
        "accent":            "#4f46e5",
        "accent_hover":      "#4338ca",
        "accent_glow":       "rgba(79, 70, 229, 0.15)",
        "text_primary":      "#1e293b",
        "text_secondary":    "#64748b",
        "text_on_accent":    "#ffffff",
        "border":            "rgba(0, 0, 0, 0.08)",
        "success":           "#16a34a",   # green-600 — sufficient contrast on white
        "warning":           "#d97706",   # amber-600
        "error":             "#dc2626",   # red-600
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
        "text_on_accent":    "#001020",   # dark text on cyan — WCAG AA
        "border":            "rgba(0, 229, 255, 0.15)",
        "success":           "#4ade80",
        "warning":           "#fbbf24",
        "error":             "#f87171",
        "shadow_sm":         "0 1px 2px rgba(0,0,0,0.6)",
        "shadow_md":         "0 4px 12px rgba(0,0,0,0.7)",
        "shadow_lg":         "0 8px 24px rgba(0,0,0,0.8)",
    },
}
```

#### 6.1.2 Shared structural tokens — `STATIC_CSS_VARS`

These never change between themes and are injected once alongside the theme vars.

```python
STATIC_CSS_VARS: dict[str, str] = {
    "--ht-radius-card":      "10px",
    "--ht-radius-input":     "8px",
    "--ht-radius-modal":     "12px",
    "--ht-radius-pill":      "9999px",
    "--ht-transition-fast":  "150ms ease",
    "--ht-transition-norm":  "200ms ease",
    "--ht-font-body": (
        "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    ),
    "--ht-font-mono":        "'Fira Mono', 'Courier New', monospace",
}
```

#### 6.1.3 CSS variable naming convention

The mapping from Python dict key to CSS custom property is mechanical:

```
"{key}" → "--ht-{key.replace('_', '-')}"
```

Examples:
- `bg_base` → `--ht-bg-base`
- `accent_glow` → `--ht-accent-glow`
- `shadow_sm` → `--ht-shadow-sm`
- `text_on_accent` → `--ht-text-on-accent`

`theme_engine.py` generates the CSS var names from the Python keys using this rule — no
hardcoded mapping table is required.

#### 6.1.4 Backward-compatibility `COLOR_*` aliases

Retain all existing `COLOR_*` constants, pointing them to the dark theme. This keeps every
file currently importing these constants working without modification until the migration
phases are complete.

```python
# ── Backward-compatibility aliases (dark theme values) ────────────────────
# NOTE: Values differ slightly from the old single-palette constants.
# These shifts are intentional — they align with the new "Control Room" dark
# palette defined in HT-027.  Any component referencing COLOR_* still compiles
# and runs correctly; the visual delta is minor.
_dark = THEMES["dark"]
COLOR_PRIMARY      = _dark["accent"]            # #6366f1
COLOR_PRIMARY_DARK = _dark["accent_hover"]      # #818cf8
COLOR_SURFACE      = _dark["bg_surface"]        # #1a1a2e
COLOR_SURFACE_ALT  = _dark["bg_surface_raised"] # #252540
COLOR_TEXT         = _dark["text_primary"]      # #e2e8f0
COLOR_TEXT_MUTED   = _dark["text_secondary"]    # #94a3b8
COLOR_ERROR        = _dark["error"]             # #f87171
COLOR_SUCCESS      = _dark["success"]           # #4ade80
COLOR_WARNING      = _dark["warning"]           # #fbbf24
```

> **Cleanup note:** After all `COLOR_*` imports are removed from components (Phase 4
> complete), delete these aliases in a follow-up story. Do not delete them during this story.

#### 6.1.5 Unchanged sections of `tokens.py`

The following sections **remain identical** to the current file — copy them verbatim:
- `SPACING_*` constants
- `FONT_*` constants
- `FONT_MONO`
- `DEVICE_SHAPES` and `DEVICE_SHAPE_BY_VALUE`
- `DEVICE_TYPE_COLORS` — explicitly excluded from theming per story scope
- `DEVICE_TYPE_ICONS`

**File size estimate:** ~210 lines. Within the 250-line cap.

---

### 6.2 Theme Engine — `src/ui/design/theme_engine.py`  *(new file)*

This module hides the mechanism of CSS custom property injection. Every function takes a
theme name string and produces HTML/JS artefacts. It imports from `tokens.py` only.

```
src/ui/design/theme_engine.py
```

#### 6.2.1 `build_css_var_dict(theme_name: str) -> dict[str, str]`

Returns a dict of all CSS custom property names → values for the named theme, combining
theme-specific tokens and static structural tokens.

```python
def build_css_var_dict(theme_name: str) -> dict[str, str]:
    theme = THEMES.get(theme_name, THEMES["dark"])
    dynamic = {
        f"--ht-{k.replace('_', '-')}": v
        for k, v in theme.items()
    }
    return {**STATIC_CSS_VARS, **dynamic}
```

#### 6.2.2 `get_initial_theme_css(theme_name: str) -> str`

Returns a complete `<style>` tag string suitable for injection via `ui.add_head_html()`.
Injected during server-side page render — guarantees zero FOUC.

```python
def get_initial_theme_css(theme_name: str) -> str:
    props = "\n".join(
        f"  {k}: {v};"
        for k, v in build_css_var_dict(theme_name).items()
    )
    font_link = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
        '&family=Fira+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
    )
    style_tag = f'<style id="ht-theme">\n:root {{\n{props}\n}}\n</style>'
    return font_link + style_tag
```

#### 6.2.3 `get_theme_js_helpers() -> str`

Returns a `<script>` block string with the global JS functions required for runtime theme
switching and tooltip colour reads. Injected **once** via `ui.add_head_html()` in
`app_shell`. Must be idempotent (guard with `if (window._htThemeJsLoaded) return;`).

```javascript
window.htApplyThemeVars = function(vars) {
    // vars is a plain object: { "--ht-bg-base": "#0f0f1a", ... }
    var root = document.documentElement;
    Object.keys(vars).forEach(function(k) {
        root.style.setProperty(k, vars[k]);
    });
};

window._htThemeColors = function() {
    // Called at tooltip render time so values are always current theme.
    var s = getComputedStyle(document.documentElement);
    return {
        success:        s.getPropertyValue('--ht-success').trim(),
        error:          s.getPropertyValue('--ht-error').trim(),
        textPrimary:    s.getPropertyValue('--ht-text-primary').trim(),
        textSecondary:  s.getPropertyValue('--ht-text-secondary').trim(),
        bgSurfaceRaised:s.getPropertyValue('--ht-bg-surface-raised').trim(),
    };
};
```

#### 6.2.4 `apply_theme_to_client(theme_name: str) -> None`

Async function called from the theme-switcher click handler. Updates CSS vars on the
current page without reload.

```python
import json
from nicegui import ui

async def apply_theme_to_client(theme_name: str) -> None:
    css_vars = build_css_var_dict(theme_name)
    await ui.run_javascript(f"htApplyThemeVars({json.dumps(css_vars)})")
```

Note: `ui.run_javascript()` requires `await` only when the return value is needed. When
called for side-effects, it MAY be called without `await`. Use `await` here so any JS
exception propagates to the Python caller for logging.

**File size estimate:** ~90 lines. Well within 250-line cap.

---

### 6.3 Cytoscape Theme Sync — `src/ui/components/canvas_styles.py`

#### 6.3.1 New export: `build_theme_style_json(theme_name: str) -> str`

Add a public function that returns a JSON string of Cytoscape style rules built from the
named theme. The existing `CANVAS_STYLE_JS` constant remains as an alias pointing to the
dark theme for backward compatibility during migration.

```python
from src.ui.design.tokens import THEMES, DEVICE_TYPE_COLORS

def build_theme_style_json(theme_name: str) -> str:
    """Return JSON-serialised Cytoscape style array for the given theme."""
    t = THEMES.get(theme_name, THEMES["dark"])
    base_styles = [
        {
            "selector": "node",
            "style": {
                "label":           "data(label)",
                "shape":           "data(shape)",
                "background-color": t["accent"],
                "color":           t["text_primary"],
                "text-valign":     "bottom",
                "text-halign":     "center",
                "font-family":     "Inter, sans-serif",
                "font-size":       "12px",
                "width":           48,
                "height":          48,
                "border-width":    1,
                "border-color":    t["border"],
            },
        },
        {
            "selector": "node:selected",
            "style": {
                "border-color": t["accent"],
                "border-width": 2,       # 2px per story — no glow halo
            },
        },
        {
            "selector": "edge",
            "style": {
                "curve-style":          "bezier",
                "target-arrow-shape":   "triangle",
                "line-color":           t["text_secondary"],
                "target-arrow-color":   t["text_secondary"],
                "width":                2,
            },
        },
        {
            "selector": "edge:selected",
            "style": {
                "width":                4,
                "line-color":           t["accent"],
                "target-arrow-color":   t["accent"],
            },
        },
    ]
    # Append per-device-type colour rules (DEVICE_TYPE_COLORS is not theme-dependent)
    for dtype, colour in DEVICE_TYPE_COLORS.items():
        base_styles.append({
            "selector": f'node[device_type = "{dtype.value}"]',
            "style":    {"background-color": colour},
        })
    # Append status and connection-type styles (unchanged from current)
    base_styles.extend(_build_selector_styles("node", "status", _STATUS_STYLE_BY_DEVICE_STATUS))
    base_styles.extend(_build_selector_styles(
        "edge", "connection_type",
        {k: v for k, v in EDGE_STYLE_BY_CONNECTION_TYPE.items() if k != "Ethernet"},
    ))
    return json.dumps(base_styles)

# Backward-compat alias
CANVAS_STYLE_JS: str = build_theme_style_json("dark")
```

#### 6.3.2 `updateCyTheme` JS function — defined in `canvas.py`

Add to the `_CANVAS_INIT_JS_TEMPLATE` string (after `window.initCanvas` definition):

```javascript
window.updateCyTheme = function(stylesJson) {
    if (!window._cy) return;
    window._cy.style().fromJson(JSON.parse(stylesJson)).update();
};
```

#### 6.3.3 Canvas init — background colour

In `canvas.py`, the `#cy` div background must use a CSS custom property so it switches
with the theme without JS:

```python
# canvas.py — the cy div element style
ui.element("div").props('id="cy"').style(
    "width: 100%; height: 100%; background-color: var(--ht-bg-base);"
)
```

Replace the current `background-color: {COLOR_SURFACE}` f-string.

#### 6.3.4 Canvas init — style argument

In `canvas.py`, `_CANVAS_INIT_JS_TEMPLATE` passes styles via `__HT_CANVAS_STYLE__`
placeholder. The `render_canvas` function already replaces this placeholder at runtime.
Change it to use `build_theme_style_json` keyed from the current session theme:

```python
# In render_canvas():
from nicegui import app as nicegui_app
from src.ui.components.canvas_styles import build_theme_style_json

theme = nicegui_app.storage.user.get("theme", "dark")
js = (_CANVAS_INIT_JS_TEMPLATE
      .replace("__HT_CANVAS_STYLE__", build_theme_style_json(theme))
      # … other placeholder replacements …
      )
```

---

### 6.4 Theme Switcher — `src/ui/components/app_shell.py`

#### 6.4.1 Theme selector in user menu

Extend `_render_user_menu()` to add a "Theme" sub-section **above** the separator before
logout:

```python
def _render_user_menu() -> None:
    username: str = nicegui_app.storage.user.get("username", "User")
    with ui.dropdown_button(username, auto_close=False).props("flat color=grey-4"):
        ui.item("Change Password",
                on_click=lambda: ui.navigate.to("/settings/profile"))
        ui.separator()
        # ── Theme submenu ────────────────────────────────────────────────
        with ui.row().classes("px-4 py-1 items-center gap-2"):
            ui.label("Theme").style(
                "font-size:0.75rem; font-weight:600; color:var(--ht-text-secondary);"
                " text-transform:uppercase; letter-spacing:0.5px;"
            )
        for label, key in [("Dark", "dark"), ("Light", "light"), ("Midnight", "midnight")]:
            current = nicegui_app.storage.user.get("theme", "dark")
            ui.item(
                f"{'✓ ' if current == key else '  '}{label}",
                on_click=lambda k=key: _handle_theme_change(k),
            )
        ui.separator()
        # ────────────────────────────────────────────────────────────────
        ui.item("Logout", on_click=_do_logout)
```

> Because `auto_close=False` is set, the dropdown stays open while the user browses themes.
> The checkmark updates on next open (re-render). This avoids complex reactive state for the
> checkmark — the story AC only requires the theme to switch, not the checkmark to update
> in-place.

#### 6.4.2 `_handle_theme_change` handler

```python
import asyncio
from src.ui.design.theme_engine import apply_theme_to_client
from src.ui.components.canvas_styles import build_theme_style_json

async def _handle_theme_change(theme: str) -> None:
    nicegui_app.storage.user["theme"] = theme
    await apply_theme_to_client(theme)
    # Sync Cytoscape if the topology canvas is currently loaded
    styles_json = build_theme_style_json(theme)
    await ui.run_javascript(
        f"if (window.updateCyTheme) window.updateCyTheme({json.dumps(styles_json)})"
    )
```

#### 6.4.3 CSS injection in `app_shell` context manager

At the top of the `app_shell` context manager body (before `ui.query("body").style(...)`),
add:

```python
from src.ui.design.theme_engine import get_initial_theme_css, get_theme_js_helpers

theme = nicegui_app.storage.user.get("theme", "dark")
ui.add_head_html(get_initial_theme_css(theme))
ui.add_head_html(get_theme_js_helpers())
```

The `get_initial_theme_css` call injects:
1. Google Fonts CDN links for Inter and Fira Mono
2. `<style id="ht-theme">` with all `:root` CSS custom properties for the stored theme

The `get_theme_js_helpers` call injects:
1. `window.htApplyThemeVars` — used by runtime theme switching
2. `window._htThemeColors` — used by `canvas_tooltip.py` at tooltip render time

Also inject a global animation + typography baseline style block once:

```python
_GLOBAL_CSS = """
<style id="ht-global">
  * { box-sizing: border-box; }
  body { font-family: var(--ht-font-body); }
  @keyframes htFadeIn { from { opacity: 0; } to { opacity: 1; } }
  .ht-page-content { animation: htFadeIn var(--ht-transition-fast); }
</style>
"""
ui.add_head_html(_GLOBAL_CSS)
```

The `ht-page-content` class is applied to the top-level `ui.column()` in the `app_shell`
context manager (the current `ui.column().classes("flex-1 w-full")`):

```python
with ui.column().classes("flex-1 w-full ht-page-content").style("min-height:0;"):
    yield
```

#### 6.4.4 Body style — remove Python f-string, use CSS vars

Replace:
```python
ui.query("body").style(
    f"background-color:{COLOR_SURFACE}; color:{COLOR_TEXT}; margin:0;"
)
```
With:
```python
ui.query("body").style(
    "background-color:var(--ht-bg-surface); color:var(--ht-text-primary); margin:0;"
)
```

#### 6.4.5 Header and sidebar — use CSS vars

All `f"...{COLOR_*}..."` inline styles in `_render_header`, `_render_sidebar`, and
`_nav_item` must be converted to `var(--ht-*)`. The complete mapping:

| Old expression | New CSS value |
|---|---|
| `f"...{COLOR_SURFACE}..."` | `var(--ht-bg-surface)` |
| `f"...{COLOR_SURFACE_ALT}..."` | `var(--ht-bg-surface-raised)` |
| `f"...{COLOR_PRIMARY}..."` | `var(--ht-accent)` |
| `f"...{COLOR_TEXT}..."` | `var(--ht-text-primary)` |
| `f"...{COLOR_TEXT_MUTED}..."` | `var(--ht-text-secondary)` |
| `#383849` (hardcoded border) | `var(--ht-border)` |
| `f"...{COLOR_PRIMARY}20..."` (hex-alpha) | `var(--ht-accent-glow)` |

##### Revised `_nav_item` implementation

```python
def _nav_item(label: str, icon: str, route: str, active: bool, disabled: bool) -> None:
    active_style = (
        "background-color:var(--ht-accent-glow); border-left:3px solid var(--ht-accent);"
        if active else ""
    )
    text_color = "var(--ht-accent)" if active else "var(--ht-text-primary)"
    with ui.row().classes("items-center px-3 py-2 cursor-pointer w-full").style(
        active_style + f" color:{text_color};"
        " transition:background-color var(--ht-transition-fast);"
    ).on("click", lambda r=route, d=disabled: (None if d else ui.navigate.to(r))):
        ui.icon(icon).style(f"color:{text_color}; font-size:1.25rem")
        ui.label(label).style(
            f"font-weight:{'600' if active else '400'}; font-size:0.875rem"
        )
```

> The hover tint effect (bg tints to `bg-surface-raised` on hover) should be implemented
> via CSS class on the row `<div>` using a `<style>` rule, not Python on-hover handlers:
>
> ```css
> .ht-nav-item:hover { background-color: var(--ht-bg-surface-raised); }
> ```
>
> Add the class `.ht-nav-item` to the row element and inject this rule in `_GLOBAL_CSS`.

#### 6.4.6 Header bar height and style

Change header height from `52px` to `48px` per story. Remove the hardcoded `#383849`
border and use `var(--ht-border)`:

```python
with ui.header().style(
    "background-color:var(--ht-bg-surface); border-bottom:1px solid var(--ht-border);"
    " padding:0 16px; height:48px; display:flex; align-items:center;"
):
```

#### 6.4.7 Session-expiry JS overlay — remove hardcoded colours

The `_SESSION_EXPIRY_JS` string in `app_shell.py` contains hardcoded hex values. Replace
them with CSS custom property reads at the time the overlay is constructed. The overlay
itself uses `getComputedStyle(document.documentElement)` to read current theme values:

Replace the hardcoded inline styles in `_SESSION_EXPIRY_JS`:
- `background:#1e1e2e` → `background:getComputedStyle(document.documentElement).getPropertyValue('--ht-bg-surface').trim()`
- `color:#cdd6f4` → `color:getComputedStyle(document.documentElement).getPropertyValue('--ht-text-primary').trim()`
- `background:#4f46e5` → `background:getComputedStyle(document.documentElement).getPropertyValue('--ht-accent').trim()`
- `color:white` on the button → `color:getComputedStyle(document.documentElement).getPropertyValue('--ht-text-on-accent').trim()`

The scrim `rgba(0,0,0,0.85)` stays hardcoded — it is intentionally opaque regardless of
theme.

---

### 6.5 Login Page Theming — `src/ui/pages/login.py`

The login page has no `app_shell`. It always renders with the dark theme. Inject CSS vars
directly into the page function.

Add at the top of `login_page()`:

```python
from src.ui.design.theme_engine import get_initial_theme_css, get_theme_js_helpers

ui.add_head_html(get_initial_theme_css("dark"))
ui.add_head_html(get_theme_js_helpers())
```

Replace the `ui.query("body").style(f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT}")`:

```python
ui.query("body").style(
    "background-color: var(--ht-bg-base); color: var(--ht-text-primary);"
)
```

Then convert all `COLOR_*` f-strings in the login card, error label, and button to use
`var(--ht-*)` equivalents.

---

### 6.6 `access_denied.py` — Standalone page

Same pattern as login: inject `get_initial_theme_css("dark")` and convert `COLOR_*`
f-strings to `var(--ht-*)`.

---

### 6.7 Component Migration Strategy — Phase 4

This phase converts every `src/ui/` file from Python f-string colour injection to CSS variable
references in inert string literals. The conversion is mechanical:

**Substitution table (full mapping)**

| Old f-string expression | New static string |
|---|---|
| `f"...color:{COLOR_TEXT}..."` | `"...color:var(--ht-text-primary)..."` |
| `f"...color:{COLOR_TEXT_MUTED}..."` | `"...color:var(--ht-text-secondary)..."` |
| `f"...color:{COLOR_PRIMARY}..."` | `"...color:var(--ht-accent)..."` |
| `f"...color:{COLOR_PRIMARY_DARK}..."` | `"...color:var(--ht-accent-hover)..."` |
| `f"...background:{COLOR_SURFACE}..."` | `"...background:var(--ht-bg-surface)..."` |
| `f"...background:{COLOR_SURFACE_ALT}..."` | `"...background:var(--ht-bg-surface-raised)..."` |
| `f"...background-color:{COLOR_SURFACE}..."` | `"...background-color:var(--ht-bg-surface)..."` |
| `f"...color:{COLOR_ERROR}..."` | `"...color:var(--ht-error)..."` |
| `f"...color:{COLOR_SUCCESS}..."` | `"...color:var(--ht-success)..."` |
| `f"...color:{COLOR_WARNING}..."` | `"...color:var(--ht-warning)..."` |

When a migration removes ALL `COLOR_*` imports from a file, remove the entire import line.

**Special cases:**

`ui.notify(color=COLOR_*)` — NiceGUI's `notify()` `color` parameter accepts Quasar colour
names, not hex. Replace with `"positive"` / `"negative"` / `"warning"` respectively.

Strings that mix a `COLOR_*` value with Python logic (e.g. `inventory_helpers.py` line 133:
`tcolor = str(tdata.get("color", COLOR_PRIMARY))`) — these are data-driven at runtime and
cannot be replaced with a static var-reference. Leave them as-is with `COLOR_*` alias.

---

### 6.8 JS-in-String Colour Migration

Three canvas component files inject colours into JS strings at render time. Each has its
own migration pattern.

#### 6.8.1 `canvas_tooltip.py` — remove `.replace()` calls

**Current pattern:**
```python
_CANVAS_TOOLTIP_JS = (_CANVAS_TOOLTIP_JS_TEMPLATE
    .replace("__HT_SUCCESS__", COLOR_SUCCESS)
    .replace("__HT_ERROR__", COLOR_ERROR)
    .replace("__HT_TEXT_MUTED__", COLOR_TEXT_MUTED)
    .replace("__HT_SURFACE_ALT__", COLOR_SURFACE_ALT)
    .replace("__HT_TEXT__", COLOR_TEXT)
)
```

**New pattern:** Remove all `.replace()` calls. In the JS template, replace the placeholder
tokens with `window._htThemeColors()` calls (the helper injected by `theme_engine`).

Replace the `HT_STATUS_COLORS` literal in the template:
```javascript
// Old
var HT_STATUS_COLORS = { running: '__HT_SUCCESS__', stopped: '__HT_ERROR__', ... };

// New
var tc = window._htThemeColors();
var HT_STATUS_COLORS = {
    running: tc.success,
    stopped: tc.error,
    unknown: tc.textSecondary
};
```

Replace tooltip box inline styles — change from:
```javascript
box.style.cssText = 'background:__HT_SURFACE_ALT__; color:__HT_TEXT__; ...';
```
to:
```javascript
var tc = window._htThemeColors();
box.style.cssText = 'background:' + tc.bgSurfaceRaised + '; color:' + tc.textPrimary + '; ...';
```

`window._htThemeColors()` reads `getComputedStyle(document.documentElement)` at the moment
the tooltip is constructed, so it always reflects the current active theme.

#### 6.8.2 `canvas_zoom.py` — remove f-string, use `var()` in `cssText`

`cssText` fully supports CSS custom properties — `var()` may appear in `cssText` string
literals.

Replace the f-string `_BTN_STYLE`:
```python
# Old (f-string with Python COLOR_* interpolation)
_BTN_STYLE = (
    "width:36px;height:36px;border-radius:6px;"
    f"background:{COLOR_SURFACE_ALT};"
    "border:1px solid rgba(255,255,255,0.1);"
    f"color:{COLOR_TEXT};"
    ...
)

# New (plain string — no f-string needed)
_BTN_STYLE = (
    "width:36px;height:36px;border-radius:var(--ht-radius-input);"
    "background:var(--ht-bg-surface-raised);"
    "border:1px solid var(--ht-border);"
    "color:var(--ht-text-primary);"
    "cursor:pointer;font-size:1.25rem;line-height:1;"
    "padding:0;display:flex;align-items:center;justify-content:center;"
)
```

Replace hardcoded hex values in the JS help modal string within `_ZOOM_CONTROLS_JS`:

| Old literal | Replace with |
|---|---|
| `#27273a` (tool card background) | `var(--ht-bg-surface-raised)` |
| `rgba(255,255,255,0.12)` (card border) | `var(--ht-border)` |
| `#cdd6f4` (card text colour) | `var(--ht-text-primary)` |
| `rgba(0,0,0,0.55)` (overlay scrim) | Keep as-is (intentional opaque scrim) |
| `#1e1e2e` (modal background) | `var(--ht-bg-surface)` |
| `rgba(255,255,255,0.12)` (modal border) | `var(--ht-border)` |
| `#2f324a` (close button background) | `var(--ht-bg-surface-raised)` |
| `#bac2de` (body text) | `var(--ht-text-secondary)` |

#### 6.8.3 `canvas_shortcuts.py` — no colour changes

`canvas_shortcuts.py` contains no colour values. No changes needed in this phase.

---

### 6.9 Visual Overhaul — Dashboard (`src/ui/pages/dashboard.py`)

#### Stat cards

Replace the `_stat_card` helper:
```python
def _stat_card(label: str, value: str) -> None:
    with ui.card().classes("p-4").style(
        "background:var(--ht-bg-surface); min-width:140px; text-align:center;"
        " border-radius:var(--ht-radius-card); border:1px solid var(--ht-border);"
        " box-shadow:var(--ht-shadow-sm);"
        " transition:transform var(--ht-transition-fast),"
        " box-shadow var(--ht-transition-fast);"
    ).classes("ht-stat-card"):
        ui.label(value).style(
            "font-size:2rem; font-weight:700; color:var(--ht-text-primary);"
        )
        ui.label(label).style(
            "font-size:0.75rem; font-weight:600; color:var(--ht-text-secondary);"
            " text-transform:uppercase; letter-spacing:0.5px;"
        )
```

Add hover lift effect via injected CSS (once in `_GLOBAL_CSS`):
```css
.ht-stat-card:hover {
    transform: translateY(-1px);
    box-shadow: var(--ht-shadow-md);
}
```

---

### 6.10 Visual Overhaul — Detail Panels

#### Collapsible accordion sections

Use NiceGUI's `ui.expansion()` (backed by Quasar `QExpansionItem`) for all collapsible
sections in `device_detail_sections.py`, `device_detail_tags_section.py`,
`device_detail_custom_fields_section.py`, and `connection_detail_panel.py`.

```python
with ui.expansion("General Information").classes("w-full ht-accordion-section").props(
    "dense expand-icon-toggle"
).style(
    "border:1px solid var(--ht-border); border-radius:var(--ht-radius-input);"
    " margin-bottom:8px; background:var(--ht-bg-surface);"
):
    # Section content here
```

The Quasar `QExpansionItem` provides:
- Chevron icon toggle (`▾` / `▸`) built-in
- Smooth height transition (Quasar uses CSS `max-height` transition internally)
- `expand-icon-toggle` prop limits the toggle click target to the icon only (not the full
  header), allowing future header click areas (e.g. edit button) without conflict

Style the expansion header label to match the "section heading" typography token:
```css
.ht-accordion-section .q-item__label {
    font-size: 0.875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--ht-text-secondary);
}
```

Inject this rule in `_GLOBAL_CSS`.

#### Form fields inside sections

All form field label + input pairs should follow:
```python
with ui.column().classes("w-full gap-1"):
    ui.label("Field Label").style(
        "font-size:0.75rem; font-weight:500; color:var(--ht-text-secondary);"
    )
    ui.input(...).style(
        "border:1px solid var(--ht-border); border-radius:var(--ht-radius-input);"
        " background:var(--ht-bg-surface); color:var(--ht-text-primary);"
    )
```

#### Tag pills in detail panel (`device_detail_tags_section.py`)

```python
# For each tag with { "name": "...", "color": "#rrggbb" }
with ui.chip(tag["name"]).style(
    f"background-color:{tag['color']}26;"   # 15% opacity hex-alpha
    f" color:{tag['color']};"
    " border-radius:var(--ht-radius-pill); font-size:0.75rem;"
):
    pass
```

> The `26` hex suffix produces ~15% opacity. This is a data-driven colour (from the tag's
> stored hex), not a theme token, so CSS var is not applicable here.

---

### 6.11 Visual Overhaul — Inventory Table (`src/ui/pages/inventory.py`)

Apply alternating row stripes via CSS classes injected in `_GLOBAL_CSS`:

```css
.ht-table-row-even { background: var(--ht-bg-surface); }
.ht-table-row-odd  { background: var(--ht-bg-surface-raised); }
.ht-table-row-even:hover,
.ht-table-row-odd:hover {
    background: var(--ht-accent-glow);
    transition: background var(--ht-transition-fast);
}
```

Apply `.ht-table-row-even` and `.ht-table-row-odd` classes to alternating row containers
in `inventory.py` and `inventory_helpers.py`.

---

### 6.12 Canvas Node Visual Overhaul

Node shape changes per story (workflow-builder rounded rectangle aesthetic) are canvas
style changes handled in `canvas_styles.py`:

- **Shape**: Override default from `data(shape)` to `round-rectangle` for most device
  types. Only `DeviceType.VM` and `DeviceType.LXC` keep `ellipse`. Update `DEVICE_SHAPES`
  in `tokens.py` to change shapes.

  > Note: `DEVICE_SHAPES` changes affect the topology canvas only, not the data model.

- **Label**: Two-line label via Cytoscape's `content` function (requires Cytoscape label
  line-break or `text-wrap: wrap` style). The exact multi-line label implementation should
  be determined by Feature-Engineer during implementation — Cytoscape supports
  `text-wrap: wrap` and `text-max-width: 80px` for wrapping. The subtitle (device type,
  12px muted) uses `label` mapped to `data(subtitle)` on a separate element class, or
  Cytoscape's built-in label with newline (`\n`) in the label data.

- **Edge label pill**: Add a Cytoscape edge label style with background (`text-background-color`,
  `text-background-opacity`, `text-background-padding`, `text-background-shape: round-rectangle`)
  to render label on a surface-coloured pill.

  ```json
  {
    "selector": "edge[label]",
    "style": {
      "label":                   "data(label)",
      "font-size":               "11px",
      "text-background-color":   "<t['bg_surface']>",
      "text-background-opacity": 1,
      "text-background-padding": "4px",
      "text-background-shape":   "roundrectangle",
      "text-border-color":       "<t['border']>",
      "text-border-opacity":     1,
      "text-border-width":       1,
      "color":                   "<t['text_primary']>"
    }
  }
  ```

  Add this rule to `build_theme_style_json`.

---

### 6.13 `_GLOBAL_CSS` — complete injected stylesheet

All of the CSS rules introduced above (`@keyframes htFadeIn`, `.ht-page-content`,
`.ht-nav-item:hover`, `.ht-stat-card:hover`, `.ht-accordion-section .q-item__label`,
`.ht-table-row-*`, etc.) must be collected into a single `_GLOBAL_CSS` string constant in
`app_shell.py` and injected once per page load via `ui.add_head_html(_GLOBAL_CSS)`. This
keeps all design-system-level CSS rules in one auditable location. No CSS rules should be
injected by individual page files.

---

## 7. Security Boundaries

- Theme name is read from `app.storage.user['theme']` — a NiceGUI server-side session dict,
  not from URL parameters or request headers. No client-controlled injection risk.
- The theme name value is used only to key into `THEMES` dict. Invalid theme names fall
  back to `"dark"` via `.get(theme_name, THEMES["dark"])`. No dynamic code execution from
  the theme name.
- CSS custom property values from `THEMES` are hardcoded Python strings. They are never
  sourced from user input, database records, or request bodies. No XSS via CSS injection
  risk.
- `build_theme_style_json` outputs `json.dumps(list)` — safe serialisation, no f-string
  interpolation of user data.

---

## 8. Files to Create / Modify

### Phase 0 — Token layer (no visible change)
| File | Action | Change |
|---|---|---|
| `src/ui/design/tokens.py` | Modify | Add `THEMES`, `STATIC_CSS_VARS`; update `COLOR_*` aliases |
| `src/ui/design/theme_engine.py` | **Create** | `build_css_var_dict`, `get_initial_theme_css`, `get_theme_js_helpers`, `apply_theme_to_client` |
| `src/ui/design/__init__.py` | Modify | Re-export new public symbols if needed |

### Phase 1 — CSS var injection (foundation, no component changes)
| File | Action | Change |
|---|---|---|
| `src/ui/components/app_shell.py` | Modify | Inject `get_initial_theme_css`, `_GLOBAL_CSS`, `get_theme_js_helpers` in context manager |
| `src/ui/pages/login.py` | Modify | Inject dark theme CSS vars, convert body style |
| `src/ui/pages/access_denied.py` | Modify | Inject dark theme CSS vars, convert body style |

### Phase 2 — Theme switcher
| File | Action | Change |
|---|---|---|
| `src/ui/components/app_shell.py` | Modify | Add Theme submenu, `_handle_theme_change` handler |

### Phase 3 — Canvas Cytoscape sync
| File | Action | Change |
|---|---|---|
| `src/ui/components/canvas_styles.py` | Modify | Add `build_theme_style_json`, update `CANVAS_STYLE_JS` alias |
| `src/ui/components/canvas.py` | Modify | Add `updateCyTheme` JS, use `build_theme_style_json` at init, switch `#cy` bg to CSS var |
| `src/ui/components/canvas_tooltip.py` | Modify | Remove `.replace()` anti-pattern; use `window._htThemeColors()` in JS |
| `src/ui/components/canvas_zoom.py` | Modify | Remove f-string `_BTN_STYLE`; replace hardcoded hex in modal JS |

### Phase 4 — Component `COLOR_*` → `var(--ht-*)` migration
| File | Action | Change |
|---|---|---|
| `src/ui/components/app_shell.py` | Modify | Convert all remaining `COLOR_*` f-strings |
| `src/ui/components/device_detail_panel.py` | Modify | Convert `COLOR_*` f-strings |
| `src/ui/components/connection_detail_panel.py` | Modify | Convert `COLOR_*` f-strings |
| `src/ui/components/device_detail_sections.py` | Modify | Convert `COLOR_*` f-strings |
| `src/ui/components/device_detail_tags_section.py` | Modify | Convert |
| `src/ui/components/device_detail_custom_fields_section.py` | Modify | Convert |
| `src/ui/components/device_detail_connections_section.py` | Modify | Convert |
| `src/ui/components/device_panel_helpers.py` | Modify | Convert |
| `src/ui/components/device_palette.py` | Modify | Convert |
| `src/ui/components/device_detail_duplicate.py` | Modify | Audit + convert |
| `src/ui/components/inventory_edit_modal.py` | Modify | Convert |
| `src/ui/components/location_modal.py` | Modify | Convert |
| `src/ui/components/topology_layout_bar.py` | Modify | Convert |
| `src/ui/pages/dashboard.py` | Modify | Convert + stat card visual overhaul |
| `src/ui/pages/inventory.py` | Modify | Convert + alternating rows |
| `src/ui/pages/inventory_helpers.py` | Modify | Convert (except data-driven `tcolor`) |
| `src/ui/pages/topology.py` | Modify | Convert |
| `src/ui/pages/settings_profile.py` | Modify | Convert |
| `src/ui/pages/settings_about.py` | Modify | Convert |
| `src/ui/pages/settings_locations.py` | Modify | Convert (notify calls → Quasar colour names) |
| `src/ui/pages/settings_users.py` | Modify | Convert (notify calls → Quasar colour names) |
| `src/ui/pages/settings_data.py` | Modify | Convert |
| `src/ui/pages/device_edit.py` | Modify | Convert |

### Phase 5 — Visual overhaul
| File | Action | Change |
|---|---|---|
| `src/ui/components/app_shell.py` | Modify | 48px header, sidebar card-style items, accent bar, hover transition via `.ht-nav-item` class |
| `src/ui/components/device_detail_sections.py` | Modify | Accordion sections with `ui.expansion()` |
| `src/ui/components/device_detail_tags_section.py` | Modify | Pill chips with tag-colour tint |
| `src/ui/components/device_detail_panel.py` | Modify | Accordion wrapper |
| `src/ui/components/connection_detail_panel.py` | Modify | Accordion wrapper |
| `src/ui/pages/dashboard.py` | Modify | Stat card radius/border/shadow/hover |
| `src/ui/pages/inventory.py` | Modify | Alternating row classes |
| `src/ui/components/canvas_styles.py` | Modify | Edge label pill, node shape/typography |
| `src/ui/design/tokens.py` | Modify | Update `DEVICE_SHAPES` for rounded rectangles |

### Phase 6 — Login visual overhaul
| File | Action | Change |
|---|---|---|
| `src/ui/pages/login.py` | Modify | Full CSS var conversion, card radius/border/shadow to match design system |

---

## 9. Validation

### Which tests validate this design

| Test | Validates |
|---|---|
| `tests/unit/test_theme_engine.py` *(new)* | `build_css_var_dict` returns correct keys for all three themes; `get_initial_theme_css` returns valid `<style>` string containing `:root`; missing theme name falls back to `"dark"` |
| `tests/unit/test_tokens.py` *(new)* | All three `THEMES` dicts contain all required keys; `STATIC_CSS_VARS` contains all radius/transition/font keys; `COLOR_*` aliases point to dark theme values |
| `tests/unit/test_canvas_styles.py` *(new)* | `build_theme_style_json("dark")` produces valid JSON; output differs between themes (at least one colour value differs); all `DeviceType` values have a per-selector colour rule |
| Existing `tests/unit/test_devices.py` | Must still pass — `DEVICE_TYPE_COLORS` and `DEVICE_SHAPES` are unchanged |
| `tests/e2e/test_theme_switch.py` *(new)* | Playwright: select "Light" theme → assert `document.documentElement.style.getPropertyValue('--ht-bg-base')` equals `#f8fafc`; reload → assert theme still "light" |

### Pre-push gate

```bash
docker compose exec api pytest tests/unit/
docker compose exec api mypy src/ --ignore-missing-imports
docker compose build
```

No new type: `Any` anywhere. `theme_name` parameters typed as `str` throughout.
