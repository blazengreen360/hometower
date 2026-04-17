# Hometower — Site Map & Navigation Flows

> **Cross-references:** [app-shell.md](app-shell.md) for shell layout · [pages.md](pages.md) for per-page wireframes · [components.md](components.md) for NavItem component

---

## 1. Page Hierarchy

```
/ (root)
├── /login                     ← Public (unauthenticated)
├── / (Dashboard)              ← All authenticated roles
├── /topology                  ← Contributor, Admin
├── /inventory                 ← All authenticated roles
├── /map                       ← All authenticated roles  [Placeholder — HT-008]
├── /settings
│   ├── /settings/locations    ← Admin only
│   ├── /settings/users        ← Admin only
│   └── /settings/data         ← Admin only
└── /access-denied             ← Shown on 403, no role required
```

---

## 2. Route Table

| Route                | Page Title          | Auth Required | Roles Allowed             | Nav Section     |
|----------------------|---------------------|---------------|---------------------------|-----------------|
| `/login`             | Login               | No            | —                         | Outside shell   |
| `/`                  | Dashboard           | Yes           | Admin, Contributor, Reader| Primary nav     |
| `/topology`          | Topology            | Yes           | Admin, Contributor        | Primary nav     |
| `/inventory`         | Inventory           | Yes           | Admin, Contributor, Reader| Primary nav     |
| `/map`               | Map *(placeholder)* | Yes           | Admin, Contributor, Reader| Primary nav     |
| `/settings/locations`| Settings › Locations| Yes           | Admin                     | Settings group  |
| `/settings/users`    | Settings › Users    | Yes           | Admin                     | Settings group  |
| `/settings/data`     | Settings › Data     | Yes           | Admin                     | Settings group  |
| `/access-denied`     | Access Denied       | No            | —                         | Outside shell   |

**Role definitions:** Reader (read-only), Contributor (read + write devices/connections), Admin (full access including settings).

---

## 3. Navigation Hierarchy in Sidebar

```
Primary
  □  Dashboard         /
  □  Topology          /topology
  □  Inventory         /inventory
  □  Map               /map          [badge: "Soon"]

────────────────────────
Settings (Admin only)
  □  Locations         /settings/locations
  □  Users             /settings/users
  □  Data              /settings/data
```

The Settings group is hidden entirely for Contributor and Reader roles. The separator between Primary and Settings is a labelled divider: `SETTINGS` in muted uppercase.

---

## 4. Navigation Flows

### 4.1 Login → Dashboard

```
[Browser: /]
    │
    ▼
[Auth Guard: no token?]
    │ yes
    ▼
[/login]
    ├─ User enters email + password → POST /api/auth/login
    ├─ 200 OK → save JWT to sessionStorage + app.storage.user
    └─ Redirect → [/]  (Dashboard)
         │
         ▼
       [App Shell renders with sidebar + header]
```

**Error path:** 401 response → inline error label "Invalid email or password" (no redirect).

### 4.2 Dashboard → Topology

```
[/]  (Dashboard)
    ├─ Sidebar NavItem "Topology"       → navigate to /topology
    ├─ Quick Action "Open Topology"     → navigate to /topology
    └─ Stat card "Devices" (if linked)  → navigate to /inventory
```

### 4.3 Sidebar Navigation (General)

```
[Any authenticated page]
    ├─ Click NavItem                     → ui.navigate.to(route)
    ├─ Sidebar collapsed (icon-only)     → hover shows tooltip with page name
    └─ Keyboard: Tab to NavItem + Enter  → same as click
```

Active state: the current route's NavItem shows the active indicator (left border + background tint). See [app-shell.md § 3](app-shell.md).

### 4.4 Settings Sub-Navigation

Settings pages share the main sidebar's Settings group. There is no additional sub-nav bar — the three settings routes are three separate NavItems in the sidebar's Settings section.

```
[/settings/locations]
    │ Sidebar: "Locations" NavItem active
    │ Sidebar: "Users", "Data" NavItems visible, inactive
    └─ Click "Users" → /settings/users
```

### 4.5 Logout Flow

```
[Header: UserMenu dropdown]
    └─ "Sign out" item
           │
           ├─ Clear app.storage.user
           ├─ Clear sessionStorage 'access_token'
           └─ Redirect → /login
```

No confirmation dialog for logout.

### 4.6 Access Denied (403)

```
[Auth Guard: role insufficient]
    └─ Redirect → /access-denied
           │
           ├─ Shows error card with role explanation
           └─ "Go to Dashboard" button → /
```

---

## 5. Deep-Link Behaviour

| Scenario | Behaviour |
|---|---|
| Unauthenticated user visits `/topology` | Redirect to `/login`, after login redirect back to `/topology` |
| Reader visits `/settings/users` | Redirect to `/access-denied` |
| Authenticated user visits `/login` | Redirect to `/` |
| 404 unknown route | NiceGUI default 404; future: styled 404 page |

---

## 6. Breadcrumbs

Used in the header for all settings pages. Dashboard, Topology, Inventory, and Map are top-level pages with no breadcrumb trail (only the page title appears in the header).

| Page | Breadcrumb |
|---|---|
| `/settings/locations` | Settings › Locations |
| `/settings/users` | Settings › Users |
| `/settings/data` | Settings › Data |

See [components.md § Breadcrumb](components.md) for the Breadcrumb component spec.
