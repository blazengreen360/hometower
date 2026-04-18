"""Settings users table configuration."""

from src.ui.utils.formatting import browser_local_cell_expression
from src.ui.utils.formatting import enrich_browser_local_timestamp_rows

SETTINGS_USERS_COLUMNS: list[dict[str, object]] = [
    {"name": "username", "label": "Username", "field": "username", "sortable": True},
    {"name": "email", "label": "Email", "field": "email", "sortable": True},
    {"name": "role", "label": "Role", "field": "role", "sortable": True},
    {"name": "last_active", "label": "Last Active", "field": "last_active_sort", "sortable": True},
    {"name": "is_active", "label": "Active", "field": "is_active", "sortable": True},
    {"name": "actions", "label": "Actions", "field": "actions", "align": "right", "style": "width: 1%; white-space: nowrap;", "headerStyle": "width: 1%; white-space: nowrap;"},
]

SETTINGS_USERS_BODY_SLOT = """ 
<q-tr :props="props">
    <q-td key="username">{{ props.row.username }}</q-td>
    <q-td key="email">{{ props.row.email }}</q-td>
    <q-td key="role">{{ props.row.role }}</q-td>
    <q-td key="last_active">
        {{ __LAST_ACTIVE_DISPLAY__ }}
        <q-tooltip v-if="props.row.last_active_iso">{{ props.row.last_active_iso }}</q-tooltip>
    </q-td>
    <q-td key="is_active">{{ props.row.is_active ? 'Yes' : 'No' }}</q-td>
    <q-td key="actions" class="text-right">
        <div class="row no-wrap justify-end q-gutter-xs">
            <q-btn flat dense round size="sm" icon="edit" class="ht-btn-icon ht-btn-icon-secondary" @click="() => $parent.$emit('edit', props.row)">
                <q-tooltip>Edit user</q-tooltip>
            </q-btn>
            <q-btn flat dense round size="sm" icon="delete" class="ht-btn-icon ht-btn-icon-danger" :disabled="props.row.is_self" @click="() => $parent.$emit('delete', props.row)">
                <q-tooltip>{{ props.row.is_self ? 'You cannot delete your own account' : 'Delete user' }}</q-tooltip>
            </q-btn>
        </div>
    </q-td>
</q-tr>
""".replace("__LAST_ACTIVE_DISPLAY__", browser_local_cell_expression("last_active"))


def build_user_rows(users_list: list[dict[str, object]], current_user_id: str) -> list[dict[str, object]]:
    """Attach self and browser-local timestamp metadata for the IAM table."""
    prepared_rows = [
        {
            **user,
            "is_self": user["id"] == current_user_id,
            "last_active_source": user.get("last_active") or user.get("updated_at") or user.get("created_at"),
        }
        for user in users_list
    ]
    return enrich_browser_local_timestamp_rows(
        prepared_rows,
        source_key="last_active_source",
        target_key="last_active",
    )