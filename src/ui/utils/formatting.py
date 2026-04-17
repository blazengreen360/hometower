"""Shared formatting helpers for UI table rendering."""

_DASH = "\u2014"

LAST_MODIFIED_BROWSER_LOCAL_BRIDGE_SCRIPT = """
<script>
(function () {
    const localFormatter = new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });

    const formatLastModifiedLocal = window.htFormatLastModifiedLocal || function (isoValue, fallbackValue) {
        if (!isoValue) {
            return fallbackValue || '—';
        }

        const parsed = new Date(isoValue);
        if (Number.isNaN(parsed.getTime())) {
            return fallbackValue || isoValue;
        }

        return localFormatter.format(parsed);
    };

    const resolveVueApp = function () {
        const rootCandidates = [];
        const appRoot = document.querySelector('#app');
        if (appRoot) {
            rootCandidates.push(appRoot);
        }

        const dataAppRoots = document.querySelectorAll('[data-v-app]');
        for (const candidate of dataAppRoots) {
            if (candidate && rootCandidates.indexOf(candidate) === -1) {
                rootCandidates.push(candidate);
            }
        }

        for (const candidate of rootCandidates) {
            if (candidate && candidate.__vue_app__) {
                return candidate.__vue_app__;
            }
        }

        return null;
    };

    const registerVueFormatter = function () {
        const vueApp = resolveVueApp();
        if (!vueApp || !vueApp.config || !vueApp.config.globalProperties) {
            return false;
        }
        vueApp.config.globalProperties.$htFormatLastModifiedLocal = formatLastModifiedLocal;
        return true;
    };

    const ensureVueFormatter = function () {
        if (registerVueFormatter()) {
            return;
        }

        let attempts = 0;
        const retryTimer = setInterval(function () {
            attempts += 1;
            if (registerVueFormatter() || attempts >= 40) {
                clearInterval(retryTimer);
            }
        }, 50);
    };

    window.htFormatLastModifiedLocal = formatLastModifiedLocal;
    ensureVueFormatter();
})();
</script>
""".strip()

LAST_MODIFIED_BROWSER_LOCAL_CELL_EXPRESSION = (
    "($htFormatLastModifiedLocal && $htFormatLastModifiedLocal(props.row.last_modified_iso, props.row.last_modified_display)) || props.row.last_modified_display"
)


def format_last_modified_timestamp(
    iso_timestamp: str | None,
    *,
    allow_raw_iso_fallback: bool = True,
) -> str:
    """Return fallback text for last-modified display handling."""
    if iso_timestamp is None:
        return _DASH

    timestamp = iso_timestamp.strip()
    if not timestamp:
        return _DASH
    if allow_raw_iso_fallback:
        return timestamp
    return _DASH


def enrich_last_modified_rows(items: object) -> list[dict[str, object]]:
    """Attach fallback, ISO, and sortable last_modified values for table rows."""
    if not isinstance(items, list):
        return []

    rows: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        row: dict[str, object] = dict(item)
        raw_last_modified = row.get("last_modified")
        iso_value = raw_last_modified.strip() if isinstance(raw_last_modified, str) else ""
        row["last_modified_sort"] = iso_value
        row["last_modified_iso"] = iso_value
        row["last_modified"] = format_last_modified_timestamp(iso_value)
        row["last_modified_display"] = format_last_modified_timestamp(
            iso_value,
            allow_raw_iso_fallback=False,
        )
        rows.append(row)

    return rows
