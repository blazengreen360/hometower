"""Workspace detail table configuration."""

TOPOLOGY_TABLE_COLUMNS: list[dict[str, object]] = [
    {"name": "name", "label": "Name", "field": "name", "sortable": True},
    {"name": "tags", "label": "Tags", "field": "tags"},
    {"name": "last_modified", "label": "Last Modified", "field": "last_modified_sort", "sortable": True},
    {"name": "actions", "label": "Actions", "field": "actions", "align": "right", "style": "width: 1%; white-space: nowrap;", "headerStyle": "width: 1%; white-space: nowrap;"},
]

TOPOLOGY_TABLE_BODY_SLOT = r"""
<q-tr :props="props">
    <q-td key="name">
        <a href="#" class="ht-table-link" @click.prevent="$parent.$emit('open', props.row)">
            {{ props.row.name }}
        </a>
    </q-td>
    <q-td key="tags">
        <q-chip v-for="tag in (props.row.tags || [])" :key="tag" :label="tag" dense size="sm" />
    </q-td>
    <q-td key="last_modified">
        {{ __LAST_MODIFIED_DISPLAY__ }}
        <q-tooltip v-if="props.row.last_modified_iso">{{ props.row.last_modified_iso }}</q-tooltip>
    </q-td>
    <q-td key="actions" class="text-right">
        <div class="row no-wrap justify-end q-gutter-xs">
            <q-btn flat dense round size="sm" icon="open_in_new" class="ht-btn-icon ht-btn-icon-secondary" @click="() => $parent.$emit('open', props.row)">
                <q-tooltip>Open topology</q-tooltip>
            </q-btn>
            <q-btn flat dense round size="sm" icon="edit" class="ht-btn-icon ht-btn-icon-secondary" @click="() => $parent.$emit('rename', props.row)">
                <q-tooltip>Rename topology</q-tooltip>
            </q-btn>
            <q-btn flat dense round size="sm" icon="delete" class="ht-btn-icon ht-btn-icon-danger" @click="() => $parent.$emit('delete', props.row)">
                <q-tooltip>Delete topology</q-tooltip>
            </q-btn>
        </div>
    </q-td>
</q-tr>
"""