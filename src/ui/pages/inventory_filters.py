"""Inventory filter chips — device type and tag chip filters."""
from collections.abc import Callable
import uuid

import httpx
from nicegui import ui
from nicegui.element import Element

from src.models.types import DeviceType
from src.ui.design.primitives import set_filter_chip_state
from src.ui.design.tokens import DEVICE_TYPE_COLORS
from src.utils.logger import logger
from src.utils.settings import settings


def render_type_chips(
    state: dict,
    refs: dict,
    make_chip_toggle: Callable[[DeviceType, str], Callable[[], None]],
    apply_filters: Callable[[], None],
) -> None:
    """Render device-type filter chips into the chips_row element."""
    chips_row = refs["chips_row"]
    chips_row.clear()
    refs["chips"] = []

    present_type_values = {d.type.value for d in state["all"]}
    present_types = [dt for dt in DeviceType if dt.value in present_type_values]
    present_type_set = set(present_types)
    state["types"] = {dt for dt in state["types"] if dt in present_type_set}

    with chips_row:
        if present_types:
            ui.label("Type:").style(
                "font-size:0.875rem; color:var(--ht-text-secondary)"
            )
        for dtype in present_types:
            color = DEVICE_TYPE_COLORS.get(dtype, "var(--ht-accent)")
            is_active = dtype in state["types"]
            chip = ui.chip(dtype.value, on_click=make_chip_toggle(dtype, color)).style(
                "cursor:pointer"
            )
            set_filter_chip_state(chip, color, is_active)
            meta = {
                "chip": chip,
                "dtype": dtype,
                "color": color,
                "active": is_active,
            }
            refs["chips"].append(meta)


def render_tag_chip_filters(
    tag_chip_row: Element,
    all_tags: list[dict[str, object]],
    selected_tag_ids: set[uuid.UUID],
    tag_chip_metas: list[dict[str, object]],
    apply_filters: Callable[[], None],
) -> None:
    """Render tag chips and wire toggle behavior for filtering."""
    tag_chip_metas.clear()
    tag_chip_row.clear()

    with tag_chip_row:
        if all_tags:
            ui.label("Tags:").style("font-size:0.875rem; color:var(--ht-text-secondary)")
        for tdata in all_tags:
            try:
                tid = uuid.UUID(str(tdata.get("id", "")))
            except (TypeError, ValueError, AttributeError):
                continue
            tcolor = str(tdata.get("color", "var(--ht-accent)"))

            def _make_tag_toggle(
                tag_id: uuid.UUID, color: str,
            ) -> Callable[[], None]:
                def _toggle() -> None:
                    meta_match = next(
                        (m for m in tag_chip_metas if m.get("tid") == tag_id), None,
                    )
                    if meta_match is None:
                        return
                    is_active = not bool(meta_match["active"])
                    meta_match["active"] = is_active
                    chip_ref = meta_match["chip"]
                    if is_active:
                        selected_tag_ids.add(tag_id)
                    else:
                        selected_tag_ids.discard(tag_id)
                    set_filter_chip_state(chip_ref, color, is_active)
                    apply_filters()

                return _toggle

            tchip = ui.chip(
                str(tdata.get("name", "")),
                on_click=_make_tag_toggle(tid, tcolor),
            ).style("cursor:pointer")
            set_filter_chip_state(tchip, tcolor, False)
            tmeta: dict[str, object] = {
                "chip": tchip,
                "tid": tid,
                "color": tcolor,
                "active": False,
            }
            tag_chip_metas.append(tmeta)


async def load_tag_chips(
    token: str,
    tag_chip_row: Element,
    selected_tag_ids: set[uuid.UUID],
    tag_chip_metas: list[dict[str, object]],
    apply_filters: Callable[[], None],
) -> list[dict[str, object]]:
    """Fetch tags from API and render chip filters."""
    try:
        async with httpx.AsyncClient() as http:
            tresp = await http.get(
                f"{settings.api_base_url}/api/tags/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
        if tresp.status_code != 200:
            return []
        all_tags = tresp.json()
        render_tag_chip_filters(
            tag_chip_row=tag_chip_row,
            all_tags=all_tags,
            selected_tag_ids=selected_tag_ids,
            tag_chip_metas=tag_chip_metas,
            apply_filters=apply_filters,
        )
        return all_tags
    except Exception as exc:
        logger.error("Tag chips load: {}", str(exc))
    return []
