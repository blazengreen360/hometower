---
name: visual-dom-snapshot
description: Uses headless Playwright to navigate to a target UI path, wait for network idle to ensure models render, and capture a physical screenshot of the DOM for visual verification protocols.
---

# visual-dom-snapshot

Satisfies the "Mandatory Visual Proof Capture" property for the `UX-Designer` and `User-Simulator` by giving them a programmable snapshot utility instead of doing it manually.

## Visual Verification Rules

- capture before/after states when validating a UI change
- prefer snapshots around a meaningful user task, not only idle landing pages
- if the page has async states, capture the most relevant stable state after loading settles

## When to use

- **UX-Designer**: After completing UI changes, to embed the visual proof into your JSON output contract.
- **User-Simulator**: When you hit a UI bug, snap a pic of the broken page.

## Run

```bash
bash .github/skills/visual-dom-snapshot/scripts/capture.sh --url "/inventory" --out "inventory_proof.png"
```

## How it works

The python engine spins up a headless Chromium instance, injects a mocked JWT auth to get past the login screen (if required), navigates to `http://localhost:8080[url]`, waits for exactly 1 second for animations/Cytoscape.js to stabilize, and writes the snapshot to the artifact path!
