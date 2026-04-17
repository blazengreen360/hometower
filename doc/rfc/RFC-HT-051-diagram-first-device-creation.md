# RFC: Diagram-First Device Creation — Type Palette, Draft State, Publish

**Story:** HT-051 · **Status:** Draft · **Date:** 2026-04-12
**Author:** Architect

---

## 1. Overview

Users drag a device type from the palette onto the canvas, fill in a floating form, and a **draft** node appears on the View. Drafts live exclusively inside the View's `cytoscape_json`—no database record exists until the user explicitly **Publishes** a draft, at which point an individual `POST /api/devices/` creates the inventory record and the node transitions to a published state. This inverts the current inventory-first flow into a diagram-first workflow where the canvas drives the inventory.

## 2. Hidden Design Decisions (Parnas Test)

| Module | Hides |
|---|---|
| `src/ui/components/canvas_draft.py` (new) | Draft element schema, ID convention (`draft-{uuid}`), draft ↔ published transition logic in JS — if the draft data shape changes, only this file is touched |
| `src/ui/components/canvas_draft_form.py` (new) | The on-drop popover form HTML/JS — input fields, validation, positioning, submit/cancel flow |
| `src/ui/components/canvas_draft_publish.py` (new) | The Publish flow JS — API call, ID swap, connection promotion, error handling on the node |
| `src/ui/services/topology_data.py` (modified) | The decision to load only opt-in devices whose UUIDs appear in `cytoscape_json` instead of all inventory devices |
| `src/ui/components/canvas_styles.py` (modified) | The visual representation of draft nodes (dashed border, muted fill, "Draft" pill) |
| `src/ui/components/canvas_events.py` (modified) | The `ht:palette-drop` handler routes to local draft creation instead of `POST /api/devices/` |

## 3. Data Model Changes

**No database migrations required.** Drafts exist only inside `cytoscape_json` (a JSON column on `DiagramLayout`). The existing autosave (`_htFlushAutosave`) already persists the full Cytoscape JSON, so draft elements are automatically saved and restored on page reload.

### 3.1 Draft Element Schema (inside `cytoscape_json`)

A draft device is a Cytoscape node element with the following `data` fields:

```json
{
  "data": {
    "id": "draft-550e8400-e29b-41d4-a716-446655440000",
    "label": "my-server",
    "raw_name": "my-server",
    "shape": "rectangle",
    "device_type": "Server",
    "raw_device_type": "Server",
    "status": "Active",
    "ip": "192.168.1.10",
    "mac": "",
    "os": "Ubuntu 24.04",
    "notes": "",
    "draft": true,
    "draft_name": "my-server",
    "draft_type": "Server",
    "draft_ip": "192.168.1.10",
    "draft_mac": "",
    "draft_os": "Ubuntu 24.04",
    "draft_notes": ""
  },
  "position": { "x": 320, "y": 180 },
  "classes": "draft"
}
```

**Field semantics:**

| Field | Type | Purpose |
|---|---|---|
| `id` | `string` | `"draft-"` + client-generated UUID v4. Prefix enables easy detection. |
| `label` / `raw_name` | `string` | Display name — kept in sync with `draft_name` for rendering consistency |
| `shape` / `device_type` / `raw_device_type` | `string` | Standard Cytoscape display fields, populated from the dragged type |
| `status` | `string` | Always `"Active"` for new drafts |
| `ip`, `mac`, `os`, `notes` | `string` | Standard display fields, populated from form |
| `draft` | `boolean` | `true` = this node is a draft. Removed on publish. |
| `draft_name` | `string` | Authoritative draft name (persisted to `cytoscape_json`) |
| `draft_type` | `string` | Authoritative draft type |
| `draft_ip`, `draft_mac`, `draft_os`, `draft_notes` | `string` | Authoritative draft field values |
| `classes` | `string` | `"draft"` — used for Cytoscape style selectors and `.draft` class queries |

**ID convention:** All draft IDs start with `"draft-"`. This prefix:
- Enables `topology_data.py` to skip these IDs when fetching published devices from the API
- Enables `_isDraft(id)` helper: `return typeof id === 'string' && id.indexOf('draft-') === 0`
- Is replaced with the server-assigned UUID after successful publish

**Coexistence with published elements:** Draft and published nodes coexist in the same `cytoscape_json.elements` array. Published nodes have real UUIDs as IDs and no `draft` data field. The `draft` CSS class drives visual differentiation.

### 3.2 Draft Connection Schema

Connections involving at least one draft endpoint are stored as local-only edges:

```json
{
  "group": "edges",
  "data": {
    "id": "draft-edge-<uuid>",
    "source": "draft-550e8400-...",
    "target": "a1b2c3d4-...",
    "label": "",
    "raw_label": "",
    "connection_type": "Ethernet",
    "draft_edge": true
  }
}
```

A `draft_edge: true` flag marks edges that have not been persisted to `POST /api/connections/`. After both endpoints are published, the Publish flow promotes the edge.

## 4. Domain Logic

No new domain functions required. Drafts are purely a UI/client-side concept. The existing domain validation in `DeviceBase` (name, IP, MAC validators) is enforced server-side when `POST /api/devices/` is called during Publish.

**Invariant:** Draft data is never sent to any service or repository layer. The only server interaction is when Publish calls the existing `POST /api/devices/` and `POST /api/connections/` endpoints.

## 5. Service Layer

No changes to `device_service.py` or `connection_service.py`. Publish reuses:
- `POST /api/devices/` (existing) — creates the device in inventory
- `POST /api/connections/` (existing) — creates the connection after both endpoints are published

## 6. API Layer

**No new endpoints.** Publish uses existing endpoints:

| Action | Endpoint | RBAC | Notes |
|---|---|---|---|
| Publish draft device | `POST /api/devices/` | Contributor+ | Sends `DeviceCreate` payload from draft data |
| Create promoted connection | `POST /api/connections/` | Contributor+ | After both endpoints are published UUIDs |

The existing `POST /api/devices/` signature:
```python
@router.post("/", status_code=201, response_model=DeviceResponse,
             dependencies=[Depends(require_role(Role.Contributor))])
async def create_device(data: DeviceCreate, session=Depends(get_session)) -> DeviceResponse:
```

DeviceCreate fields (`name`, `type`, `status`, `ip`, `mac`, `os`, `notes`, `location_id`, `parent_id`) map directly from draft data.

## 7. UI Layer

### 7.1 `src/ui/components/canvas_draft.py` (NEW — ~80 lines)

JS constants for draft element creation and helper functions.

