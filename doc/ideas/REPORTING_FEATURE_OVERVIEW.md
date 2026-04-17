# Reporting Feature: Generate Homelab Report

**Status:** Flagship feature for Phase 2  
**Priority:** ⭐⭐⭐⭐⭐ (High Value)  
**Effort:** M (4-7 hours)  
**Unique Value:** No other homelab tool has this

---

## 🎯 What It Does

**Generate professional reports about your homelab in one click.**

The reporting feature lets you create scoped, customizable reports that answer questions like:
- "How much have I invested in hardware?"
- "What's aging and needs replacement?"
- "What are single points of failure?"
- "When did I last back up each device?"
- "What critical services depend on what devices?"

---

## 📋 Report Types (7 Templates)

### 1. **Executive Summary** (1 page)
Print-friendly overview of your entire homelab.

**Example Output:**
```
═══════════════════════════════════════════════════════════
                   HOMELAB OVERVIEW REPORT
                        April 13, 2026
═══════════════════════════════════════════════════════════

📊 INVENTORY SNAPSHOT
├─ Total Devices: 18
├─ Active Services: 12
├─ Networks/VLANs: 3
└─ Locations: 2 (home office, garage)

💰 INVESTMENT
├─ Total Hardware Value: $8,450
├─ Avg Device Cost: $469
└─ Oldest Device: 2 years 4 months

⚡ POWER & CAPACITY
├─ Current Draw: 2.3 kW (46% of capacity)
├─ Available Headroom: 2.7 kW
└─ Growth Potential: Can add ~5 more servers

🔒 RESILIENCE
├─ Devices with Backups: 12/18 (67%)
├─ Last Backup Age: 3 hours (fresh)
├─ Single Points of Failure: 3
└─ Risk Level: MEDIUM

🗓️ LIFECYCLE
├─ Devices <1 year old: 5
├─ Devices >3 years old: 4
├─ Warranty Expiring Soon: 2
└─ Avg Device Age: 2 years 1 month

Last Updated: April 13, 2026 at 10:32 UTC
═══════════════════════════════════════════════════════════
```

---

### 2. **Inventory Report** (Detailed Spreadsheet)
Complete device list with all metadata.

**Example Output:**
```
Device Name      | Type     | Status    | Cost  | IP Addr      | OS Version    | Backup
─────────────────┼──────────┼───────────┼───────┼──────────────┼───────────────┼──────────────
proxmox-01       | Server   | Active    | $1200 | 10.0.1.10    | Proxmox 8.0.4 | Daily (NAS)
nas-01           | NAS      | Active    | $599  | 10.0.1.20    | TrueNAS 12.0  | S3 (off-site)
switch-core      | Switch   | Active    | $349  | 10.0.1.254   | N/A            | N/A
ap-wifi-01       | Access Pt| Active    | $89   | 10.0.1.30    | N/A            | N/A
router-isp       | Router   | Active    | $200  | 10.0.0.1     | RouterOS 7.2   | N/A
vm-plex          | VM       | Active    | $0    | 10.0.1.100   | Ubuntu 22.04   | Snapshot
vm-vaultwarden   | VM       | Active    | $0    | 10.0.1.101   | Ubuntu 22.04   | Daily
...
─────────────────┴──────────┴───────────┴───────┴──────────────┴───────────────┴──────────────
TOTALS:          18 devices, 15 active, 1 offline, 2 maintenance
```

---

### 3. **Network Topology Diagram**
ASCII or visual diagram of device connections.

**Example Output:**
```
                    ╔═══════════════╗
                    ║   ISP/WAN     ║
                    ╚═══════════════╝
                           │
                           │ (100Mbps)
                           │
                    ╔═══════════════╗
                    │  router-isp   │
                    ╚═══════════════╝
                      │            │
            ┌─────────┴────────────┴─────────┐
            │                                 │
     ╔═════════════╗                  ╔════════════╗
     │ switch-core │                  │ ap-wifi-01 │
     ║ (24-port)   ║                  ╚════════════╝
     ╚═════════════╝
     │    │    │    │
  ┌──┴─┬──┴─┬──┴─┬──┴─┐
  │    │    │    │    │
 NAS Server Server UPS Mgmt
(10GbE) (1GbE) (1GbE) (1GbE) (1GbE)
```

