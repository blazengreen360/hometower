"""Rich field render helpers for the device detail panel (HT-087)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import html
import ipaddress
import re

from nicegui import ui

_UNSAFE_MARKDOWN_LINK_PATTERN = re.compile(
    r"\]\(\s*(javascript|vbscript|data)\s*:",
    flags=re.IGNORECASE,
)
_BLOCKQUOTE_MARKER_PATTERN = re.compile(r"(?m)^(\s*)&gt;(?=(?:\s|$|&gt;))")


def _restore_blockquote_markers(escaped_markdown: str) -> str:
    """Restore leading markdown blockquote markers after HTML escaping."""
    return _BLOCKQUOTE_MARKER_PATTERN.sub(r"\1>", escaped_markdown)


def sanitize_markdown_notes(markdown_text: str | None) -> str:
    """Escape raw HTML and neutralize unsafe markdown link protocols."""
    escaped = html.escape(markdown_text or "")
    with_blockquotes = _restore_blockquote_markers(escaped)
    return _UNSAFE_MARKDOWN_LINK_PATTERN.sub("](#", with_blockquotes)


def _render_notes_preview(notes_container: ui.element, notes_value: str | None) -> None:
    notes_container.clear()
    with notes_container:
        rendered_notes = sanitize_markdown_notes(notes_value)
        if rendered_notes.strip() == "":
            ui.label("\u2014").style(
                "font-size:0.875rem; color:var(--ht-text-primary);"
            )
            return

        ui.markdown(rendered_notes).classes("w-full").props(
            'id="ht-device-notes-markdown"'
        ).style("font-size:0.875rem; color:var(--ht-text-primary);")
        ui.run_javascript(
            "const root=document.getElementById('ht-device-notes-markdown');"
            "if(root){root.querySelectorAll('a').forEach(function(a){"
            "a.target='_blank';a.rel='noopener noreferrer';});}"
        )


def render_markdown_notes_row(
    current: str | None,
    is_editor: bool,
    on_saved: Callable[[], None] | None = None,
    save_value: Callable[[object], Awaitable[bool]] | None = None,
) -> None:
    """Render markdown notes in read mode with raw textarea editing in edit mode."""
    state: dict[str, str | None] = {"notes": current}

    with ui.column().classes("w-full gap-1"):
        with ui.row().classes("items-center gap-1 w-full"):
            ui.label("Notes:").style(
                "font-size:0.875rem; color:var(--ht-text-secondary); min-width:44px;"
                " flex-shrink:0;"
            )
            ui.space()

        with ui.element("div").classes("w-full") as notes_read:
            _render_notes_preview(notes_read, state["notes"])

        if not is_editor:
            return

        with ui.column().classes("w-full gap-1").style("display:none") as notes_edit:
            notes_input = ui.textarea(value=current or "").props(
                'autogrow aria-label="Edit Notes"'
            ).classes("w-full").style("font-size:0.8125rem;")
            ui.label("Markdown supported.").style(
                "font-size:0.75rem; color:var(--ht-text-secondary);"
            )
            with ui.row().classes("items-center justify-end gap-1"):
                ui.button(icon="check").props(
                    "flat dense round size=xs aria-label=\"Save Notes\""
                ).style("color:var(--ht-success);").on("click", lambda: _save_notes())
                ui.button(icon="close").props(
                    "flat dense round size=xs aria-label=\"Cancel Notes Edit\""
                ).style("color:var(--ht-error);").on("click", lambda: _cancel_notes())

        def _start_notes_edit() -> None:
            notes_input.set_value(state["notes"] or "")
            notes_read.style("display:none")
            notes_edit.style("display:flex")

        def _cancel_notes() -> None:
            notes_read.style("display:block")
            notes_edit.style("display:none")

        async def _save_notes() -> None:
            next_value = str(notes_input.value or "")
            normalized_value = next_value.strip() or None
            if save_value is None:
                _cancel_notes()
                return
            ok = await save_value(normalized_value)
            if ok:
                state["notes"] = normalized_value
                _render_notes_preview(notes_read, normalized_value)
                if on_saved is not None:
                    on_saved()
            _cancel_notes()

        ui.button(icon="edit", on_click=_start_notes_edit).props(
            'flat dense round size=xs aria-label="Edit Notes"'
        ).style("color:var(--ht-text-secondary);")


def _format_ip_host(ip_value: str) -> str:
    try:
        parsed_ip = ipaddress.ip_address(ip_value)
    except ValueError:
        return ip_value
    if parsed_ip.version == 6:
        return f"[{parsed_ip.compressed}]"
    return parsed_ip.compressed


def build_quick_connect_links(ip_value: str | None) -> dict[str, str]:
    """Return standard quick-connect protocol links for an IP address."""
    candidate = (ip_value or "").strip()
    if candidate == "":
        return {}
    host = _format_ip_host(candidate)
    return {
        "ssh": f"ssh://{host}",
        "http": f"http://{host}",
        "https": f"https://{host}",
    }


def render_ip_quick_links(ip_value: str | None) -> None:
    """Render compact quick-connect icon buttons when a device has an IP."""
    links = build_quick_connect_links(ip_value)
    if not links:
        return

    with ui.row().classes("items-center gap-1 w-full"):
        ui.label("Links:").style(
            "font-size:0.75rem; color:var(--ht-text-secondary); min-width:44px;"
            " flex-shrink:0;"
        )
        ui.button(icon="terminal").props(
            f'flat dense round size=xs title="SSH" href="{links["ssh"]}" '
            'target="_blank" rel="noopener noreferrer"'
        ).style("color:var(--ht-text-secondary);")
        ui.button(icon="public").props(
            f'flat dense round size=xs title="HTTP" href="{links["http"]}" '
            'target="_blank" rel="noopener noreferrer"'
        ).style("color:var(--ht-text-secondary);")
        ui.button(icon="lock").props(
            f'flat dense round size=xs title="HTTPS" href="{links["https"]}" '
            'target="_blank" rel="noopener noreferrer"'
        ).style("color:var(--ht-text-secondary);")
