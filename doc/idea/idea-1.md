# Idea 1: "Share My Setup" + Community Blueprint Library

**Status:** Concept
**Category:** Viral Growth / Community
**Impact:** High — solves activation friction and distribution simultaneously
**Effort:** Medium — core infrastructure (RBAC, Cytoscape, PostgreSQL) already exists

---

## The Problem It Solves

Homelabbers already go viral. Every week on r/homelab someone posts "rate my homelab" with a hand-drawn Visio screenshot or a wall of text. Those posts get thousands of upvotes. People want to learn from each other's infrastructure designs.

Hometower already holds the data. The diagram IS the inventory. One button away from making it shareable.

SMEs have a parallel problem: onboarding a new IT contractor, a vendor support call, or a compliance audit all start with "can you show us your network?" — answered today with a PowerPoint or a panicked Visio export.

---

## How It Works

### For the Homelabber

1. One-click **"Share My Setup"** → generates a public, interactive, read-only URL
2. Post on Reddit, Discord, YouTube description, Twitter/X
3. Viewers explore the live topology, click devices, see the full stack
4. One button: **"Clone This Setup"** → copies the diagram into their own Hometower instance, they fill in their own IPs/names

### Community Blueprint Library

A curated gallery of top-rated community setups, browsable by category:

- "3-tier homelab — Proxmox + TrueNAS + pfSense"
- "Home office with VLANs and Pi-hole"
- "SME 15-user office network with failover"
- "Docker Swarm + reverse proxy homelab"

Blueprints reduce activation friction from hours to minutes. The blank canvas problem — the biggest Y1 churn risk — disappears.

### Health Score (attached feature)

Hometower analyzes the topology graph and produces a score 0–100:

| Check | Example finding |
|---|---|
| Single point of failure | "switch-01 is on the critical path for 80% of your devices" |
| No redundant uplink | "Your core switch has no failover path" |
| UPS coverage | "3 critical nodes have no UPS in their location chain" |
| VLAN isolation | "IoT devices share a segment with servers" |
| Backup coverage | "NAS-01 has no documented backup target" |

Score is visible on the shared profile. Shareable, improvable, competitive.

---

## Why It Goes Viral

| Mechanism | Effect |
|---|---|
| Every share is organic acquisition | A Reddit post with a live Hometower link is free marketing. Viewer clicks, explores, wants their own. |
| YouTubers adopt it | Craft Computing, Wolfgang, NetworkChuck show their setup via Hometower link instead of a static image. |
| Clone button = zero-friction onboarding | Hardest part of any doc tool is the blank canvas. Cloning a blueprint removes it entirely. |
| Health Score creates competition | "My homelab scored 74 — how do I get to 90?" drives engagement and return visits. |
| r/homelab culture already does this | They're already posting setups. Hometower gives them a better format. |

---

## Why SMEs Pay for It

| SME Pain Point | What They Get |
|---|---|
| New contractor onboarding | Share a private link → contractor sees the full topology before day one |
| Vendor support calls | "Here's our network" → live link → support understands in 30 seconds |
| MSP client documentation | Each client has a private workspace, shareable on demand |
| Compliance audit | "Show us your network diagram" → share link → done |
| Health Score as mini IT audit | SMEs show score to MSP. MSPs use it to sell remediation work. |

---

## The Growth Flywheel

```
User builds topology
        │
        ▼
Gets Health Score → wants to improve → uses Hometower more
        │
        ▼
Shares setup publicly → Reddit / YouTube / Discord
        │
        ▼
New visitors clone blueprint → instant value, zero blank canvas
        │
        ▼
New users build their topology → share → repeat
```

This is the **GitHub for infrastructure diagrams**. GitHub didn't invent version control — it made it social. Hometower doesn't invent network documentation — it makes it social.

---

## Revenue Impact

| Effect | Impact |
|---|---|
| Activation friction solved | Conversion from install → active user: ~20% → ~50%+ |
| Free distribution at scale | Every share drives installs. CAC trends toward zero. |
| Private sharing = LightTower upsell | "Your link is public. Want private sharing for your team?" → natural paid conversion trigger |
| MSP use case unlocked | MSPs pay $200–500/mo to give every client a private shared topology |
| Blueprint marketplace (Y2–Y3) | Charge consultants/MSPs to publish premium blueprints. Revenue share model. |

**Estimated impact: 3× Y2 revenue projection vs. without this feature.**

---

## Build Complexity

### What already exists
- Topology data in PostgreSQL ✓
- Cytoscape.js rendering ✓
- RBAC with Reader role (maps directly to public share) ✓
- Device, Connection, Location models ✓

### What's new
| Component | Effort |
|---|---|
| Public share URL generation + read-only view | Low — Reader role + public token |
| Clone function (copy diagram to new account) | Medium — deep copy of devices/connections/layout |
| Health score algorithm | Medium — graph traversal, single-point-of-failure detection |
| Blueprint library UI | Medium — gallery page + category browsing |
| Featured/curated blueprint curation | Ongoing — community management |

---

## Positioning

> **"GitHub for infrastructure diagrams."**

Not a documentation tool. A living, shareable, community-powered inventory. Every homelaber who shares their setup is a free billboard. Every SME who shares with their MSP is a paid acquisition.

---

## Open Questions

1. Should the Health Score algorithm live in `src/domain/topology.py` as a pure graph function?
2. Clone function — does it copy location data, or does the user re-assign locations?
3. Blueprint library — community-submitted or curated by Hometower team initially?
4. Public share URL format — `/s/{token}` or `/u/{username}/{slug}`?
5. Privacy default — public or private? (Recommendation: private by default, explicit opt-in to public)
6. Rate limiting on public share views to prevent scraping of network topology data?
