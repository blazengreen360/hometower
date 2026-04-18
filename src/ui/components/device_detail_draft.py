"""Draft device detail panel — editable fields + Publish button (HT-051).

Extracted from device_detail_panel.py to keep file sizes under 250 lines.
"""
import html
import json

from nicegui import ui

from src.ui.design.primitives import primary_button
from src.utils.logger import logger


async def show_draft_panel(
    draft_id: str,
    content: ui.column,
) -> None:
    """Show panel for a draft device with editable fields and Publish button."""
    js_draft_id = json.dumps(draft_id)
    data = await ui.run_javascript(
        f"(function(){{ var n = window._cy.getElementById({js_draft_id});"
        f" return n.length ? n.data() : null; }})()"
    )
    if not data or not isinstance(data, dict):
        logger.debug("Draft panel: no data for {}", draft_id)
        return

    content.clear()
    with content:
        ui.label("\u26a0 Draft Device").style(
            "color:var(--ht-warning); font-weight:600; font-size:0.875rem;"
        )

        async def _on_publish() -> None:
            result = await ui.run_javascript(
                f"window._htPublishDraft({js_draft_id})"
            )
            if result:
                await ui.run_javascript(
                    "document.getElementById('device-detail-panel')"
                    ".style.display='none'"
                )

        primary_button(ui.button(
            "Publish to Inventory",
            icon="publish",
            on_click=_on_publish,
        )).classes("w-full")
        for field_key, label_text in [
            ("draft_name", "Name"),
            ("draft_type", "Type"),
            ("draft_ip", "IP"),
            ("draft_mac", "MAC"),
            ("draft_os", "OS"),
            ("draft_notes", "Notes"),
        ]:
            value = data.get(field_key, "")
            inp = ui.input(
                label=label_text, value=str(value) if value else ""
            ).classes("w-full")

            async def _on_field_change(
                e: object,
                _fk: str = field_key,
                _did: str = draft_id,
            ) -> None:
                val = getattr(e, "value", "")
                js_key = _fk.replace("draft_", "")
                safe_val = json.dumps(str(val))
                js_id = json.dumps(_did)
                shape_js = ""
                if _fk == "draft_type":
                    shape_js = (
                        f"var _sh=(window._htDeviceShapes||{{}})["
                        f"{safe_val}]||'rectangle';"
                        f"window._cy.getElementById({js_id})"
                        f".data('shape',_sh);"
                    )
                await ui.run_javascript(
                    f"window._htUpdateDraftData("
                    f"window._cy.getElementById({js_id}),"
                    f"{{ {js_key}: {safe_val} }});"
                    f"{shape_js}"
                    f"if(window.scheduleAutosave) window.scheduleAutosave(800);"
                )

            inp.on_value_change(_on_field_change)

    await ui.run_javascript(
        "document.getElementById('device-detail-panel').style.display='flex'"
    )
