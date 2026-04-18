---
name: canvas-bridge
description: Guides adding or modifying Cytoscape.js topology-canvas or Leaflet map behavior in Hometower's NiceGUI UI. Use whenever a task touches src/ui/components/canvas*.py, map_view.py, or requires Python-to-JS bridging via ui.add_body_html or ui.run_javascript. Covers the one-way data flow, file-role separation, view/edit mode gating, HT_READONLY enforcement, and the recipe for adding a canvas interaction end-to-end.
---

# canvas-bridge

The canvas is the most LLM-hostile area of the codebase: Python generates JS strings, NiceGUI mounts them, Cytoscape emits events, Python handles them. This skill captures the conventions so you don't rediscover them every task.

## Mental model

```
DB records
  └─ topology_data.py → dict → JSON
      └─ canvas_js.py (JS string constants)
          └─ ui.add_body_html() mounts into page
              └─ Cytoscape renders nodes/edges
                  └─ canvas_events.py handles cy.on(...)
                      └─ calls service layer
                          └─ re-reads DB, pushes JSON via ui.run_javascript()
```

One-way data flow. The DB is source of truth. JS never mutates Python state directly — it emits an event that Python handles and re-renders.

## File roles (do not repurpose)

| File | Responsibility |
|---|---|
| `canvas.py` | NiceGUI component — mounts container, wires events. Keep <200 lines. |
| `canvas_js.py` | JS string constants. IIFEs that attach `window.ht*` functions. No DOM logic in Python. |
| `canvas_js_helpers.py` | JS helper strings for layout, selection, animation. |
| `canvas_js_utils.py` | JS string utilities (formatters, coord math). |
| `canvas_events.py` | Python handlers for Cytoscape-emitted events (node tap, edge create, drag end). |
| `canvas_container_events.py` | Events specific to compound/container nodes. |
| `canvas_mode.py` | View vs. edit mode toggle. Default is view-only. |
| `canvas_shortcuts.py` | Keyboard shortcuts. **Every write shortcut checks `HT_READONLY`**. |
| `canvas_styles.py` | Cytoscape stylesheet. Colors from `src/ui/design/tokens.py` — never hardcoded. |
| `canvas_zoom.py`, `canvas_tooltip.py` | Standalone concerns. |
| `src/ui/services/topology_data.py` | DB → Cytoscape-shaped dict. UI helper, not a backend service. |

## Adding a new canvas interaction

1. **Define the JS entrypoint** in `canvas_js.py` (or a new `canvas_js_*.py`):
   ```python
   MY_FEATURE_JS: str = """(function() {
     window.htMyFeature = function(arg) {
       const cy = window.htCy;
       // read-only side of the interaction
     };
   })();"""
   ```
2. **Inject it** in `canvas.py` via `ui.add_body_html(f"<script>{MY_FEATURE_JS}</script>")` alongside existing injections.
3. **Wire the event** in `canvas_events.py`:
   ```python
   cy.on("tap", "node", lambda evt: _handle_my_feature(evt, ...))
   ```
4. **Gate by mode** in `canvas_mode.py` if it's a write. Readers must never trigger writes.
5. **Call the service** (not the repository). Example: `device_service.update(...)`. Services own the commit.
6. **Re-render** via `await ui.run_javascript("htApplyPatch(...)")` with fresh data from `topology_data.py`.

## Readonly / RBAC enforcement

- Source of truth for "can this user edit?" is the JWT-derived `current_user.role` on the server, **not** a JS flag.
- `HT_READONLY` in JS is a UX hint only. Always validate again in the Python service layer — the canvas can be manipulated via devtools.
- `canvas_shortcuts.py` must early-return on any write shortcut when `HT_READONLY` is set.
- `canvas_mode.py` default is `view`. Entering `edit` requires `Contributor` or `Admin`.

## Common pitfalls

- **Mutating Cytoscape directly from a Python handler** — don't. Call the service, then push new state via `htApplyPatch`.
- **Hardcoding hex colors in JS strings** — read tokens in Python and interpolate: `f"color: '{tokens.PRIMARY}'"`.
- **Putting DOM logic in Python** — Python should never build HTML strings for Cytoscape nodes. Rendering lives in JS.
- **Forgetting compound nodes** — containers use Cytoscape's native `data.parent`. Do not invent a parallel grouping scheme.
- **Leaflet map**: same embedding pattern (`ui.add_body_html` + `ui.run_javascript`). OSM tiles, no API key. Markers from `Location.lat`/`lng`. Click marker → sidebar shows devices at that location.

## Verification

After any canvas change:
1. `bash .claude/skills/verify-gate/scripts/run.sh --fast` — arch-grep catches stray repo imports in `src/ui/`.
2. Manually open the topology page and confirm: view-mode cannot write, edit-mode can, undo/redo work, keyboard shortcuts respect readonly.
3. Browser devtools console should show no unhandled Cytoscape errors.