```python
"""Draft device element helpers for the Cytoscape.js canvas.

Hides the draft element schema (ID convention, data fields, CSS class)
so that if the draft data shape changes, only this file is touched.
"""

CANVAS_DRAFT_JS = """
(function() {
    /**
     * Returns true when the given Cytoscape element ID belongs to a draft device.
     */
    window._htIsDraft = function(id) {
        return typeof id === 'string' && id.indexOf('draft-') === 0;
    };

    /**
     * Returns true when the given Cytoscape edge has at least one draft endpoint.
     */
    window._htIsDraftEdge = function(edgeData) {
        return !!(edgeData && edgeData.draft_edge);
    };

    /**
     * Generate a draft element ID.
     */
    window._htDraftId = function() {
        return 'draft-' + crypto.randomUUID();
    };

    /**
     * Build a Cytoscape node definition for a draft device.
     * @param {Object} opts - {id, name, type, ip, mac, os, notes, shape, x, y}
     * @returns {Object} Cytoscape element definition
     */
    window._htBuildDraftNode = function(opts) {
        var escapedName = _escapeHtml(opts.name || '');
        var escapedType = _escapeHtml(opts.type || '');
        return {
            data: {
                id: opts.id,
                label: escapedName,
                raw_name: opts.name || '',
                shape: opts.shape || 'rectangle',
                device_type: escapedType,
                raw_device_type: opts.type || '',
                status: 'Active',
                ip: _escapeHtml(opts.ip || ''),
                mac: _escapeHtml(opts.mac || ''),
                os: _escapeHtml(opts.os || ''),
                notes: _escapeHtml(opts.notes || ''),
                draft: true,
                draft_name: opts.name || '',
                draft_type: opts.type || '',
                draft_ip: opts.ip || '',
                draft_mac: opts.mac || '',
                draft_os: opts.os || '',
                draft_notes: opts.notes || ''
            },
            position: { x: opts.x || 200, y: opts.y || 200 },
            classes: 'draft'
        };
    };

    /**
     * Update a draft node's data fields in-place from edited form values.
     */
    window._htUpdateDraftData = function(node, fields) {
        if (!node || !node.length) return;
        var d = node.data();
        if (fields.name !== undefined) {
            node.data('draft_name', fields.name);
            node.data('raw_name', fields.name);
            node.data('label', _escapeHtml(fields.name));
        }
        if (fields.type !== undefined) {
            node.data('draft_type', fields.type);
            node.data('raw_device_type', fields.type);
            node.data('device_type', _escapeHtml(fields.type));
        }
        if (fields.ip !== undefined)    { node.data('draft_ip', fields.ip);       node.data('ip', _escapeHtml(fields.ip)); }
        if (fields.mac !== undefined)   { node.data('draft_mac', fields.mac);     node.data('mac', _escapeHtml(fields.mac)); }
        if (fields.os !== undefined)    { node.data('draft_os', fields.os);       node.data('os', _escapeHtml(fields.os)); }
        if (fields.notes !== undefined) { node.data('draft_notes', fields.notes); node.data('notes', _escapeHtml(fields.notes)); }
    };

    /**
     * Return the count of draft nodes currently on the canvas.
     */
    window._htDraftCount = function() {
        return window._cy ? window._cy.nodes('.draft').length : 0;
    };
})();
"""
```

**Inject via:** `ui.add_body_html(f"<script>{CANVAS_DRAFT_JS}</script>")` in `canvas_events.py` or `topology.py`.

### 7.2 `src/ui/components/canvas_draft_form.py` (NEW — ~100 lines)

The floating on-drop popover form. Injected as JS that creates/destroys a DOM popover when `ht:palette-drop` fires.

```python
"""On-drop creation form — floating popover for draft device details.

Hides the form HTML, validation, positioning, and submit/cancel flow.
"""

CANVAS_DRAFT_FORM_JS = """
(function() {
    /**
     * Show a floating popover at (screenX, screenY) for a new draft device.
     * @param {Object} opts - {deviceType, x, y, screenX, screenY, deviceShapes}
     * @param {Function} onSubmit - called with {name, type, ip, mac, os, notes}
     * @param {Function} onCancel - called with no args
     */
    window._htShowDraftForm = function(opts, onSubmit, onCancel) {
        // Remove any existing form
        var existing = document.getElementById('ht-draft-form');
        if (existing) existing.remove();

        var form = document.createElement('div');
        form.id = 'ht-draft-form';
        form.style.cssText = [
            'position:fixed', 'z-index:10000',
            'background:var(--ht-bg-surface-raised)',
            'border:1px solid var(--ht-border)',
            'border-radius:var(--ht-radius-card)',
            'padding:16px', 'min-width:260px', 'max-width:320px',
            'box-shadow:var(--ht-shadow-lg)',
            'display:flex', 'flex-direction:column', 'gap:10px',
        ].join(';');

        // Position near drop point (clamped to viewport)
        var left = Math.min(opts.screenX || 200, window.innerWidth - 340);
        var top  = Math.min(opts.screenY || 200, window.innerHeight - 380);
        form.style.left = left + 'px';
        form.style.top  = top  + 'px';

        // Title
        var title = document.createElement('div');
        title.style.cssText = 'font-weight:600;color:var(--ht-text-primary);font-size:0.95rem;';
        title.textContent = 'New ' + (opts.deviceType || 'Device');
        form.appendChild(title);

        function makeField(labelText, id, required, value) {
            var wrap = document.createElement('div');
            wrap.style.cssText = 'display:flex;flex-direction:column;gap:2px;';
            var lbl = document.createElement('label');
            lbl.textContent = labelText + (required ? ' *' : '');
            lbl.style.cssText = 'font-size:0.75rem;color:var(--ht-text-secondary);';
            lbl.setAttribute('for', id);
            var inp = document.createElement('input');
            inp.id = id;
            inp.value = value || '';
            inp.style.cssText = 'padding:6px 8px;border-radius:var(--ht-radius-input);border:1px solid var(--ht-border);background:var(--ht-bg-surface);color:var(--ht-text-primary);font-size:0.875rem;';
            if (required) inp.setAttribute('required', 'true');
            wrap.appendChild(lbl);
            wrap.appendChild(inp);
            form.appendChild(wrap);
            return inp;
        }

        var nameInput = makeField('Name', 'ht-draft-name', true, '');
        var typeInput = makeField('Type', 'ht-draft-type', false, opts.deviceType || '');
        typeInput.disabled = true;
        typeInput.style.opacity = '0.7';
        var ipInput   = makeField('IP', 'ht-draft-ip', false, '');
        var macInput  = makeField('MAC', 'ht-draft-mac', false, '');
        var osInput   = makeField('OS', 'ht-draft-os', false, '');
        var notesInput = makeField('Notes', 'ht-draft-notes', false, '');

        // Error message area
        var errDiv = document.createElement('div');
        errDiv.style.cssText = 'color:var(--ht-error);font-size:0.75rem;min-height:1em;';
        form.appendChild(errDiv);

        // Buttons
        var btnRow = document.createElement('div');
        btnRow.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;';
        var cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.style.cssText = 'padding:6px 14px;border-radius:var(--ht-radius-input);border:1px solid var(--ht-border);background:transparent;color:var(--ht-text-secondary);cursor:pointer;font-size:0.8rem;';
        var submitBtn = document.createElement('button');
        submitBtn.textContent = 'Add Draft';
        submitBtn.style.cssText = 'padding:6px 14px;border-radius:var(--ht-radius-input);border:none;background:var(--ht-accent);color:var(--ht-text-on-accent);cursor:pointer;font-size:0.8rem;font-weight:600;';
        btnRow.appendChild(cancelBtn);
        btnRow.appendChild(submitBtn);
        form.appendChild(btnRow);

        document.body.appendChild(form);
        nameInput.focus();

        function cleanup() { form.remove(); }

        function submit() {
            var name = nameInput.value.trim();
            if (!name) { errDiv.textContent = 'Name is required.'; nameInput.focus(); return; }
            cleanup();
            onSubmit({
                name: name,
                type: opts.deviceType || 'Server',
                ip: ipInput.value.trim(),
                mac: macInput.value.trim(),
                os: osInput.value.trim(),
                notes: notesInput.value.trim()
            });
        }

        function cancel() { cleanup(); onCancel(); }

        submitBtn.addEventListener('click', submit);
        cancelBtn.addEventListener('click', cancel);

        nameInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { e.preventDefault(); submit(); }
            if (e.key === 'Escape') { e.preventDefault(); cancel(); }
        });
        form.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { e.preventDefault(); cancel(); }
        });

        // Click outside dismisses
        setTimeout(function() {
            document.addEventListener('mousedown', function dismissOnOutside(e) {
                if (!form.contains(e.target)) {
                    document.removeEventListener('mousedown', dismissOnOutside);
                    cancel();
                }
            });
        }, 50);
    };
})();
"""
```