---

### 4. **Service Dependencies Report**
Shows which applications depend on which devices.

**Example Output:**
```
🎯 CRITICAL SERVICES & DEPENDENCIES

Plex (media server)
├─ Depends on: proxmox-01 (KVM hypervisor)
│   └─ Depends on: nas-01 (shared storage /mnt/media)
│       └─ Depends on: switch-core (10GbE link)
│           └─ Depends on: router-isp (internet)
│
├─ Redundancy: NONE ⚠️ (single point of failure)
├─ RTO (Recovery Time): 2 hours
└─ RPO (Recovery Point): 1 day

Vaultwarden (password vault)
├─ Depends on: proxmox-01 (KVM hypervisor)
│   ├─ Depends on: nas-01 (PostgreSQL database on shared storage)
│   └─ Depends on: router-isp (HTTPS from external)
│
├─ Redundancy: Backup VM on second Proxmox node ✓
├─ RTO: 15 minutes (fast restart)
└─ RPO: 1 hour (hourly snapshots)

Home Assistant (automation)
├─ Depends on: proxmox-01 (KVM)
│   └─ Depends on: ap-wifi-01 (Zigbee/WiFi device control)
│
├─ Redundancy: NONE ⚠️
├─ RTO: 10 minutes
└─ RPO: Daily snapshot

🔴 CRITICAL FINDINGS:
  ⚠️  Plex: single point of failure if NAS dies
  ⚠️  No redundant Proxmox hosts
  ⚠️  Single internet circuit (no failover)
  ✓ Vaultwarden: good redundancy
```

---

### 5. **Capacity & Planning Report**
Utilization and growth projections.

**Example Output:**
```
📈 CAPACITY & PLANNING ANALYSIS

POWER CONSUMPTION
├─ Current Draw: 2.3 kW
├─ Peak Capacity: 5.0 kW (UPS-backed)
├─ Utilization: 46%
├─ Available Headroom: 2.7 kW
│
└─ Projection:
    Current growth: +0.3 kW / 6 months
    → Upgrade needed in: 18 months
    → Recommendation: Plan UPS upgrade for next year

STORAGE CAPACITY
├─ Total: 100 TB (NAS + local)
├─ Used: 65 TB
├─ Available: 35 TB
├─ Utilization: 65%
│
└─ Projection:
    Growth rate: +2 TB / month
    → Capacity full in: 17.5 months
    → Recommendation: Add 50 TB NAS next quarter

NETWORK THROUGHPUT
├─ Main Links: 1GbE (bottleneck)
├─ Uplinks: 10GbE (underutilized)
├─ Current usage: 200 Mbps average (20% of 1GbE)
│
└─ Recommendation:
    Upgrade 1GbE links to 10GbE to Proxmox hosts
    → Would improve VM performance by 3-5x
    → Cost: ~$300 (NICs + cabling)

RECOMMENDATIONS (PRIORITY ORDER)
1. ✅ Add redundant Proxmox host (enables HA)
2. ✅ Upgrade NAS to redundant pair (RAID across units)
3. ⚠️  Add 10GbE connectivity to servers
4. ⚠️  Plan storage expansion (17 months out)
5. ⚠️  Plan power upgrade (18 months out)
```

---

### 6. **Hardware Lifecycle Report**
Device age, warranty, and replacement planning.

