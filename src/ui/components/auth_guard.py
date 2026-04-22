"""UI authentication and role guard utilities.

This module hides the decision of how NiceGUI pages verify authentication
and enforce role requirements. Import these helpers at the top of every
protected page — do not duplicate auth logic in individual pages.
"""
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from nicegui import app as nicegui_app
from nicegui import ui

from src.domain.rbac import can_perform
from src.models.types import Role


def safe_next_path(path: str) -> Optional[str]:
    """Return *path* if it is a safe internal redirect target, else None.

    Rules (open-redirect prevention):
      - Must be non-empty and not only whitespace
      - Must start with /
      - Must not start with // (protocol-relative URL)
      - Must not contain :// (absolute URL)
    """
    if not path or not path.strip():
        return None
    if not path.startswith("/"):
        return None
    if path.startswith("//"):
        return None
    if "://" in path:
        return None
    return path


def get_ui_role() -> Optional[Role]:
    """Return the authenticated user's role from storage, or None if expired/missing."""
    role_str = nicegui_app.storage.user.get("role")
    token_exp = nicegui_app.storage.user.get("token_exp", 0)
    if not role_str or datetime.now(timezone.utc).timestamp() >= int(token_exp):
        for key in ("role", "user_id", "token_exp", "username"):
            nicegui_app.storage.user.pop(key, None)
        return None
    try:
        return Role(role_str)
    except ValueError:
        return None


def redirect_if_unauthenticated(current_path: Optional[str] = None) -> bool:
    """Redirect to /login if no valid token is present.

    When *current_path* is provided, a safe internal target is preserved in the
    login redirect via ``?next=...``. If a token was present but is now
    invalid/expired, the redirect additionally includes ``expired=1`` so the
    login page can show an expiry banner before returning the user after
    re-login.

    Args:
        current_path: The page's own route (e.g. ``"/topology"``). Pass this
                      so expired-session redirects carry the ``next`` param.

    Returns:
        True if a redirect was issued (caller must return immediately).
    """
    had_token = bool(nicegui_app.storage.user.get("role"))
    cleaned = safe_next_path(current_path) if current_path else None
    if get_ui_role() is None:
        if cleaned:
            if had_token:
                ui.navigate.to(f"/login?expired=1&next={quote(cleaned, safe='')}")
            else:
                ui.navigate.to(f"/login?next={quote(cleaned, safe='')}")
            return True
        ui.navigate.to("/login")
        return True
    return False


def redirect_if_insufficient_role(minimum: Role) -> bool:
    """Redirect to /403 if the user's role is below *minimum*.

    Must be called after redirect_if_unauthenticated().

    Returns:
        True if a redirect was issued (caller must return immediately).
    """
    role = get_ui_role()
    if role is None or not can_perform(role, minimum):
        ui.navigate.to("/403")
        return True
    return False