### 7.3 `src/ui/components/canvas_draft_publish.py` (NEW — ~120 lines)

The Publish flow JS — individual API call per draft, ID swap, connection promotion.

```python
"""Publish a draft device to global inventory.

Hides the API call sequence, element ID replacement, connection
promotion, and error display — if the Publish protocol changes,
only this file is modified.
"""

CANVAS_DRAFT_PUBLISH_JS = """
(function() {
    /**
     * Publish a single draft device to the global inventory.
     * @param {string} draftId — the draft-{uuid} element ID
     * @returns {Promise<boolean>} — true on success
     */
    window._htPublishDraft = function(draftId) {
        var cy = window._cy;
        if (!cy) return Promise.resolve(false);
        var node = cy.getElementById(draftId);
        if (!node.length) return Promise.resolve(false);
        var d = node.data();

        var payload = {
            name:   d.draft_name || d.raw_name,
            type:   d.draft_type || d.raw_device_type,
            ip:     d.draft_ip   || null,
            mac:    d.draft_mac  || null,
            os:     d.draft_os   || null,
            notes:  d.draft_notes || null,
        };
        // Normalise empty strings to null for optional fields (server expects null, not "")
        ['ip','mac','os','notes'].forEach(function(k) {
            if (payload[k] === '') payload[k] = null;
        });

        return fetch('/api/devices/', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function(r) {
            if (!r.ok) return r.json().then(function(b) { throw new Error(b.detail || 'Publish failed'); });
            return r.json();
        })
        .then(function(device) {
            var newId = String(device.id);

            // 1. Update the node's ID and data
            node.data('id', newId);
            // Remove draft-specific fields
            node.removeData('draft');
            node.removeData('draft_name');
            node.removeData('draft_type');
            node.removeData('draft_ip');
            node.removeData('draft_mac');
            node.removeData('draft_os');
            node.removeData('draft_notes');
            // Update display fields from server response
            node.data('label', _escapeHtml(device.name || ''));
            node.data('raw_name', device.name || '');
            node.data('status', _escapeHtml(device.status || 'Active'));
            // Remove draft CSS class
            node.removeClass('draft');

            // 2. Rewrite edges that referenced the old draft ID
            cy.edges().forEach(function(edge) {
                var src = edge.data('source');
                var tgt = edge.data('target');
                if (src === draftId || tgt === draftId) {
                    var newSrc = (src === draftId) ? newId : src;
                    var newTgt = (tgt === draftId) ? newId : tgt;
                    // Cytoscape doesn't allow source/target mutation — recreate
                    var eData = Object.assign({}, edge.data());
                    eData.source = newSrc;
                    eData.target = newTgt;
                    var oldEdgeId = edge.id();
                    edge.remove();
                    cy.add({ group: 'edges', data: eData });
                }
            });

            // 3. Promote eligible local-only connections
            _htPromoteConnections(newId);

            // 4. Flush autosave to persist the ID swap
            if (window._htFlushAutosave) window._htFlushAutosave();

            _notify('Device published to inventory.', 'positive');
            return true;
        })
        .catch(function(err) {
            // Show error on the node (add error class, display toast)
            node.addClass('draft-error');
            _notify('Publish failed: ' + (err.message || 'Unknown error'), 'negative');
            // Remove error class after 5 seconds
            setTimeout(function() { node.removeClass('draft-error'); }, 5000);
            return false;
        });
    };

    /**
     * After publishing, check all edges touching `publishedId`.
     * If both endpoints are now published (neither starts with "draft-"),
     * create the connection via POST /api/connections/.
     */
    function _htPromoteConnections(publishedId) {
        var cy = window._cy;
        if (!cy) return;
        var node = cy.getElementById(publishedId);
        if (!node.length) return;

        node.connectedEdges().forEach(function(edge) {
            if (!edge.data('draft_edge')) return;
            var src = edge.data('source');
            var tgt = edge.data('target');
            // Both must be published (no draft- prefix)
            if (window._htIsDraft(src) || window._htIsDraft(tgt)) return;

            var connType = edge.data('connection_type') || 'Ethernet';
            var connLabel = edge.data('raw_label') || '';

            fetch('/api/connections/', {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_id: src,
                    target_id: tgt,
                    type: connType,
                    label: connLabel || null
                })
            })
            .then(function(r) { return r.ok ? r.json() : null; })
            .then(function(conn) {
                if (!conn) return;
                // Replace the local edge with the server-assigned one
                var eData = Object.assign({}, edge.data());
                edge.remove();
                cy.add({ group: 'edges', data: {
                    id: conn.id,
                    source: conn.source_id,
                    target: conn.target_id,
                    label: _escapeHtml(conn.label || ''),
                    raw_label: conn.label || '',
                    connection_type: conn.type
                }});
            });
        });
    }
})();
"""
```

### 7.4 `src/ui/components/canvas_events.py` (MODIFIED)

