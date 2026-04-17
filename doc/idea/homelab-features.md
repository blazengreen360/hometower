# Homelab Feature Ideas

**Date:** 2026-04-13  
**Status:** Brainstorm / Ready for Triage  
**Audience:** Product-Owner, Project-Manager

These are high-value features identified through analysis of homelab use cases and pain points. Not yet in backlog or icebox — PM should triage these into appropriate pipeline.

---

## Overview

Hometower Phase 1 covers **core inventory**: devices, connections, networks, services, workspaces, RBAC. What's missing are **operational features** that help homelabbers maintain, track, and manage their infrastructure day-to-day.

**Key observation:** Homelabbers don't just need to *see* their infrastructure — they need to *maintain* it. That means tracking versions, backups, cabling, costs, and lifecycle.

---

## 🎯 Priority Features

### 0. Generate Homelab Report (FLAGSHIP) ⭐⭐⭐⭐⭐

**Value:** Enables planning, documentation, compliance  
**Effort:** M (medium)  
**Complexity:** Medium  
**Dependencies:** None (builds on existing data)

#### Problem

Homelabbers need to:
- **Justify spending** — "How much am I investing in hardware?"
- **Plan upgrades** — "What hardware is aging? What's bottlenecking?"
- **Document setup** — "Show my boss/partner what's running"
- **Disaster planning** — "What devices are critical? What can fail?"
- **Tax/insurance** — "Itemized list of equipment value"

Currently, there's no way to generate a cohesive, professional document about the homelab.

#### Proposed Solution

**Report Generator** — Scoped report generation with multiple templates:

**Scope Options:**
- Entire homelab
- By workspace
- By topology  
- By location (physical site)
- By device type
- By service/application tier

**Report Templates:**

1. **Executive Summary** (1 page)
   ```
   Homelab Overview Report
   ├── Total Devices: 18
   ├── Inventory Value: $8,450
   ├── Active Services: 12
   ├── Total Power Draw: 2.3 kW
   ├── Geographic Locations: 2
   └── Last Updated: 2026-04-13
   ```

2. **Inventory Report** (tabular)
   ```
   Device Name | Type | Status | Location | Cost | Notes
   Server-01   | Server | Active | Rack-A | $599 | Proxmox hypervisor
   NAS-01      | NAS    | Active | Rack-A | $499 | Backup destination
   ...
   ```

3. **Network Topology Report** (with ASCII/text diagram)
   ```
   Internet
      │
      └─ ISP-Router
           │
           ├─ Core-Switch (24-port)
           │   ├─ Server-01 (2x 1GbE)
           │   ├─ Server-02 (2x 1GbE)
           │   └─ NAS-01 (1GbE + 10GbE SFP)
           │
           └─ Wifi-AP
   ```

4. **Service Dependencies Report** (showing critical paths)
   ```
   Critical Services:
   └─ Plex
       └─ Server-01
           └─ NAS-01 (shared storage)
               └─ Network (10GbE link)
   
   Redundancy: No backup Plex server
   RTO: High (single point of failure)
   ```

5. **Capacity & Planning Report**
   ```
   Power Utilization:
   ├── Current Draw: 2.3 kW / 5.0 kW available = 46%
   ├── Available Capacity: 2.7 kW
   └── Recommendation: Can add ~5 more servers before power upgrade
   
   Storage:
   ├── Total Capacity: 100 TB
   ├── Used: 65 TB (65%)
   ├── Available: 35 TB
   └── Growth Rate: +2 TB/month → Upgrade needed in ~17 months
   
   Network:
   ├── Main Links: 1GbE (bottleneck)
   ├── Uplinks: 10GbE (room to scale)
   └── Recommendation: Add 10GbE to main servers for better throughput
   ```

6. **Hardware Lifecycle Report**
   ```
   Devices by Age:
   ├─ <1 year: 5 devices ✓
   ├─ 1-3 years: 8 devices ⚠️ (monitor)
   ├─ 3-5 years: 4 devices 🔴 (plan replacement)
   └─ >5 years: 1 device (end-of-life soon)
   
   Warranty Expiration:
   ├─ Active: 12 devices
   ├─ Expiring Soon (<90 days): 2 devices
   └─ Expired: 4 devices
   ```

