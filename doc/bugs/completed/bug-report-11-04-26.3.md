# QA-Orchestrator Bug Report: 11-04-26.3

**Date:** 12 April 2026
**Target:** Hometower UI & Integration Layer (Phase 1)
**Orchestrator:** QA-Orchestrator
**Methodology:** UI State / Javascript Bridge Integration Audit

## Executive Summary
A focused bug hunt was executed on the `src/ui/` directory, isolating the Javascript/Python event bridges and state management systems (NiceGUI). State encapsulation inside NiceGUI components passed successfully — variables are properly scoped within UI function closures, preventing destructive cross-user global leaks (`nicegui-state-management` skill verified). However, a critical **memory/event leak** in the client-side JS integrations was discovered that will degrade performance and DDos the backend on persistent sessions.

### Verdict
🔴 **VULNERABLE (CLIENT-SIDE LEAK)**
Unprotected DOM-level event listeners injected dynamically by Python components will cause geometric duplication loops.

---

## Findings

### LANE: Performance & Integration (ODC: Function/Timing)

| ID | Severity | File | Description |
|---|---|---|---|
| **BUG-1103-01** | **HIGH** | `device_detail_panel_bridge.py`, `connection_detail_panel.py` | **Exponential Event Listener Duplication (Client Leak).** Components inject pure JS strings containing `document.addEventListener(...)` payloads into the frontend via `ui.add_body_html()`. Because they lack IIFE guard flags (e.g., `if (window._htPanelInit) return;`), traversing to the topology page repeatedly triggers re-injections of the script. The `document` object does not reset on SPA-like transitions in NiceGUI, causing identical event listeners to stack. **Impact:** Clicking a device or connection edge in a long-lived browser session will eventually trigger dozens or hundreds of duplicate `emitEvent('conn_panel_select')` Socket.IO messages back to Python, causing severe server lag and UI locking. |

*Proof of Concept (BUG-1103-01):*
```javascript
// src/ui/components/device_detail_panel_bridge.py
(function() {
    // Missing: if (window._htDetailBridgeInit) return; window._htDetailBridgeInit = true;
    document.addEventListener('ht:node-selected', function(evt) {
        var id = evt && evt.detail && evt.detail.id;
        if (id) emitEvent('panel_select', {device_id: String(id)});
    });
})();
```

### LANE: Security (STRIDE: XSS / Cross-Site Scripting)

| ID | Severity | File | Description |
|---|---|---|---|
| **VERIFIED-1103-00** | **PASS** | JS Bridge Code (`connection_detail_panel.py`) | **Safe Interpolation Validated.** A structural audit of functions like `_build_cy_edge_update_js` confirms they correctly employ Python's `json.dumps()` prior to interpolating variables into generated Javascript blocks, safely dodging quote-escape XSS attacks. |

---

## Routing & Next Steps Operations

1. **BUG-1103-01 (Event Array Leak):** Route to `Feature-Engineer` or `UX-Designer`. Wrap all `ui.add_body_html` injected scripts with a `window._<name>_Initialized` boolean check to ensure exact singleton behavior on the `document` scope.
2. **Tracking Update:** Record these findings in `doc/bugs/bug-report-11-04-26.3.md` and alert PM.