**Before** — current `ht:palette-drop` handler (lines ~14–43):
```javascript
document.addEventListener('ht:palette-drop', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    if (!window._cy) return;
    fetch('/api/devices/', {
        method: 'POST',
        // ... creates device immediately via API
    }).then(function(r) { return r.ok ? r.json() : null; })
      .then(function(device) {
        if (!device) return;
        // ... adds node with server-assigned ID
        window._cy.add({ ... });
    });
});
```

**After** — replace with draft creation via form:
```javascript
document.addEventListener('ht:palette-drop', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    if (!window._cy) return;

    // Convert model coords to screen coords for form positioning
    var zoom = window._cy.zoom();
    var pan  = window._cy.pan();
    var container = document.getElementById('cy');
    var rect = container ? container.getBoundingClientRect() : {left:0,top:0};
    var screenX = d.x * zoom + pan.x + rect.left;
    var screenY = d.y * zoom + pan.y + rect.top;

    window._htShowDraftForm({
        deviceType: d.deviceType,
        x: d.x,
        y: d.y,
        screenX: screenX,
        screenY: screenY,
        deviceShapes: deviceShapes
    }, function onSubmit(fields) {
        var draftId = window._htDraftId();
        var shape = deviceShapes[fields.type] || 'rectangle';
        var nodeDefn = window._htBuildDraftNode({
            id: draftId,
            name: fields.name,
            type: fields.type,
            ip: fields.ip,
            mac: fields.mac,
            os: fields.os,
            notes: fields.notes,
            shape: shape,
            x: d.x,
            y: d.y
        });
        window._cy.add(nodeDefn);
        // Trigger autosave to persist the draft to cytoscape_json
        if (window._htAutosaveTimer) clearTimeout(window._htAutosaveTimer);
        window._htAutosaveTimer = setTimeout(window._htFlushAutosave, 800);
    }, function onCancel() {
        // No action needed — form dismissed, no node added
    });
});
```

Also in `canvas_events.py`, update `ht:node-duplicate` to skip duplication for draft nodes:

**Before:**
```javascript
document.addEventListener('ht:node-duplicate', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    // ... always POSTs to /api/devices/
```

**After** — add guard at the top:
```javascript
document.addEventListener('ht:node-duplicate', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    if (!window._cy) return;
    // Draft devices cannot be duplicated
    if (window._htIsDraft && window._htIsDraft(d.id)) {
        _notify('Publish the draft first before duplicating.', 'warning');
        return;
    }
    // ... existing duplication logic unchanged
```

Update `ht:node-delete` to handle draft deletion differently (no API call):

**Before:**
```javascript
document.addEventListener('ht:node-delete', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    // ... always DELETEs via /api/devices/{id}
```

**After:**
```javascript
document.addEventListener('ht:node-delete', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    if (!window._cy) return;

    // Draft device — delete locally only (no API call)
    if (window._htIsDraft && window._htIsDraft(d.id)) {
        var draftName = (d && (d.name || (d.data && (d.data.raw_name || d.data.label)) || d.id)) || 'this draft';
        _confirmDelete("Delete draft '" + _escapeHtml(draftName) + "'? This cannot be undone.", function() {
            var el = window._cy.getElementById(d.id);
            if (el.length > 0) {
                // Remove connected edges first
                el.connectedEdges().remove();
                el.remove();
            }
            if (window._htAutosaveTimer) clearTimeout(window._htAutosaveTimer);
            window._htAutosaveTimer = setTimeout(window._htFlushAutosave, 800);
        });
        return;
    }

    // Published device — existing logic (API DELETE) unchanged
    var deviceName = (d && (d.name || (d.data && (d.data.raw_name || d.data.label)) || d.id)) || 'this device';
    _confirmDelete("Delete device '" + _escapeHtml(deviceName) + "'? This cannot be undone.", function() {
        // ... existing fetch DELETE logic unchanged
    });
});
```

Also add a new handler for **`ht:node-remove-from-view`** (published device removal from View):

```javascript
document.addEventListener('ht:node-remove-from-view', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    if (!window._cy) return;
    // Only for published devices
    if (window._htIsDraft && window._htIsDraft(d.id)) return;

    var deviceName = (d.data && (d.data.raw_name || d.data.label)) || d.id;
    if (window.Quasar && window.Quasar.Dialog && window.Quasar.Dialog.create) {
        window.Quasar.Dialog.create({
            title: 'Remove from View',
            message: "Remove '" + _escapeHtml(deviceName) + "' from this View? The device stays in your inventory.",
            ok: { label: 'Remove', color: 'warning' },
            cancel: { label: 'Cancel', flat: true, color: 'grey-6' },
            persistent: true,
        }).onOk(function() {
            var el = window._cy.getElementById(d.id);
            if (el.length > 0) {
                el.connectedEdges().remove();
                el.remove();
            }
            if (window._htAutosaveTimer) clearTimeout(window._htAutosaveTimer);
            window._htAutosaveTimer = setTimeout(window._htFlushAutosave, 800);
            _notify('Device removed from View.', 'info');
        });
    } else if (window.confirm("Remove '" + deviceName + "' from this View? The device stays in your inventory.")) {
        var el = window._cy.getElementById(d.id);
        if (el.length > 0) {
            el.connectedEdges().remove();
            el.remove();
        }
        if (window._htAutosaveTimer) clearTimeout(window._htAutosaveTimer);
        window._htAutosaveTimer = setTimeout(window._htFlushAutosave, 800);
    }
});
```

Add a new handler for **`ht:node-publish`** (context menu Publish action):

```javascript
document.addEventListener('ht:node-publish', function(evt) {
    if (window.HT_READONLY) return;
    var d = evt.detail;
    if (!d || !d.id) return;
    if (window._htPublishDraft) window._htPublishDraft(d.id);
});
```

**Import change:** at the top of `_CANVAS_EVENTS_JS`, add the draft JS imports:

```python
from src.ui.components.canvas_draft import CANVAS_DRAFT_JS
from src.ui.components.canvas_draft_form import CANVAS_DRAFT_FORM_JS
from src.ui.components.canvas_draft_publish import CANVAS_DRAFT_PUBLISH_JS
```

These are injected as separate `<script>` blocks in `inject_canvas_events()`:

```python
def inject_canvas_events() -> None:
    """Inject canvas event-handler JavaScript into the page body."""
    ui.add_body_html(f"<script>{CANVAS_DRAFT_JS}</script>")
    ui.add_body_html(f"<script>{CANVAS_DRAFT_FORM_JS}</script>")
    ui.add_body_html(f"<script>{CANVAS_DRAFT_PUBLISH_JS}</script>")
    ui.add_body_html(f"<script>{_CANVAS_EVENTS_JS}</script>")
```

### 7.5 `src/ui/components/canvas_js.py` (MODIFIED)

**Change:** Pass the screen-space coordinates of the drop to the `ht:palette-drop` event so the form can position itself.