7. **Risk & Resilience Report**
   ```
   Single Points of Failure:
   ├─ Internet connection: 1 ISP (RTO: immediate)
   ├─ Power supply: 1 circuit (RTO: ~30 min generator)
   ├─ Core switch: 1 device (RTO: 15 min replacement)
   ├─ NAS storage: RAID-6 (can survive 2 drive failures)
   └─ Backup: Daily to S3 (can recover in 2 hours)
   
   Backup Status:
   ├─ Devices backed up: 12/18 (67%)
   ├─ Last successful backup: 2026-04-13 (today)
   ├─ Backup age: 2-6 hours (good)
   └─ Recovery test: Pending
   ```

#### Output Formats

- **HTML** — Pretty report, printable, embedded images/diagrams
- **PDF** — Print-friendly, shareable, archivable (via wkhtmltopdf)
- **Markdown** — For wiki/documentation integration
- **JSON** — Structured data export for further processing

#### UI Implementation

**New "Reports" section in Settings:**

```python
# Settings → Reports
┌─────────────────────────────────────────┐
│ Report Generator                        │
├─────────────────────────────────────────┤
│ Template: [Inventory ▼]                 │
│ Scope: [Entire Homelab ▼]              │
│ Include sections:                       │
│  ☑ Device inventory table              │
│  ☑ Network diagram                     │
│  ☑ Services & dependencies             │
│  ☑ Capacity analysis                   │
│  ☑ Hardware lifecycle                  │
│  ☑ Backup status                       │
│                                         │
│ Output format: [PDF ▼]                  │
│ [Generate Report]                       │
├─────────────────────────────────────────┤
│ Recent Reports:                         │
│ • homelab-2026-04-13.pdf               │
│ • homelab-2026-04-06.pdf               │
│ • by-location-2026-04-13.pdf           │
└─────────────────────────────────────────┘
```

#### Database Changes

Minimal — all data already exists. Create new `Report` model for caching:

```python
class Report(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(foreign_key="workspace.id")
    template: str  # "inventory", "topology", "risk", etc.
    scope: str     # "entire", "by_location", "by_service", etc.
    created_by: UUID = Field(foreign_key="user.id")
    created_at: datetime
    filename: str
    size_bytes: int
    ttl_days: int = 7  # Auto-delete after 7 days
```

#### Use Cases

**User 1: Hardware Planning**
```
"I want to plan next quarter's upgrades"
Action: Reports → Template: "Capacity & Planning" 
        → Output: PDF shows power, storage, network bottlenecks
Result: Clear prioritization (network upgrade first, storage second)
```

**User 2: Disaster Recovery**
```
"We need a DR plan for our homelab"
Action: Reports → Template: "Risk & Resilience"
        → Output: PDF shows SPOFs, backup status, RTO estimates
Result: Identifies that NAS is SPOF, triggers redundancy planning
```

**User 3: Documentation**
```
"My partner needs to know what's in the homelab"
Action: Reports → Template: "Inventory" → Scope: "Entire Homelab"
        → Output: Professional HTML report with topology diagram
Result: Shareable document of infrastructure with costs, services, locations
```

**User 4: Insurance/Tax**
```
"I need itemized list for insurance claim"
Action: Reports → Template: "Inventory"
        → Include: Device list with cost, serial number, model
        → Output: CSV for accounting software
Result: Ready for insurance agent, accountant
```

#### Implementation Path

**Phase 1 (Week 1-2):** Basic inventory report
- Template engine (Jinja2)
- HTML output
- Device inventory table + totals

**Phase 2 (Week 3-4):** Rich reports
- ASCII topology diagram
- Service dependency tree
- PDF generation (wkhtmltopdf)

**Phase 3 (Future):** Advanced reports
- Capacity analysis (power, storage, network)
- Hardware lifecycle timeline
- Risk/resilience assessment
- Grafana/Prometheus integration for metrics

#### Effort Estimate
- Template engine: 1h (Jinja2 setup)
- Inventory template: 1.5h (table rendering)
- HTML output: 0.5h
- PDF generation: 1h (wkhtmltopdf integration)
- Topology diagram: 2h (ASCII or Graphviz)
- UI: 1h (reports settings page)
- **Total Phase 1: 4h**
- **Total Phase 2: 2-3h**

#### Why This Feature?

1. **Unlocks monetization** — Could justify self-hosted version vs. cloud
2. **Documentation** — Every homelab needs documentation, this generates it
3. **Planning** — Capacity/risk reports enable informed decisions
4. **Compliance** — CSV export for insurance, tax, audits
5. **Shareability** — PDF reports for collaborators, partners, team members

---

## 🎯 Top 5 Features (Ranked by Value)

### 1. Cable & Port Management ⭐⭐⭐⭐⭐

