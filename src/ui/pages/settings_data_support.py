"""Support helpers for the Settings -> Data page."""
import json


def export_download_js(token: str) -> str:
    """Return JS for authenticated export download."""
    bearer = f"Bearer {token}" if token else ""
    return f"""
        (async () => {{
            const authHeader = {json.dumps(bearer)};
            const headers = {{}};
            if (authHeader) headers.Authorization = authHeader;

            const showError = (message) => {{
                const existing = document.getElementById('ht-export-error');
                if (existing) existing.remove();

                const banner = document.createElement('div');
                banner.id = 'ht-export-error';
                banner.setAttribute('role', 'alert');
                const styles = getComputedStyle(document.documentElement);
                banner.style.cssText =
                    'position:fixed;top:16px;right:16px;max-width:420px;'
                    + 'padding:12px 14px;border-radius:8px;z-index:100000;'
                    + 'background:' + styles.getPropertyValue('--ht-bg-surface-raised').trim() + ';'
                    + 'border:1px solid ' + styles.getPropertyValue('--ht-error').trim() + ';'
                    + 'color:' + styles.getPropertyValue('--ht-text-primary').trim() + ';'
                    + 'box-shadow:' + styles.getPropertyValue('--ht-shadow-md').trim() + ';'
                    + 'font-size:14px;line-height:1.4;';
                banner.textContent = message;
                document.body.appendChild(banner);
                window.setTimeout(() => {{
                    if (banner.parentNode) banner.parentNode.removeChild(banner);
                }}, 6000);
            }};

            try {{
                const response = await fetch('/api/export', {{
                    method: 'GET',
                    credentials: 'include',
                    headers,
                }});

                if (!response.ok) {{
                    if (response.status === 401) {{
                        showError('Export failed: your session may have expired. Please sign in again.');
                        return;
                    }}
                    if (response.status === 403) {{
                        showError('Export failed: your account does not have permission to export data.');
                        return;
                    }}
                    if (response.status >= 500) {{
                        showError('Backup failed: the server could not create the export. Please try again.');
                        return;
                    }}
                    showError(`Backup failed (${{response.status}}). Please try again.`);
                    return;
                }}

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement('a');
                anchor.href = url;
                anchor.download = 'hometower-export.json';
                document.body.appendChild(anchor);
                anchor.click();
                anchor.remove();
                URL.revokeObjectURL(url);
            }} catch (_error) {{
                showError('Backup failed: network error while contacting the server.');
            }}
        }})();
    """