**Before** (drop handler in `_CANVAS_CORE_JS`, ~line 160):
```javascript
container.addEventListener('drop', function(e) {
    e.preventDefault();
    var deviceType = e.dataTransfer.getData('deviceType');
    if (!deviceType) return;
    var rect = container.getBoundingClientRect();
    var zoom = cy.zoom();
    var pan = cy.pan();
    var renderedX = e.clientX - rect.left;
    var renderedY = e.clientY - rect.top;
    var pos = { x: (renderedX - pan.x) / zoom, y: (renderedY - pan.y) / zoom };
    document.dispatchEvent(new CustomEvent('ht:palette-drop', {
        detail: { deviceType: deviceType, x: pos.x, y: pos.y }
    }));
});
```

**After:**
```javascript
container.addEventListener('drop', function(e) {
    e.preventDefault();
    var deviceType = e.dataTransfer.getData('deviceType');
    if (!deviceType) return;
    var rect = container.getBoundingClientRect();
    var zoom = cy.zoom();
    var pan = cy.pan();
    var renderedX = e.clientX - rect.left;
    var renderedY = e.clientY - rect.top;
    var pos = { x: (renderedX - pan.x) / zoom, y: (renderedY - pan.y) / zoom };
    document.dispatchEvent(new CustomEvent('ht:palette-drop', {
        detail: {
            deviceType: deviceType,
            x: pos.x, y: pos.y,
            screenX: e.clientX, screenY: e.clientY
        }
    }));
});
```

### 7.6 `src/ui/components/canvas_styles.py` (MODIFIED)

Add draft node styles to `build_theme_style_json()`. Insert after the compound node styles block:

```python
    # Draft node styles (HT-051)
    styles.append({
        "selector": "node.draft",
        "style": {
            "border-width":     2,
            "border-style":     "dashed",
            "border-color":     t["warning"],
            "opacity":          0.75,
        },
    })
    styles.append({
        "selector": "node.draft-error",
        "style": {
            "border-color":     t["error"],
            "border-width":     3,
        },
    })
```

The "Draft" pill badge is rendered via Cytoscape's label overlay. To avoid label complexity, instead use a CSS overlay approach not achievable purely in Cytoscape styles. The preferred approach is to use a second line in the label:

```python
    # Draft label — append "(Draft)" suffix via Cytoscape label format
    styles.append({
        "selector": "node.draft",
        "style": {
            "label":        "data(label)\n⚠ Draft",
            "text-wrap":    "wrap",
            "text-max-width": "80px",
            "font-size":    "10px",
        },
    })
```

**Note:** Cytoscape's `label` style property override with `"data(label)\n⚠ Draft"` appends a second line with a draft indicator. This is simpler than an HTML overlay and survives export.

### 7.7 `src/ui/pages/topology.py` (MODIFIED)

**Context menu** — replace the current `_CONTEXT_MENU_JS` with draft-aware actions.

**Before** — `actions` array:
```javascript
var actions = [
    { label: 'Start Association',    event: 'ht:association-source' },
    { label: 'Duplicate',            event: 'ht:node-duplicate' },
    { label: 'Convert to Container', event: 'ht:node-convert-container', hide: isContainer },
    { label: 'Convert to Node',      event: 'ht:node-unconvert-container', hide: !isContainer },
    { label: 'Collapse/Expand',      event: 'ht:node-collapse-toggle', hide: !isContainer },
    { label: 'Delete',               event: 'ht:node-delete' },
];
```

**After** — draft-aware actions:
```javascript
var isDraft = window._htIsDraft && window._htIsDraft(d.id);

var actions = [
    { label: 'Start Association',       event: 'ht:association-source' },
    { label: 'Duplicate',               event: 'ht:node-duplicate',           hide: isDraft },
    { label: 'Convert to Container',    event: 'ht:node-convert-container',   hide: isContainer || isDraft },
    { label: 'Convert to Node',         event: 'ht:node-unconvert-container', hide: !isContainer || isDraft },
    { label: 'Collapse/Expand',         event: 'ht:node-collapse-toggle',     hide: !isContainer || isDraft },
    { label: 'Publish to Inventory',    event: 'ht:node-publish',             hide: !isDraft },
    { label: 'Delete Draft',            event: 'ht:node-delete',              hide: !isDraft },
    { label: 'Remove from View',        event: 'ht:node-remove-from-view',    hide: isDraft },
];
```

**Reasoning:** Published devices get "Start Association", "Duplicate", "Convert to Container"/"Convert to Node", "Collapse/Expand", "Remove from View". Draft devices get "Start Association", "Publish to Inventory", "Delete Draft". The "Delete" label changes to "Delete Draft" for clarity (same event).

### 7.8 `src/ui/services/topology_data.py` (MODIFIED)

**Fundamental change:** Stop loading ALL devices. Only load devices whose UUIDs appear in the View's `cytoscape_json` elements, excluding `draft-` prefixed IDs.

**Before** — loads all devices with pagination, then loads connections, then merges saved layout.

**After** — new flow:

1. Fetch the diagram layout first (to get `cytoscape_json`)
2. Extract published device IDs from `cytoscape_json` elements (skip `draft-` prefixed)
3. Fetch only those devices via `GET /api/devices/{id}` (batch via individual calls) or use the existing list endpoint with ID filtering if available
4. Reconstruct draft elements from `cytoscape_json` data directly (no API call)
5. Fetch connections only for published device pairs appearing in the layout

**Revised `load_canvas_data` signature** (unchanged):
```python
async def load_canvas_data(
    token: str,
    layout_id: str = "",
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
```

**Key implementation change — extract IDs from saved layout:**

```python
def _extract_published_ids(saved_layout: dict[str, object] | None) -> set[str]:
    """Extract published (non-draft) device IDs from cytoscape_json elements."""
    if not saved_layout:
        return set()
    raw = saved_layout.get("elements", {})
    nodes: list[dict[str, object]] = []
    if isinstance(raw, dict):
        nodes = raw.get("nodes", [])
    elif isinstance(raw, list):
        nodes = [n for n in raw if isinstance(n, dict) and n.get("group") != "edges"]
    
    ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        nid = str(data.get("id", ""))
        # Skip draft elements
        if nid.startswith("draft-"):
            continue
        # Skip elements that are draft (belt-and-suspenders)
        if data.get("draft"):
            continue
        if nid:
            ids.add(nid)
    return ids


def _extract_draft_elements(saved_layout: dict[str, object] | None) -> list[dict[str, object]]:
    """Extract draft device elements from cytoscape_json for direct rendering."""
    if not saved_layout:
        return []
    raw = saved_layout.get("elements", {})
    nodes: list[dict[str, object]] = []
    if isinstance(raw, dict):
        nodes = raw.get("nodes", [])
    elif isinstance(raw, list):
        nodes = [n for n in raw if isinstance(n, dict) and n.get("group") != "edges"]
    
    drafts: list[dict[str, object]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        nid = str(data.get("id", ""))
        if nid.startswith("draft-") or data.get("draft"):
            drafts.append(node)
    return drafts
```

