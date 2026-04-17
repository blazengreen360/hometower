---
name: hometower-product
description: Hometower product definition — what it does, who uses it, phase scopes, user archetypes, and app route table. Read this when you need product context for stories, personas, or user-facing design decisions.
---

# hometower-product

## What Hometower Does

Users drag and drop homelab devices (servers, switches, VMs, containers, services) onto a topology canvas and connect them. The diagram IS the inventory — searchable, tagged, with custom fields and notes. A map view handles geo-distributed infra.

## Users

- **Primary:** Solo homelabbers documenting their own stack
- **Secondary:** Small teams (Phase 2, LightTower brand)

## Phase Scopes

**Phase 1 (Hometower):** Topology canvas, map view, inventory search, RBAC (Admin/Contributor/Reader), tags, custom fields, locations, export/backup.

**Phase 2 (LightTower):** Proxmox/Docker/Home Assistant auto-discovery, multi-workspace, audit log, LDAP/SSO, Traefik SSL.

## User Archetypes

**The Beginner Homelabber (25-35)**
- 1 server (Proxmox/Unraid), 1 switch, 2-3 services (Plex, Nextcloud, Pi-hole)
- First time documenting. Moves slowly, reads labels, makes typos, deletes and re-adds.
- Goals: know what they have, remember what services run where

**The Intermediate Builder (30-45)**
- 3-5 servers, managed switch, NAS, UPS, 10-15 services
- Outgrown mental model. Works quickly, tries shortcuts, expects autosave.
- Goals: track IPs, document VLANs, share with partner for emergencies

**The Power Homelabber (28-50)**
- 10+ nodes, multiple VLANs, VMs/LXCs, colocated VPS, home + office
- Tests edge cases naturally (long names, special chars, many connections).
- Goals: complete topology map, geo map, exportable backup

**The Small Team IT Admin (30-50)**
- Shared lab for 3-8 people. Needs Contributor/Reader roles.
- Creates devices for colleagues, tests role boundaries.

## App Routes

| Route | Page | CRUD |
|---|---|---|
| `/` | Topology canvas | Add/edit/delete devices, draw connections |
| `/inventory` | Inventory list | Search, filter, view, edit |
| `/map` | Geographic map | View locations, click to see devices |
| `/devices/{id}` | Device detail | Full edit, custom fields, notes, tags |
| `/settings` | Settings | Export, backup, preferences |
| `/admin/users` | User management (Admin only) | Add/edit/delete users |

## Domain-Specific Workflows

1. Add server to canvas → place, add IP, connect to switch → verify in inventory
2. Document a VM → add VM type, set parent host → verify relationship
3. Tag multiple devices → create tag, apply to N devices → filter by tag → verify count
4. Custom fields → add serial_number, warranty_expiry, purchase_price → verify persist
5. Geo location → add VPS with lat/lng → verify map marker → click → see device
6. Export inventory → trigger JSON export → verify valid JSON
7. Diagram snapshot → export PNG → verify non-empty image

## Observability Thresholds

| Area | Threshold |
|---|---|
| Canvas interaction (30 nodes) | < 100ms |
| Canvas interaction (50 nodes) | < 150ms |
| Canvas interaction (100 nodes) | < 300ms |
| Inventory filter/search (500 rows) | < 500ms |
| Page cold load | < 2s |