**Value:** Solves real pain point (tracking physical connections)  
**Effort:** M (medium)  
**Complexity:** Low  
**Dependencies:** None

#### Problem
Homelabbers have dozens of cables. When troubleshooting or planning upgrades, it's easy to forget which device connects to what port, what cable type is used, and which ports are available.

#### Proposed Solution
- **Add ports/interfaces to Device model:**
  ```json
  {
    "device_id": "...",
    "ports": [
      {
        "name": "eth0",
        "type": "1GbE",
        "speed": "1000Mbps",
        "connected_to_port": "switch-01:port-1"
      },
      {
        "name": "eth1",
        "type": "1GbE",
        "speed": "1000Mbps",
        "connected_to_port": null
      }
    ]
  }
  ```

- **Connection UI enhancement:**
  - When drawing a connection, show "Source Port" + "Dest Port" dropdowns
  - Optional: cable type selector (Cat5e, Cat6, Cat6a, Fiber, PoE)
  - Store `source_port`, `dest_port`, `cable_type` on Connection model

- **Device detail panel:**
  - New "Port Matrix" tab showing all ports and connections
  - Visual indicator for available vs. occupied ports
  - Bulk action: show port utilization (8/24 ports used)

- **Reports:**
  - "Cable Inventory" CSV export: device, source port, dest port, cable type, length
  - "Port Availability": which devices have available ports
  - "Connected Topology": graph of all connections with cable types

#### Use Case
```
User action: "I need to move Server-03. What's it connected to?"
Current: Manual inspection of device detail, check connections
With feature: Click "Port Matrix" → see all ports + cables → safe to disconnect
```

#### Wireframe
```
Device: Server-01 (detail panel)
├── [General] [Specs] [Services] [Port Matrix]
│
├── Port Matrix:
│   ┌─────────────────────────────────────────────┐
│   │ Port  │ Type   │ Speed  │ Connected To │ Type │
│   ├─────────────────────────────────────────────┤
│   │ eth0  │ 1GbE   │ 1Gbps  │ Switch-1:p1  │ Cat6 │
│   │ eth1  │ 1GbE   │ 1Gbps  │ Switch-1:p2  │ Cat6 │
│   │ ipmi  │ Mgmt   │ 1Gbps  │ OOB-Switch:3 │ Cat5e│
│   │ (unused) │      │        │              │      │
│   └─────────────────────────────────────────────┘
```

#### Implementation Path
1. **Phase 1:** Add `ports` JSON field to Device + `source_port`/`dest_port` to Connection
2. **Phase 2:** Port Matrix UI in device detail
3. **Phase 3:** Cable inventory reports + visualization

#### Effort Estimate
- Database: 1h (add JSON fields)
- UI: 2h (port matrix table, connection UI)
- Reports: 1h (CSV generation)
- **Total: 4h**

---

### 2. Firmware & OS Version Tracking ⭐⭐⭐⭐

**Value:** High — enables security/upgrade planning  
**Effort:** S (small)  
**Complexity:** Low  
**Dependencies:** None

#### Problem
Homelabbers need to know which devices are running outdated software. Security patches, bug fixes, and feature availability depend on OS versions. Without tracking versions, it's easy to miss critical updates.

#### Proposed Solution
- **Add to Device model:**
  ```python
  class Device(DeviceBase, table=True):
      # ... existing fields ...
      os_name: Optional[str] = None          # "Ubuntu 22.04 LTS"
      os_version: Optional[str] = None       # "22.04.1"
      firmware_version: Optional[str] = None # "1.2.3"
      kernel_version: Optional[str] = None   # "6.2.16-generic"
      last_version_check: Optional[datetime] = None
  ```

- **Device detail panel:**
  - New "System Info" section (editable)
  - Fields: OS, OS Version, Firmware, Kernel
  - Last updated timestamp
  - Optional: version comparison against known latest (requires external data source)

- **List view enhancement:**
  - Optional column: "OS Version" with color-coding:
    - 🟢 Green: Current (checked within 30 days)
    - 🟡 Yellow: Outdated (>30 days since check)
    - 🔴 Red: Unknown (never checked)

- **Dashboard widget:**
  - "System Health" card showing:
    - Devices with unknown versions
    - Devices known to be outdated
    - Last version check timestamps

#### Use Case
```
User sees dashboard: "5 devices with unknown OS versions"
Click → List of devices needing version check
Plan: Check versions this week, schedule updates
```