**Revised load flow (pseudocode):**

```python
async def load_canvas_data(token, layout_id=""):
    # 1. Fetch the saved layout FIRST
    saved_layout = await _fetch_layout(token, layout_id)
    
    # 2. Extract published device IDs from the layout
    published_ids = _extract_published_ids(saved_layout)
    
    # 3. Fetch only those published devices from the API
    devices = await _fetch_devices_by_ids(token, published_ids)
    
    # 4. Build Cytoscape elements from fetched devices
    elements = _build_device_elements(devices)
    elements = _topological_sort_elements(elements)
    
    # 5. Fetch connections only for published device pairs
    connections = await _fetch_connections_for_ids(token, published_ids)
    elements.extend(_build_connection_elements(connections))
    
    # 6. Append draft elements directly from cytoscape_json (no API call)
    draft_elements = _extract_draft_elements(saved_layout)
    elements.extend(draft_elements)
    
    # 7. Merge positions and collapsed state
    device_ids = {str(d["id"]) for d in devices}
    merge_saved_layout(elements, saved_layout, device_ids)
    apply_collapsed_state(elements, saved_layout)
    
    return elements, saved_layout
```

**Note on device fetching strategy:** The current API supports `GET /api/devices/` with pagination but NOT filtering by a list of IDs. Rather than adding a new endpoint (which would be an API change), the implementation should:
- If `published_ids` is empty → skip device fetch entirely
- If `published_ids` has items → fetch `GET /api/devices/?limit=1000` and filter client-side, OR fetch individually via `GET /api/devices/{id}` for each ID

**Recommended approach:** Fetch all devices via the existing paginated list (same as today) but only build Cytoscape elements for IDs in `published_ids`. This avoids N+1 individual fetches and requires no API change. The only behavioral change is: devices NOT in `cytoscape_json` are excluded from the elements list.

```python
# After fetching all devices (existing pagination loop):
for device in devices:
    device_id = str(device["id"])
    if published_ids and device_id not in published_ids:
        continue  # Skip devices not placed on this View
    # ... existing element-building logic
```

When `published_ids` is empty (no saved layout), fall back to showing all devices (backward-compatible with views that predate HT-051).

### 7.9 `src/ui/components/canvas_js_helpers.py` (MODIFIED)

**Change:** Update `_createAssociation` to handle draft endpoints by creating local-only edges instead of calling the API.

**Before:**
```javascript
function _createAssociation(sourceId, targetId) {
    fetch('/api/connections/', { ... })
    // ... always calls API
}
```

**After:**
```javascript
function _createAssociation(sourceId, targetId) {
    // If either endpoint is a draft, create a local-only edge (no API call)
    if ((window._htIsDraft && window._htIsDraft(sourceId)) ||
        (window._htIsDraft && window._htIsDraft(targetId))) {
        var localEdgeId = 'draft-edge-' + crypto.randomUUID();
        window.addEdgeToCanvas({
            id: localEdgeId,
            source: sourceId,
            target: targetId,
            label: '',
            raw_label: '',
            connection_type: 'Ethernet',
            draft_edge: true
        });
        _notify('Local connection created (will be published when both devices are published).', 'info');
        return;
    }

    // Both published — existing API call
    fetch('/api/connections/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, target_id: targetId, type: 'Ethernet' })
    }).then(function(r) { return r.ok ? r.json() : null; })
      .then(function(conn) {
        if (!conn) {
            _notify('Association could not be created.', 'negative');
            return;
        }
        var rawEdgeLabel = conn.label || '';
        window.addEdgeToCanvas({
            id: conn.id, source: conn.source_id, target: conn.target_id,
            label: _escapeHtml(rawEdgeLabel),
            raw_label: rawEdgeLabel,
            connection_type: conn.type
        });
        _notify('Association created.', 'positive');
    });
}
```

Also update `_deleteAssociation` to handle draft edges (local-only deletion, no API call):

**Before:**
```javascript
function _deleteAssociation(d) {
    // ... always calls DELETE /api/connections/{id}
}
```

**After:**
```javascript
function _deleteAssociation(d) {
    if (!d || !d.id) return;

    // Draft edge — remove locally, no API call
    if (window._htIsDraftEdge && window._htIsDraftEdge(d)) {
        window._cy.getElementById(d.id).remove();
        return;
    }
    // Check by ID prefix as fallback
    if (typeof d.id === 'string' && d.id.indexOf('draft-edge-') === 0) {
        window._cy.getElementById(d.id).remove();
        return;
    }

    // Published edge — existing API deletion logic unchanged
    var edgeLabel = d.raw_label || d.label || (d.data && (d.data.raw_label || d.data.label));
    // ... rest unchanged
}
```

### 7.10 `src/ui/components/device_detail_panel.py` (MODIFIED)

**Change:** When a draft device is selected, show editable fields + "Publish to Inventory" button instead of fetching from the API.

In `_on_panel_select`, detect draft IDs:

**Before:**
```python
async def _on_panel_select(e: object) -> None:
    args = getattr(e, "args", None)
    # ... parses UUID, calls _refresh() which fetches from API
```

**After** — add draft detection before UUID parsing:
```python
async def _on_panel_select(e: object) -> None:
    args = getattr(e, "args", None)
    if not isinstance(args, dict):
        return
    raw_id = args.get("device_id", "")
    if not isinstance(raw_id, str):
        return

    # Draft device — handle in JS-backed panel mode
    if raw_id.startswith("draft-"):
        state["device_id"] = None
        state["last_device"] = None
        await _show_draft_panel(raw_id)
        return

    # Published device — existing logic
    try:
        state["device_id"] = uuid.UUID(raw_id)
    except ValueError:
        logger.warning("panel_select: invalid UUID {!r}", raw_id)
        return
    await _refresh()
```

The `_show_draft_panel` function renders editable fields populated from the Cytoscape node's data (read via `ui.run_javascript`) plus a "Publish to Inventory" button:

