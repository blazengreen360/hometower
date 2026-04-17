# RFC-001 Part 4: UI and Canvas Integration

**Parts:** [Part 1 – System Overview](rfc-001-part1-system-overview.md) · [Part 2 – Data Model](rfc-001-part2-data-model.md) · [Part 3 – API Layer](rfc-001-part3-api-layer.md) · [Part 4 (this)] · [Part 5 – Auth & Ops](rfc-001-part5-auth-ops.md)

---

## 1. NiceGUI + FastAPI Unified Process

NiceGUI wraps FastAPI internally. `ui.run_with(app)` mounts the NiceGUI WebSocket server onto the existing FastAPI app. Both serve from a single port (8080). There is no CORS configuration because the browser only communicates with one origin.

```
Port 8080
├── /api/*          → FastAPI routers (REST + Pydantic)
├── /docs           → FastAPI OpenAPI UI
├── /_nicegui/*     → NiceGUI WebSocket + static assets
├── /login          → NiceGUI login page
├── /topology       → NiceGUI topology canvas page
├── /map            → NiceGUI map page
├── /inventory      → NiceGUI inventory list page
└── /admin          → NiceGUI admin user panel page
```

NiceGUI pages use `@ui.page("/path")` decorators defined in `src/ui/pages/*.py`.
Pages check auth state before rendering; unauthenticated users are redirected to `/login`.

---

## 2. Cytoscape.js Integration — `src/ui/components/canvas.py`

### 2.1 Embedding Pattern

```python
# src/ui/components/canvas.py
from nicegui import ui, app
import json

CYTOSCAPE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"

def render_canvas(elements: list[dict], layout_json: dict | None) -> None:
    ui.add_head_html(f'<script src="{CYTOSCAPE_CDN}"></script>')
    ui.add_body_html(
        '<div id="cy" style="width:100%;height:calc(100vh - 60px);"></div>'
    )
    elements_json = json.dumps(elements)
    layout_json_str = json.dumps(layout_json or {})
    ui.run_javascript(f"initCanvas({elements_json}, {layout_json_str})")
```

### 2.2 JavaScript Initialization Template

```javascript
// Injected via ui.add_body_html() or a static JS file loaded by the page
function initCanvas(elements, savedLayout) {
    window.cy = cytoscape({
        container: document.getElementById('cy'),
        elements: elements,
        style: [
            { selector: 'node', style: { label: 'data(label)', shape: 'data(shape)' }},
            { selector: 'edge', style: { 'curve-style': 'bezier', 'target-arrow-shape': 'triangle' }}
        ],
        layout: Object.keys(savedLayout).length ? { name: 'preset' } : { name: 'cose' }
    });
    if (Object.keys(savedLayout).length) {
        cy.json(savedLayout);
    }
    registerEventHandlers();
}
```

### 2.3 Data Flow: DB → Python → JSON → Cytoscape Elements

```python
# src/ui/pages/topology.py
def build_cytoscape_elements(devices: list[Device], connections: list[Connection]) -> list[dict]:
    nodes = [
        {"group": "nodes", "data": {"id": str(d.id), "label": d.name,
         "type": d.type.value, "shape": DEVICE_SHAPES[d.type]}}
        for d in devices
    ]
    edges = [
        {"group": "edges", "data": {"id": str(c.id), "source": str(c.source_id),
         "target": str(c.target_id), "label": c.label or ""}}
        for c in connections
    ]
    return nodes + edges
```

Device shape mapping in `src/ui/design/tokens.py`:
```python
DEVICE_SHAPES: dict[DeviceType, str] = {
    DeviceType.Server: "rectangle",
    DeviceType.Switch: "diamond",
    DeviceType.Router: "triangle",
    DeviceType.NAS: "hexagon",
    DeviceType.VM: "ellipse",
    DeviceType.Docker: "round-rectangle",
    DeviceType.VLAN: "barrel",  # fallback to rectangle if unsupported
    ...
}
```

### 2.4 JavaScript Event Bridge (JS → Python)