#### Wireframe
```
Dashboard Card: System Health
┌──────────────────────────────┐
│ 🖥️  System Versions          │
├──────────────────────────────┤
│ ✓ Current:  8 devices        │
│ ⚠️  Outdated: 2 devices      │
│ ❓ Unknown:  1 device        │
│                              │
│ [View Details]               │
└──────────────────────────────┘
```

#### Effort Estimate
- Database: 0.5h (add fields to Device)
- UI: 1h (detail panel + list view column)
- Dashboard: 0.5h (widget)
- **Total: 2h**

---

### 3. Asset Lifecycle & Warranty Tracking ⭐⭐⭐

**Value:** Medium-High — enables asset planning  
**Effort:** M (medium)  
**Complexity:** Low  
**Dependencies:** None

#### Problem
Homelabbers want to know:
- Which devices are aging (approaching 5-year replacement cycle)?
- Which are out of warranty?
- What's the total investment in hardware?
- When should devices be replaced?

#### Proposed Solution
- **Add to Device model:**
  ```python
  class Device(DeviceBase, table=True):
      # ... existing fields ...
      purchase_date: Optional[date] = None
      cost_usd: Optional[float] = None
      warranty_expiry: Optional[date] = None
      model_code: Optional[str] = None          # "Synology DS920+"
      serial_number: Optional[str] = None       # "ABC123XYZ"
      eol_date: Optional[date] = None           # Vendor end-of-life
  ```

- **Device detail panel:**
  - New "Lifecycle" section showing:
    - Device age (calculated from purchase_date)
    - Days until warranty expires (with color: 🟢 <90 days away = yellow)
    - Days until EOL (if vendor data available)
    - Cost (for budgeting)
  - Example:
    ```
    Purchase Date: 2022-03-15
    Age: 2 years 1 month
    Warranty Expiry: 2025-03-15 ⚠️ 337 days remaining
    Cost: $599
    EOL: 2027-03-15 (3 years 1 month away)
    ```

- **Dashboard widgets:**
  - "Warranty Expiring Soon" (next 90 days)
  - "Aging Hardware" (>4 years old)
  - "Total Investment" (sum of all device costs)

- **Bulk actions:**
  - Export "Asset Register" (CSV: name, model, cost, warranty, age)
  - Export "Depreciation Schedule" (for accounting)

#### Use Case
```
User: "I need to budget for hardware replacement next year"
Action: Inventory → Filter by Age > 4 years → Export to Excel → Budget planning
```

#### Effort Estimate
- Database: 0.5h (add fields)
- UI: 1.5h (detail panel, dashboard widgets)
- Export: 1h (CSV generation)
- **Total: 3h**

---

### 4. Quick Documentation Links & Runbooks ⭐⭐⭐

**Value:** Medium-High — improves usability  
**Effort:** S (small)  
**Complexity:** Low  
**Dependencies:** None

#### Problem
Every device has associated documentation:
- Management interfaces (SSH, IPMI, web UI)
- Wiki articles
- Vendor documentation
- Runbooks (disaster recovery, troubleshooting)
- Monitoring dashboards (Grafana)

Homelabbers need quick access without hunting through bookmarks.

#### Proposed Solution
- **Add to Device model:**
  ```python
  class Device(DeviceBase, table=True):
      # ... existing fields ...
      quick_links: Optional[list[QuickLink]] = []
  
  class QuickLink(SQLModel):
      label: str              # "Web UI", "SSH", "Wiki", etc.
      url: str                # Full URL
      icon: Optional[str]     # Icon name (globe, terminal, book, etc.)
      description: Optional[str]
  ```