```python
async def _show_draft_panel(draft_id: str) -> None:
    """Show panel for a draft device with editable fields and Publish button."""
    # Read draft data from Cytoscape node
    data = await ui.run_javascript(
        f"(function() {{ var n = window._cy.getElementById('{draft_id}');"
        f" return n.length ? n.data() : null; }})()"
    )
    if not data:
        return

    content.clear()
    with content:
        # Draft badge
        ui.label("⚠ Draft Device").style(
            "color:var(--ht-warning); font-weight:600; font-size:0.875rem;"
        )

        # Publish button (prominent, amber)
        async def _on_publish() -> None:
            result = await ui.run_javascript(
                f"window._htPublishDraft('{draft_id}')"
            )
            if result:
                # After publish, the ID changed — close panel
                await ui.run_javascript(
                    "document.getElementById('device-detail-panel').style.display='none'"
                )

        ui.button(
            "Publish to Inventory",
            icon="publish",
            on_click=_on_publish,
        ).style(
            "background:var(--ht-warning); color:#1a1a2e;"
            " font-weight:600; width:100%; min-height:44px;"
        )

        # Editable fields (changes update Cytoscape node data + trigger autosave)
        for field_key, label_text in [
            ("draft_name", "Name"),
            ("draft_ip", "IP"),
            ("draft_mac", "MAC"),
            ("draft_os", "OS"),
            ("draft_notes", "Notes"),
        ]:
            value = data.get(field_key, "")
            inp = ui.input(label=label_text, value=value or "").classes("w-full")

            async def _on_field_change(
                e: object,
                _fk: str = field_key,
                _did: str = draft_id,
            ) -> None:
                val = getattr(e, "value", "")
                js_key = _fk.replace("draft_", "")
                await ui.run_javascript(
                    f"window._htUpdateDraftData("
                    f"window._cy.getElementById('{_did}'),"
                    f"{{ {js_key}: {repr(val)} }});"
                    f"if(window._htAutosaveTimer) clearTimeout(window._htAutosaveTimer);"
                    f"window._htAutosaveTimer = setTimeout(window._htFlushAutosave, 800);"
                )

            inp.on_value_change(_on_field_change)

    await ui.run_javascript(
        "document.getElementById('device-detail-panel').style.display='flex'"
    )
```

**File size concern:** `device_detail_panel.py` is currently ~175 lines. Adding `_show_draft_panel` (~60 lines) brings it to ~235 lines — within the 250-line budget. If it exceeds during implementation, extract `_show_draft_panel` to `src/ui/components/device_detail_draft.py`.

### 7.11 `src/ui/components/canvas_js.py` (MODIFIED) — Delete key guard

**Change:** The Delete key must NOT trigger removal for published devices. Currently handled by `canvas_shortcuts.py`. Verify that `canvas_shortcuts.py` dispatches `ht:node-delete` on Delete key — the event handler in `canvas_events.py` already differentiates draft vs published. **No additional change needed here** — the published device `ht:node-delete` handler will be retained for backward compat with HT-052 (device deletion from inventory), but the context menu for published devices will NOT show "Delete" (replaced by "Remove from View").

However, the Delete key shortcut should only delete **draft** nodes. Add a guard:

### 7.12 `src/ui/components/canvas_shortcuts.py` (MODIFIED)

Read the current file to confirm what it dispatches on Delete:

The Delete key handler must be modified to:
- Draft node selected → dispatch `ht:node-delete` (existing behavior, which now handles drafts locally)
- Published node selected → do nothing (no-op, prevents accidental deletion; right-click "Remove from View" is the explicit path)

**Change in the keydown handler:**
```javascript
// Delete key — only dispatches for draft nodes
if (e.key === 'Delete' || e.key === 'Backspace') {
    var selected = window._cy.nodes(':selected');
    if (selected.length === 1) {
        var selData = selected[0].data();
        var selId = selected[0].id();
        // Only allow Delete key for drafts — published devices use "Remove from View" via right-click
        if (window._htIsDraft && window._htIsDraft(selId)) {
            document.dispatchEvent(new CustomEvent('ht:node-delete', {
                detail: { id: selId, data: selData, name: selData.raw_name || selData.label }
            }));
        }
    }
}
```

### 7.13 Draft Counter in Toolbar

Add a small draft counter display in the topology toolbar. This is a NiceGUI label that updates via periodic JS polling or event-driven updates.

**Implementation:** In `src/ui/pages/topology.py`, add a label in the header actions area:

```python
# In _render_header_actions, after render_edit_toggle:
draft_badge = ui.label("").style(
    "font-size:0.75rem; color:var(--ht-warning); font-weight:600;"
    " padding:2px 8px; border-radius:var(--ht-radius-pill);"
    " background:rgba(251,191,36,0.15); display:none;"
).props('id="ht-draft-badge"')
```

Add JS to update the badge whenever a draft is added/removed/published:

```javascript
// In canvas_draft.py — CANVAS_DRAFT_JS
window._htUpdateDraftBadge = function() {
    var count = window._htDraftCount();
    var badge = document.getElementById('ht-draft-badge');
    if (!badge) return;
    if (count > 0) {
        badge.textContent = count + ' draft' + (count > 1 ? 's' : '');
        badge.style.display = 'inline';
    } else {
        badge.style.display = 'none';
    }
};
```

Call `_htUpdateDraftBadge()` after: draft creation, draft deletion, publish success, page load.

### 7.14 Association with Draft Endpoints

When creating an association (Shift+click or "Start Association" context menu), if either endpoint is a draft, the connection is stored locally as described in §3.2. The `_createAssociation` change in §7.9 handles this.

## 8. Security Boundaries

- **No new secrets or credentials** — Publish reuses the existing JWT token from `credentials: 'include'` (cookie-based).
- **RBAC unchanged** — `POST /api/devices/` requires `Contributor+`. Draft creation is purely client-side and gated by `HT_READONLY` (set from role check in edit toggle).
- **Double-gate:** UI prevents drafts in view-only mode (`HT_READONLY` check) AND the API enforces `Depends(require_role(Role.Contributor))` on publish.
- **Draft data is user-controlled** — since `draft_name`, `draft_ip`, etc. are stored in `cytoscape_json` which is a JSON column, they pass through `_escapeHtml` before rendering. The existing `field_validator` on `DeviceBase` validates name/IP/MAC on publish.
- **No draft data appears in server logs** — drafts never reach the service layer until publish.

## 9. Edge Cases

### 9.1 Empty state
When zero draft devices exist, the draft badge is hidden (`display:none`). The palette and form work identically whether the canvas is empty or populated.

### 9.2 Boundary values
- **Max name length** — enforced server-side on Publish (`max_length=255` on `DeviceBase.name`). The form does not enforce a max; if the server rejects, the error is shown on the node.
- **Empty name** — the form requires a non-empty name before submitting (client-side validation). Server also rejects via `min_length=1`.
- **UUID collisions** — `crypto.randomUUID()` is used for draft IDs. The probability of collision is negligible. After publish, the server assigns a proper UUID.

### 9.3 Concurrent access
Drafts are per-View and stored in `cytoscape_json`. Two users editing the same View: the last-write-wins policy (noted in AGENTS.md) applies to `cytoscape_json` autosave. Draft devices from user A could be overwritten by user B's save if they edit concurrently. This is the same existing behavior for node positions. HT-051 does not change the concurrency model.