**Example Output:**
```
🔄 HARDWARE LIFECYCLE & REPLACEMENT PLANNING

DEVICES BY AGE
├─ New (< 6 months):     2 devices ✓
│  └─ proxmox-02, ap-wifi-02
│
├─ Young (6 mo - 1 yr):  3 devices ✓
│  └─ nas-backup, router-edgeos, ups-new
│
├─ Mid-life (1-3 years): 8 devices ⚠️ (monitor)
│  └─ proxmox-01, nas-01, switch-core, ...
│
├─ Aging (3-5 years):    4 devices 🔴 (plan replacement)
│  └─ nas-old, mgmt-server, ap-wifi-old, ...
│
└─ End-of-Life (>5 yrs): 1 device 🔴🔴 (replace soon)
   └─ switch-old (end-of-life, security risks)

WARRANTY STATUS
├─ Active (warranty remaining):    12 devices ✓
│  └─ Average: 18 months remaining
│
├─ Expiring Soon (<90 days):       2 devices ⚠️
│  └─ switch-core (expires June 15)
│  └─ nas-01 (expires July 1)
│
└─ Expired (out of warranty):     4 devices
   └─ Repair cost now out of pocket

REPLACEMENT TIMELINE
┌─────────────────────────────────────────┐
│ Q1 2026 │          Replace switch-old    │
├─────────────────────────────────────────┤
│ Q2 2026 │   Monitor aging devices for    │
│         │     performance degradation    │
├─────────────────────────────────────────┤
│ Q3 2026 │ Add storage (before 65TB limit)│
├─────────────────────────────────────────┤
│ Q4 2026 │ Add redundant Proxmox host     │
├─────────────────────────────────────────┤
│ Q1 2027 │ Consider NAS-01 replacement    │
│         │    (3 years old, heavy use)    │
└─────────────────────────────────────────┘

TOTAL 5-YEAR REPLACEMENT COST (ESTIMATE)
├─ Devices aging (3-5 yr) needing replacement: $3,500-5,000
├─ Add redundancy/growth: $2,000-3,000
└─ 5-Year Total Cost: ~$5,500-8,000 / 60 months = ~$100-130/month
```

---

### 7. **Risk & Resilience Report**
Single points of failure, backup status, RTO/RPO.

**Example Output:**
```
🛡️ RISK & RESILIENCE ASSESSMENT

SINGLE POINTS OF FAILURE (SPOF)

Critical SPOFs (causes complete outage if fails):
┌─────────────────────────────────────────────┐
│ 🔴 Internet Connection (only ISP)          │
│   ├─ Impact: All external services down    │
│   ├─ RTO (Recovery): Immediate failover    │
│   ├─ Probability: 0.5% / year (ISP SLA)    │
│   └─ Mitigation: Add 4G failover ($30/mo)  │
├─────────────────────────────────────────────┤
│ 🔴 Proxmox Host (only hypervisor)          │
│   ├─ Impact: All VMs down (Plex, Vault)    │
│   ├─ RTO: 30 min (restart + VM recovery)   │
│   ├─ Probability: 5% / year (hardware)     │
│   └─ Mitigation: Add redundant host ($1.2k)│
├─────────────────────────────────────────────┤
│ 🔴 NAS Storage (shared by all VMs)         │
│   ├─ Impact: Loss of Plex media + backups  │
│   ├─ RTO: 2-4 hours (NAS rebuild)          │
│   ├─ Probability: 2% / year (RAID-6)       │
│   └─ Mitigation: Add backup NAS ($600)     │
└─────────────────────────────────────────────┘

Non-critical SPOFs (degrades performance):
├─ Core Switch: Only network link (1 device)
│  └─ Workaround: WiFi fallback (slower)
├─ UPS: Only backup power (critical devices only)
│  └─ Workaround: Natural shutdown (1 hour battery)

BACKUP STATUS

Devices with Backups:
├─ Daily (snapshots): proxmox-01, nas-01 ✓
├─ Weekly (full copy): vm-plex, vm-vault ✓
├─ Monthly archive: critical data ✓
└─ Off-site: nas-01 → S3 (daily) ✓

Devices WITHOUT Backups (at risk):
├─ switch-core: no config backup 🔴
├─ router-isp: no config backup 🔴
├─ ap-wifi-01: no backup needed (auto-config)

Last Successful Backups:
├─ Proxmox: 2 hours ago (2026-04-13 12:30) ✓
├─ NAS: 4 hours ago (2026-04-13 10:15) ✓
├─ S3 sync: Yesterday (2026-04-12 23:45) ✓
└─ Backup Test: 30 days ago ⚠️ (due for retest)

OVERALL RISK SCORE: MEDIUM (6.5/10)
├─ Backup Status: GOOD (67% backed up)
├─ Redundancy: POOR (3 critical SPOFs)
├─ Recovery Readiness: FAIR (tested 30 days ago)
│
└─ CRITICAL ACTIONS:
   1. Test backup restore procedure (do NOW)
   2. Add redundant Proxmox host (Q4 priority)
   3. Backup router/switch configs (1 hour)
   4. Add 4G failover for internet (budget item)
```