- **Device detail panel:**
  - New "Quick Links" section at the top (high visibility)
  - Template suggestions by device type:
    - **Server:** SSH (port 22), IPMI/iLO, Web UI, Monitoring
    - **Router:** Web UI, SSH, Syslog, Monitoring
    - **NAS:** Web UI, SMB share path, SSH, Backups
    - **Hypervisor:** Console, API, SSH, Metrics
  - Each link shows:
    - Icon + label
    - Protocol detection (http → clickable, ssh://user@host → copy to clipboard)
    - Click → open in new tab or copy to clipboard

- **Device creation/edit:**
  - Optional: "Quick Links" tab with +Add button
  - Pre-fill from type template (user can customize)

#### Use Case
```
User (in middle of troubleshooting): "Need to SSH into Proxmox-01"
Current: Search browser history → find IP → type ssh root@...
With feature: Click device name → click "SSH" link → copies ssh root@proxmox-01.local
```

#### Wireframe
```
Device: Proxmox-01 (detail panel header)
┌────────────────────────────────────────┐
│ Quick Links:                           │
│ [🌐 Web UI] [🔧 SSH] [📖 Wiki] [📊 Grafana] │
└────────────────────────────────────────┘
```

#### Effort Estimate
- Database: 0.5h (add JSON field)
- UI: 1h (links section, template engine)
- **Total: 1.5h**

---

### 5. Backup Status Tracking ⭐⭐⭐

**Value:** Medium-High — prevents RTO disasters  
**Effort:** M (medium)  
**Complexity:** Low  
**Dependencies:** None

#### Problem
Homelabbers rely on backups but struggle to track:
- Which devices are backed up?
- When was the last successful backup?
- Are any backups failing?
- What's the backup destination?

Without visibility, RTO (Recovery Time Objective) skyrockets.

#### Proposed Solution
- **Add to Device model (via custom fields or native):**
  ```python
  class Device(DeviceBase, table=True):
      # ... existing fields ...
      backup_enabled: Optional[bool] = None
      last_backup_time: Optional[datetime] = None
      backup_status: Optional[str] = None    # "Success", "Failed", "Pending", "Unknown"
      backup_destination: Optional[str] = None  # "NAS-backup", "S3", "USB-external"
      backup_notes: Optional[str] = None       # "Backing up to NAS via rsync"
  ```

- **Device detail panel:**
  - New "Backup Status" section showing:
    - Enabled/disabled toggle (quick visual)
    - Last backup time + age (color-coded: 🟢 <7 days, 🟡 7-14 days, 🔴 >14 days)
    - Status: Success ✓ / Failed ❌ / Pending ⏳
    - If failed, show error message for debugging
    - Destination (for context)
  - Example:
    ```
    Backup: ✓ Enabled
    Last Backup: 2026-04-13 10:30 UTC (2 hours ago) 🟢
    Status: Success ✓
    Destination: NAS-backup volume
    
    --- vs ---
    
    Backup: ✓ Enabled
    Last Backup: 2026-04-11 02:15 UTC (2 days 9 hours ago) 🟡
    Status: Failed ❌
    Error: "Insufficient disk space on NAS-backup"
    Destination: NAS-backup volume (FULL)
    ```

- **Dashboard widget:**
  - "Backup Health" card:
    ```
    Backups Healthy: 12/15 ✓
    Failed: 2 ❌
    Pending: 1 ⏳
    Never Backed Up: 0
    ```
  - Click → see which devices need attention

- **Alerts (optional phase 2):**
  - Alert if last backup > 7 days
  - Alert if status = Failed
  - Alert if backup_enabled = false

- **Bulk actions:**
  - "Generate Backup Checklist" (CSV) for manual backups
  - Filter "Backups Need Attention" → bulk export

#### Use Case
```
User: "Is everything backed up?"
Before: Check each device individually → 15 minutes
After: Open dashboard → "Backup Health" card → 10 seconds
```

#### Wireframe
```
Dashboard Card: Backup Health
┌─────────────────────────────┐
│ 💾 Backup Status            │
├─────────────────────────────┤
│ ✓ Healthy:  12/15 devices   │
│ ❌ Failed:   2 devices      │
│ ⏳ Pending:  1 device       │
│                             │
│ [View Details]              │
└─────────────────────────────┘
```

#### Effort Estimate
- Database: 0.5h (add fields)
- UI: 1.5h (detail panel, dashboard widget)
- Export: 0.5h (checklist CSV)
- **Total: 2.5h**

---

## 🎁 Bonus Ideas (Lower Effort, Still Valuable)

| # | Idea | Effort | Value | Why | Implementation |
|---|---|---|---|---|---|
| **B1** | Device Groups/Clusters | S | HIGH | Group by function: web-tier, db-tier, storage | Add `group` field, filter by group in list view |
| **B2** | Cost Calculator | S | MEDIUM | Sum device costs, show total investment | Dashboard widget, export with totals |
| **B3** | CSV Import/Export | S | HIGH | Users love spreadsheets | Extend HT-012/013 to support CSV + field mapping |
| **B4** | Device Checklists | M | MEDIUM | Pre-deployment, maintenance, decommission | New model: Checklist with device_id + items |
| **B5** | Change History (Audit Log) | M | MEDIUM | Who changed what and when | Add audit_log table, log all mutations |
| **B6** | Read-Only QR Codes | S | MEDIUM | Scan to quickly access device details | Generate QR → device-detail URL |
| **B7** | Performance Alerts | M | MEDIUM | Integration with Grafana for threshold alerts | Optional: webhook receiver for Grafana alerts |
| **B8** | Device Search by IP (reverse lookup) | S | HIGH | "What device owns 10.0.0.5?" | Extend search API with IP reverse search |

---

## 🔄 Already Well-Covered (Don't Duplicate)

These are in the backlog or completed:

✅ **HT-044** — Power usage tracking (watts + aggregation)  
✅ **HT-042** — Device attachments & photos  
✅ **HT-008** — Geographic map view (Leaflet)  
✅ **HT-043** — QR code labels for devices  
✅ **HT-014** — Export canvas to PNG/SVG  
✅ **HT-037** — Connection port / interface mapping  
✅ **HT-022** — Networks / VLANs / Subnets  
✅ **HT-024** — IPAM (IP address management)  
✅ **HT-023** — Services with dependencies  

**Phase 2 (LightTower):**  
✅ **LT-001** — Proxmox auto-discovery  
✅ **LT-002** — Docker auto-discovery  
✅ **LT-006** — Scheduled backup automation  
✅ **LT-007** — Audit log  

---

## 📊 Prioritization Matrix

```
Value    High |  #1 Cable       #2 Firmware  #3 Asset      #5 Backup
         High |  Ports          Tracking     Lifecycle     Status
              |
         Med  |                                #4 Docs Links
              |
         Low  |
              |
              +─────────────────────────────────────────────
                Low            Medium           High
                           Effort/Complexity

Quick Wins (Small Effort, High Value):
1. Firmware tracking (#2) — 2h, solves real need
2. Quick links (#4) — 1.5h, improves UX significantly
3. CSV import/export (B3) — 2h, high user demand

Medium Term (Medium Effort, High Value):
1. Cable management (#1) — 4h, solves major pain point
2. Backup tracking (#5) — 2.5h, prevents disasters
3. Asset lifecycle (#3) — 3h, enables planning
```

---

## 🚀 Recommended Roadmap

### Sprint 1 (Week 1-2): Quick Wins
- [ ] **B2** Cost Calculator (1h) — Dashboard widget
- [ ] **#2** Firmware Tracking (2h) — Model + UI
- [ ] **#4** Quick Links (1.5h) — High UX improvement

**Total: 4.5 hours** (Perfect for slow-moving sprint)

### Sprint 2 (Week 3-4): Major Features
- [ ] **#1** Cable & Port Management (4h) — Phase 1 (model + basic UI)
- [ ] **#5** Backup Status Tracking (2.5h) — Model + dashboard

**Total: 6.5 hours** (Pairs well with a story)

### Sprint 3+ (Future)
- [ ] **#1** Cable Management Phase 2 — Reports + visualization
- [ ] **#3** Asset Lifecycle (3h) — Full suite
- [ ] **B3** CSV Import/Export — Extend existing exports

---

## ❓ Questions for Product-Owner

Before implementing, clarify:

1. **Cable Management:** 
   - Should we support multiple connections per port (trunk lines)?
   - Cable type enum (Cat5e, Cat6, Cat6a, Fiber, PoE) or free text?

2. **Firmware Tracking:**
   - Should we integrate with vendor APIs to auto-fetch latest versions?
   - Or manual entry only?

3. **Backup Status:**
   - Can users manually update status, or should we integrate with backup tools?
   - How detailed should backup errors be (just text, or structured fields)?

4. **Asset Lifecycle:**
   - Should warranty data be auto-fetched from device model?
   - Or manual entry only?

5. **Prioritization:**
   - Which features align with business goals for next quarter?
   - Any competitive or feature-parity concerns?

---

## 📝 Next Steps

**For PM:**
1. Triage these ideas into backlog/icebox/reject
2. Prioritize top 3 for implementation
3. Clarify dependencies with design/engineering

**For Product-Owner:**
1. Align with user feedback (which pain points are most common?)
2. Decide on scope (e.g., auto-fetch versions or manual entry?)
3. Create stories with acceptance criteria

**For Feature-Engineer:**
1. Estimate implementation effort for top features
2. Identify technical blockers or dependencies
3. Suggest phased rollout (e.g., Phase 1 = data model, Phase 2 = UI/reports)

---

## 📚 References

- Backlog: `doc/backlog.md`
- Tracker: `doc/tracker.md`
- Architecture: `CLAUDE.md`
- Code Audit: `doc/bugs/recommendation.md`
