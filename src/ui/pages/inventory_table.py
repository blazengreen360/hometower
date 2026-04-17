"""Inventory table columns, body-slot template, and row builder."""
from collections.abc import Callable
from datetime import datetime

from nicegui import ui
from nicegui.elements.table import Table

from src.models.device import DeviceResponseEnriched
from src.ui.design.tokens import (
    DEVICE_TYPE_ICONS,
)

# Quasar badge colour names by DeviceStatus value
_STATUS_COLORS: dict[str, str] = {
    "Active": "positive",
    "Offline": "grey",
    "Maintenance": "orange",
    "Planned": "info",
    "Decommissioned": "negative",
}

_INVENTORY_BASE_COLUMNS: list[dict[str, object]] = [
    {"name": "icon", "label": "", "field": "icon", "sortable": False, "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
    {"name": "type", "label": "Type", "field": "type", "sortable": True, "align": "left"},
]

_INVENTORY_TRAILING_COLUMNS: list[dict[str, object]] = [
    {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "left"},
    {"name": "ip", "label": "IP", "field": "ip", "sortable": True, "align": "left"},
    {"name": "tags", "label": "Tags", "field": "tags", "sortable": False, "align": "left"},
    {"name": "location", "label": "Location", "field": "location", "sortable": True, "align": "left"},
    {"name": "services", "label": "Services", "field": "services", "sortable": False, "align": "left"},
    {"name": "networks", "label": "Networks", "field": "networks", "sortable": False, "align": "left"},
    {"name": "updated", "label": "Updated", "field": "updated", "sortable": False, "align": "left"},
    {"name": "actions", "label": "Actions", "field": "actions", "sortable": False, "align": "left"},
]


def inventory_table_columns(show_power: bool) -> list[dict[str, object]]:
    """Return table columns with optional Power (W) support."""
    columns = [dict(col) for col in _INVENTORY_BASE_COLUMNS]
    if show_power:
        columns.append(
            {
                "name": "power",
                "label": "Power (W)",
                "field": "power",
                "sortable": True,
                "align": "left",
            }
        )
    columns.extend(dict(col) for col in _INVENTORY_TRAILING_COLUMNS)
    return columns


_INVENTORY_TABLE_COLUMNS: list[dict[str, object]] = inventory_table_columns(show_power=False)

_ICON_SLOT = r"""
<q-td key="icon" :props="props">
  <q-icon :name="props.row.icon" size="sm" />
</q-td>
"""

_NAME_SLOT = r"""
<q-td key="name" :props="props">
  {{ props.row.name }}
  <q-icon v-if="props.row.is_orphaned" name="link_off" size="16px"
          color="grey-6" class="q-ml-xs">
    <q-tooltip>Not placed on any View</q-tooltip>
  </q-icon>
</q-td>
"""

_STATUS_SLOT = r"""
<q-td key="status" :props="props">
  <q-badge :color="props.row.status_color" :label="props.row.status" />
</q-td>
"""

_IP_SLOT = r"""
<q-td key="ip" :props="props" style="font-family:monospace">
  {{ props.row.ip || '\u2014' }}
  <q-btn v-if="props.row.ip" flat dense round size="xs"
         icon="content_copy"
         @click.stop="navigator.clipboard.writeText(props.row.ip); $q.notify({message:'IP copied', color:'primary', position:'top-right'})">
    <q-tooltip>Copy IP</q-tooltip>
  </q-btn>
</q-td>
"""

_POWER_SLOT = r"""
<q-td key="power" :props="props">
  {{ props.row.power === null || props.row.power === undefined ? '\u2014' : props.row.power + 'W' }}
</q-td>
"""

_SERVICES_SLOT = r"""
<q-td key="services" :props="props">
  <q-badge v-if="props.row.service_count > 0" color="blue-grey" :label="props.row.service_count + ' svc'" />
  <span v-else style="color:var(--ht-text-secondary)">\u2014</span>
</q-td>
"""

_NETWORKS_SLOT = r"""
<q-td key="networks" :props="props">
  <q-chip
    v-for="network in (props.row.networks || [])"
    :key="network.id"
    dense
    square
    :style="'background:' + network.color + ';color:var(--ht-text-on-accent)'"
    class="q-mr-xs q-mb-xs"
  >{{ network.label }}</q-chip>
  <span v-if="!props.row.networks || props.row.networks.length === 0" style="color:var(--ht-text-secondary)">\u2014</span>
</q-td>
"""

_ACTIONS_SLOT = r"""
<q-td key="actions" :props="props">
  <q-btn flat dense icon="edit" :href="'/inventory/edit/' + props.row.id">
    <q-tooltip>Edit device</q-tooltip>
  </q-btn>
  <q-btn flat dense icon="account_tree" :href="'/topology?device_id=' + props.row.id">
    <q-tooltip>Open in topology</q-tooltip>
  </q-btn>
  <button v-if="props.row.can_delete"
      type="button"
      class="q-btn q-btn-item non-selectable no-outline q-btn--flat q-btn--rectangle text-negative q-btn--actionable q-focusable q-hoverable q-btn--dense"
      :data-testid="'inventory-delete-' + props.row.id"
      :data-device-id="props.row.id"
      :data-device-name="props.row.name"
      :data-placement-count="props.row.placement_count"
      title="Delete device from inventory"
      onclick="emitEvent('inventory_delete', {id: this.dataset.deviceId, name: this.dataset.deviceName, placement_count: this.dataset.placementCount})">
      <span class="q-focus-helper"></span>
      <span class="q-btn__content text-center col items-center q-anchor--skip justify-center row">
          <i class="q-icon notranslate material-icons" aria-hidden="true" role="img">delete</i>
      </span>
  </button>
</q-td>
"""


def build_inventory_rows(
    devices: list[DeviceResponseEnriched],
    relative_time: Callable[[datetime], str],
    orphan_ids: set[str] | None = None,
    can_delete: bool = False,
    placement_counts: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    """Map enriched devices to table rows."""
    _orphans = orphan_ids or set()
    _placements = placement_counts or {}
    return [
        {
            "id": str(d.id),
            "icon": DEVICE_TYPE_ICONS.get(d.type, "devices"),
            "name": d.name,
            "type": d.type.value,
            "status": d.status.value if d.status else "Active",
            "status_color": _STATUS_COLORS.get(
                d.status.value if d.status else "Active", "grey"
            ),
            "ip": d.ip or "",
            "power": getattr(d, "power_watts", None),
            "tags": ", ".join(t.name for t in d.tags) if d.tags else "\u2014",
            "location": d.location_name or "",
            "service_count": len(d.services) if d.services else 0,
            "networks": [
              {"id": str(n.network_id), "label": n.name, "color": n.color}
              for n in d.networks
            ] if d.networks else [],
            "updated": relative_time(d.updated_at),
            "is_orphaned": str(d.id) in _orphans,
            "can_delete": can_delete,
            "placement_count": _placements.get(str(d.id), 0),
        }
        for d in devices
    ]


def create_inventory_table(
    *,
    can_bulk_edit: bool,
    on_select: Callable[[object], object],
    show_power: bool = False,
) -> Table:
    """Create inventory table with optional bulk selection and custom cell slots."""
    columns = inventory_table_columns(show_power)
    if can_bulk_edit:
        table = (
            ui.table(
                columns=columns,
                rows=[],
                row_key="id",
                selection="multiple",
                on_select=on_select,
            )
            .classes("w-full")
            .style("background:var(--ht-bg-surface-raised); color:var(--ht-text-primary)")
        )
    else:
        table = (
            ui.table(
          columns=columns,
                rows=[],
                row_key="id",
            )
            .classes("w-full")
            .style("background:var(--ht-bg-surface-raised); color:var(--ht-text-primary)")
        )

    table.add_slot("body-cell-icon", _ICON_SLOT)
    table.add_slot("body-cell-name", _NAME_SLOT)
    table.add_slot("body-cell-status", _STATUS_SLOT)
    table.add_slot("body-cell-ip", _IP_SLOT)
    table.add_slot("body-cell-power", _POWER_SLOT)
    table.add_slot("body-cell-services", _SERVICES_SLOT)
    table.add_slot("body-cell-networks", _NETWORKS_SLOT)
    table.add_slot("body-cell-actions", _ACTIONS_SLOT)
    return table