---

## 📤 Output Formats

Choose your export format:

### **HTML** (Pretty & Printable)
- Professional formatting
- Interactive (expandable sections)
- Embeds charts and diagrams
- Print-friendly styling
- Share via email/link

### **PDF** (Professional Documents)
- Ready for insurance/documentation
- Archivable
- No dependencies
- Print perfectly

### **CSV** (Spreadsheet Compatible)
- Inventory report only
- Open in Excel/Google Sheets
- Easy to manipulate and pivot
- Ready for accounting software

### **JSON** (Programmatic Access)
- Structured data export
- Use in automation scripts
- Feed to other tools
- API-ready format

---

## 🎛️ Customization Options

**Scope Selector** — Choose what to include:
```
Report Scope:
├─ Entire Homelab ✓
├─ Workspace: "Home Network"
├─ Topology: "Production Services"
├─ Location: "Home Office"
├─ By Device Type: "All Servers"
└─ By Service: "Critical Infrastructure"
```

**Section Selector** — Pick which reports to include:
```
Include Sections:
☑ Executive Summary (1 page overview)
☑ Device Inventory (full list)
☑ Network Topology (diagram)
☑ Service Dependencies (critical paths)
☑ Capacity Analysis (growth projections)
☑ Hardware Lifecycle (replacement planning)
☑ Risk Assessment (SPOFs, backups)
```

**Options:**
```
□ Include financial data (costs, investment)
□ Include backup status
□ Include warranty status
□ Include contact info (sensitive, skip by default)
□ Include recommendations (insights)
□ Highlight critical findings
```

---

## 🖥️ User Interface

**New "Reports" section in Settings:**

```
Settings → Reports & Documentation
┌────────────────────────────────────────┐
│ 📊 REPORT GENERATOR                    │
├────────────────────────────────────────┤
│ Template: [Inventory Report ▼]         │
│ Scope: [Entire Homelab ▼]             │
│                                        │
│ Include Sections:                      │
│ ☑ Inventory table                     │
│ ☑ Network diagram                     │
│ ☑ Service dependencies                │
│ ☑ Capacity analysis                   │
│ ☑ Hardware lifecycle                  │
│ ☑ Backup & risk status                │
│                                        │
│ Output Format: [PDF ▼]                │
│                                        │
│ ☐ Include costs/investment            │
│ ☐ Highlight critical findings         │
│ ☐ Add recommendations                 │
│                                        │
│ [Generate Report Now]                 │
│ [Schedule Weekly Report] [Setup Email]│
├────────────────────────────────────────┤
│ 📁 RECENT REPORTS:                     │
├────────────────────────────────────────┤
│ • homelab-2026-04-13.pdf (2 min ago)  │
│   └─ Full inventory + capacity plan    │
│                                        │
│ • by-location-2026-04-13.pdf (today)  │
│   └─ Separate reports per location    │
│                                        │
│ • critical-services-2026-04-11.pdf    │
│   └─ Service dependencies only        │
│                                        │
│ [Download] [Email] [Share] [Delete]   │
└────────────────────────────────────────┘
```

---