All JS → Python communication goes through the FastAPI REST API. JavaScript calls `fetch()` directly against `/api/...` endpoints. The JWT token is stored in `sessionStorage` and attached to every request.

```javascript
// Dragging a device from the palette onto the canvas
function onPaletteDrop(event, deviceType) {
    const pos = cy.renderer().projectIntoViewport(event.clientX, event.clientY);
    const token = sessionStorage.getItem('access_token');
    fetch('/api/devices', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
        body: JSON.stringify({name: 'New ' + deviceType, type: deviceType})
    })
    .then(r => r.json())
    .then(device => {
        cy.add({group: 'nodes', data: {id: device.id, label: device.name,
                type: device.type, shape: DEVICE_SHAPES[device.type]},
                position: {x: pos[0], y: pos[1]}});
    });
}
```

### 2.5 Python → JavaScript Commands

Use `ui.run_javascript()` when Python needs to update the canvas state (e.g., after a successful import):

```python
# Add a node after server-side creation
await ui.run_javascript(
    f"cy.add({{group:'nodes', data:{{id:'{device.id}', label:'{device.name}', "
    f"type:'{device.type.value}'}}, position:{{x:{x}, y:{y}}}}});"
)
```

### 2.6 Position Persistence Strategy

- **Positions live in `diagram_layouts.cytoscape_json`**, not on the `Device` model.
- On `dragfree` (node stop moving), canvas updates in-memory only.
- "Save Layout" button triggers: `cy.json()` → `POST /api/diagrams {name, cytoscape_json}`.
- On page load: fetch most-recently-updated layout → `cy.json(layout)` to restore positions.
- If no saved layout exists, Cytoscape's `cose` auto-layout is applied.

### 2.7 Node Click → Detail Panel

```javascript
cy.on('tap', 'node', function(event) {
    const deviceId = event.target.id();
    // Notify Python via a custom signal approach: POST to a dedicated endpoint,
    // or store in a NiceGUI-accessible variable via a tiny internal endpoint.
    fetch('/api/devices/' + deviceId, {
        headers: {'Authorization': 'Bearer ' + sessionStorage.getItem('access_token')}
    })
    .then(r => r.json())
    .then(device => {
        // Dispatch custom DOM event; NiceGUI JS bridge can listen or
        // Python polls / uses NiceGUI's ui.timer for sidebar updates
        window.dispatchEvent(new CustomEvent('ht:node-selected', {detail: device}));
    });
});
```

In Python, a `ui.timer` or native NiceGUI event binding can respond to `ht:node-selected` to update the sidebar component.

### 2.8 XSS Mitigation — Label Rendering Safety

**Cytoscape.js renders node and edge labels as plain text by default.** The `label: 'data(label)'` style selector passes label content through Cytoscape's internal text renderer, which writes to an HTML5 Canvas element using `ctx.fillText()`. Canvas `fillText()` has no concept of HTML — it renders the string literally, so `<script>alert(1)</script>` appears as visible text, not executable code. **This path is safe against XSS without any additional sanitization.**

However, if a future implementation uses Cytoscape's `content` style with `'html'` rendering (e.g., a custom renderer plugin), label values **must** be sanitized with [DOMPurify](https://github.com/cure53/DOMPurify) before being passed to the renderer:

```javascript
// REQUIRED if HTML label rendering is ever enabled:
// import DOMPurify from 'dompurify';
const safeLabel = DOMPurify.sanitize(device.name);
```

**Phase 1 constraint:** Custom HTML label rendering is **not used**. If introduced in a future phase, a security review is required and DOMPurify must be added to the bundle. This note exists as a defense-in-depth reminder for the homelab context where user-supplied device names are displayed on the canvas.

---

## 3. Leaflet.js Integration — `src/ui/components/map_component.py`

### 3.1 Embedding Pattern

```python
LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

def render_map(geo_locations: list[dict], devices_by_location: dict[str, list[dict]]) -> None:
    ui.add_head_html(f'<link rel="stylesheet" href="{LEAFLET_CSS}">'
                     f'<script src="{LEAFLET_JS}"></script>')
    ui.add_body_html('<div id="map" style="width:100%;height:calc(100vh - 60px);"></div>')
    locations_json = json.dumps(geo_locations)
    devices_json   = json.dumps(devices_by_location)
    ui.run_javascript(f"initMap({locations_json}, {devices_json})")
```