### 9.4 Cascade effects
- **Deleting a draft** removes the draft node and all its connected edges from `cytoscape_json`. No database records are affected.
- **Removing a published device from View** removes the node and its edges from `cytoscape_json`. The device and connections remain in inventory.
- **Publishing a draft** creates an inventory record. If the published device is later deleted from the View, only the View reference is removed.

### 9.5 RBAC per operation
| Operation | Admin | Contributor | Reader |
|---|---|---|---|
| Create draft (drag + drop) | ✅ | ✅ | ❌ (no edit mode) |
| Edit draft fields | ✅ | ✅ | ❌ |
| Delete draft | ✅ | ✅ | ❌ |
| Publish draft | ✅ | ✅ | ❌ |
| Remove published from View | ✅ | ✅ | ❌ |
| View draft devices on canvas | ✅ | ✅ | ✅ (read-only, no edit actions) |

### 9.6 Round-trip integrity
Draft elements survive a page reload because they are persisted in `cytoscape_json` via autosave. The `draft: true` flag and `draft_*` fields are all stored in the JSON. On reload, `topology_data.py` reconstructs draft elements from the saved layout.

### 9.7 Canvas impact
- Draft nodes use the `node.draft` Cytoscape CSS class: dashed border, muted opacity, "Draft" label suffix.
- Published nodes are unchanged.
- Connections to/from draft nodes render normally but carry `draft_edge: true` data.

### 9.8 Performance at scale
- **500 devices, 50 drafts** — draft operations are purely local (no API calls). Performance is bounded by Cytoscape rendering, which handles thousands of nodes efficiently.
- **Publish N drafts sequentially** — each publish is an individual `POST /api/devices/`. For 50 drafts, this is 50 sequential API calls. Acceptable for the expected draft count (single-digit in typical use). If latency becomes an issue, a batch endpoint can be added later (explicitly out of scope per story).
- **topology_data.py** — the change to filter by `cytoscape_json` IDs reduces data loaded for large inventories. If a View has 20 devices placed, only those 20 are fetched (previously all 500 would be fetched).

## 10. Files to Create/Modify

| File | Action | Lines (est.) | Purpose |
|---|---|---|---|
| `src/ui/components/canvas_draft.py` | Create | ~80 | Draft element helpers: `_htIsDraft`, `_htDraftId`, `_htBuildDraftNode`, `_htUpdateDraftData`, `_htDraftCount`, `_htUpdateDraftBadge` |
| `src/ui/components/canvas_draft_form.py` | Create | ~100 | On-drop floating popover form: `_htShowDraftForm` |
| `src/ui/components/canvas_draft_publish.py` | Create | ~120 | Publish flow: `_htPublishDraft`, `_htPromoteConnections` |
| `src/ui/components/canvas_events.py` | Modify | ~230→250 | Replace `ht:palette-drop` handler with draft creation, update `ht:node-delete` for drafts, add `ht:node-remove-from-view` and `ht:node-publish` handlers, import+inject draft JS |
| `src/ui/components/canvas_js.py` | Modify | ~190→195 | Add `screenX`, `screenY` to `ht:palette-drop` event detail |
| `src/ui/components/canvas_js_helpers.py` | Modify | ~100→130 | Update `_createAssociation` for draft endpoints, update `_deleteAssociation` for draft edges |
| `src/ui/components/canvas_styles.py` | Modify | ~135→155 | Add `node.draft` and `node.draft-error` style selectors |
| `src/ui/components/canvas_shortcuts.py` | Modify | — | Guard Delete key to only fire for draft nodes |
| `src/ui/pages/topology.py` | Modify | ~240→250 | Draft-aware context menu actions, draft badge in toolbar |
| `src/ui/components/device_detail_panel.py` | Modify | ~175→235 | Draft panel: detect `draft-` ID, render editable fields + Publish button |
| `src/ui/services/topology_data.py` | Modify | ~165→220 | Opt-in device loading: extract published IDs from `cytoscape_json`, filter devices, append draft elements |
| `src/ui/services/topology_data_helpers.py` | Modify | ~140→180 | Add `_extract_published_ids`, `_extract_draft_elements` helpers |
| `src/ui/components/topology_edit_toggle.py` | No change | — | Already queries `window._cy.nodes('.draft').length` — works with the `.draft` CSS class |

**No migrations.** No new API endpoints. No changes to `src/api/`, `src/services/`, `src/repositories/`, or `src/domain/`.

## 11. Test Plan

### 11.1 Unit Tests — `tests/unit/test_topology_data_helpers.py` (new)

Test the pure helper functions extracted to `topology_data_helpers.py`:

| Test | Fixture | Asserts |
|---|---|---|
| `test_extract_published_ids_excludes_drafts` | Hand-crafted `cytoscape_json` dict with mix of draft and published nodes | `_extract_published_ids` returns only non-`draft-` IDs |
| `test_extract_published_ids_empty_layout` | `None` and `{}` | Returns empty set |
| `test_extract_draft_elements_returns_drafts_only` | Mixed layout | `_extract_draft_elements` returns only draft nodes |
| `test_extract_draft_elements_preserves_position` | Draft with position | Position data is in returned element |

### 11.2 Integration Tests — `tests/integration/test_topology_data.py` (new)

Test the `load_canvas_data` function with mocked HTTP responses:

| Test | Fixture | Asserts |
|---|---|---|
| `test_load_canvas_data_filters_by_layout_ids` | `admin_token`, mock `httpx.AsyncClient` | Only devices in `cytoscape_json` are returned as elements |
| `test_load_canvas_data_includes_draft_elements` | Mock layout with drafts | Draft elements appear in returned elements list |
| `test_load_canvas_data_no_layout_loads_all` | No saved layout | Falls back to loading all devices (backward compat) |

### 11.3 E2E Tests — `tests/e2e/test_draft_device.py` (new, Playwright)

| Scenario | Steps | Asserts |
|---|---|---|
| Drag type → form → draft node | Drag "Server" onto canvas, fill name, submit | Node appears with dashed border, "Draft" label |
| Cancel form → no node | Drag + Escape | No new node on canvas |
| Publish draft | Create draft → right-click → Publish | Node border becomes solid, API device exists |
| Delete draft | Create draft → right-click → Delete Draft → confirm | Node removed from canvas |
| Remove published from View | Right-click published → Remove from View → confirm | Node removed from canvas, device still in inventory |
| Draft count badge | Create 2 drafts | Badge shows "2 drafts" |
| Exit edit mode with drafts | Create draft → Stop Editing | Prompt dialog appears |
| Draft survives reload | Create draft → reload page | Draft node still present |

### 11.4 Fixtures Used

From `tests/conftest.py`:
- `admin_token` / `contributor_token` — for authenticated API calls during Publish
- `client` — for integration tests against the FastAPI test client
- `session` — for verifying published devices exist in the database after Publish