## 💡 Use Cases

### **Use Case 1: Hardware Planning**
```
Scenario: "I want to plan next quarter's upgrades"

Action:
1. Go to Settings → Reports
2. Select "Capacity & Planning" template
3. Check "Include costs" and "Add recommendations"
4. Generate as PDF
5. Share with budget committee

Result: 
- Shows power headroom (2.7 kW available)
- Shows storage growth timeline (17 months until full)
- Recommends: upgrade NAS first ($600), then 10GbE ($300)
- Total recommendation: $900 budget needed
```

### **Use Case 2: Disaster Planning**
```
Scenario: "Our insurance agent needs proof of hardware value"

Action:
1. Select "Inventory Report" template
2. Scope: "Entire Homelab"
3. Include: costs, serial numbers, models
4. Export as CSV
5. Send to insurance company

Result:
- Professional itemized list
- Total value: $8,450
- Item-by-item breakdown for claim purposes
- Ready for accountant
```

### **Use Case 3: Risk Assessment**
```
Scenario: "I want to understand single points of failure"

Action:
1. Select "Risk & Resilience" template
2. Include: backup status, RTO/RPO, recommendations
3. Generate as PDF

Result:
- Shows 3 critical SPOFs
- Backup status (67% backed up)
- RTO estimates per service
- Prioritized remediation plan
- Identifies that NAS is critical
```

### **Use Case 4: Team Documentation**
```
Scenario: "I need to show my family my homelab"

Action:
1. Select "Executive Summary" template
2. Add "Network Topology Diagram"
3. Include "Service Dependencies"
4. Export as HTML (for web viewing)
5. Share link

Result:
- One-page overview (non-technical)
- Shows all services and what they depend on
- Nice diagram of network
- Non-technical family member understands setup
```

---

## ⚙️ Implementation Details

### **Database Model**
Minimal impact — all data already exists in Hometower:

```python
class Report(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(foreign_key="workspace.id")
    template: str  # "inventory", "topology", "risk", etc.
    scope: str     # "entire", "by_location", "by_service"
    created_by: UUID = Field(foreign_key="user.id")
    created_at: datetime
    filename: str
    size_bytes: int
    ttl_days: int = 7  # Auto-delete after 7 days
```

### **Tech Stack**
- **Template Engine:** Jinja2 (Python)
- **HTML → PDF:** wkhtmltopdf or WeasyPrint
- **CSV Export:** Python csv module
- **Charts:** Matplotlib or Chart.js
- **ASCII Diagrams:** Graphviz or custom text

---

## 📊 Effort Estimate

| Phase | Features | Effort | Timeline |
|---|---|---|---|
| **Phase 1** | Basic reports (HTML, PDF, CSV) | 4-6 hours | Week 1-2 |
| **Phase 2** | Rich formatting (charts, diagrams) | 2-3 hours | Week 3 |
| **Phase 3** | Scheduling, email delivery | 3-4 hours | Week 4+ |
| **Phase 4** | Grafana/Prometheus integration | 4-6 hours | Future |

---

## 🎁 Bonus Ideas

- **Scheduled Reports** — Auto-generate weekly/monthly
- **Email Delivery** — PDF arrives in inbox automatically
- **Diff Reports** — Compare "now" vs "last month"
- **Custom Templates** — Users create their own report format
- **Grafana Integration** — Pull live metrics into reports
- **Ansible Playbook Export** — Generate remediation playbooks from recommendations

---

## 🏆 Why This Feature Matters

1. **Unique** — No other homelab tool generates reports
2. **Practical** — Solves real problems (planning, documentation, compliance)
3. **Professional** — Looks impressive to non-technical people
4. **Justifies Tool** — Makes Hometower indispensable
5. **Monetizable** — Could be enterprise-only feature (scheduled reports, webhooks)

---

**Bottom Line:** This feature transforms Hometower from a cool visualization tool into a **documented, reportable, defensible infrastructure management system** that homelabbers will actually use for planning and compliance.