### 3.2 JavaScript Initialization Template

```javascript
function initMap(locations, devicesByLocation) {
    window.leafletMap = L.map('map').setView([20, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(leafletMap);

    locations.forEach(loc => {
        const marker = L.marker([loc.lat, loc.lng])
            .addTo(leafletMap)
            .bindPopup(loc.name);
        marker.on('click', () => {
            window.dispatchEvent(new CustomEvent('ht:marker-clicked',
                {detail: {locationId: loc.id, devices: devicesByLocation[loc.id] || []}}));
        });
    });
}
```

### 3.3 Add Marker After POST

```python
# After POST /api/locations succeeds, Python pushes new marker to JS
await ui.run_javascript(
    f"addMapMarker({{id:'{loc.id}', lat:{loc.lat}, lng:{loc.lng}, name:'{loc.name}'}});"
)
```

---

## 4. NiceGUI Page Structure

### Auth guard pattern

```python
# src/ui/pages/topology.py
from nicegui import ui, app

@ui.page("/topology")
async def topology_page():
    token = app.storage.user.get("access_token")
    if not token:
        ui.navigate.to("/login")
        return
    # render page content
```

### Login flow

```python
# src/ui/pages/login.py
@ui.page("/login")
async def login_page():
    async def do_login():
        response = await http_client.post("/api/auth/login",
                                          json={"email": email.value, "password": pw.value})
        if response.status_code == 200:
            token = response.json()["access_token"]
            app.storage.user["access_token"] = token
            ui.navigate.to("/topology")
        else:
            ui.notify("Invalid credentials", color="negative")
```

### Auth State Synchronization

`app.storage.user` is NiceGUI's **server-side per-session storage**, keyed by a browser cookie that NiceGUI manages automatically. It persists across page reloads because it lives on the server, not in the browser.

**Lifecycle of the JWT across both storage layers:**

1. **Login success** — The Python handler stores the token server-side: `app.storage.user["access_token"] = token`. It then calls `ui.run_javascript(f"sessionStorage.setItem('access_token', '{token}')")` so that inline `fetch()` calls in JavaScript can attach the `Authorization: Bearer …` header directly.

2. **Page reload** — `app.storage.user` is already populated on the server. The page boot sequence repopulates `sessionStorage` with `ui.run_javascript(...)` before any JS canvas or map code runs, ensuring `fetch()` has a token without requiring a re-login.

3. **Token expiry** — Any API call that returns `401` triggers a JS handler that calls `sessionStorage.removeItem('access_token')` and redirects to `/login`. The Python auth guard (`app.storage.user.get("access_token")`) performs the same check server-side and redirects unauthenticated page loads before rendering.

4. **Logout** — `POST /api/auth/logout` handler clears the server-side store: `app.storage.user.clear()`. JavaScript simultaneously calls `sessionStorage.removeItem('access_token')` and navigates to `/login`. Both layers are cleared atomically from the user's perspective.

> **Security note:** JWT tokens are **never written to Loguru logs**. `sessionStorage` is tab-scoped and cleared when the browser tab closes — it does not persist to `localStorage`.

---

## 5. Design System — `src/ui/design/tokens.py`

```python
# Colors
PRIMARY   = "#6366f1"   # Indigo
SUCCESS   = "#22c55e"
WARNING   = "#f59e0b"
DANGER    = "#ef4444"
BG_DARK   = "#0f172a"
BG_LIGHT  = "#f8fafc"
SURFACE   = "#1e293b"   # Dark mode card background

# Typography
FONT_MONO = "JetBrains Mono, monospace"

# Spacing (rem units)
SPACING_SM = "0.5rem"
SPACING_MD = "1rem"
SPACING_LG = "2rem"
```

No hardcoded colors elsewhere in `src/ui/`. All components import from `tokens.py`.
