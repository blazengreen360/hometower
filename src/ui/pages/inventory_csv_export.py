"""Inventory CSV export helpers for HT-087."""

from __future__ import annotations

import csv
import io
import json

from src.models.device import DeviceResponseEnriched

CSV_FILENAME = "hometower_inventory_export.csv"
CSV_COLUMNS = ["Name", "Status", "Type", "IP", "MAC", "Location", "Notes"]

_DANGEROUS_CSV_PREFIXES = ("=", "+", "-", "@", "\t")


def _csv_cell(value: object) -> str:
    raw = "" if value is None else str(value)
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.startswith(_DANGEROUS_CSV_PREFIXES):
        return f"'{normalized}"
    return normalized


def build_inventory_csv(devices: list[DeviceResponseEnriched]) -> str:
    """Build UTF-8 CSV payload for inventory rows using primary story columns."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for device in devices:
        writer.writerow(
            [
                _csv_cell(device.name),
                _csv_cell(device.status.value if device.status else "Active"),
                _csv_cell(device.type.value),
                _csv_cell(device.ip),
                _csv_cell(device.mac),
                _csv_cell(device.location_name),
                _csv_cell(device.notes),
            ]
        )
    return buffer.getvalue()


def build_inventory_csv_download_js(csv_payload: str, filename: str = CSV_FILENAME) -> str:
    """Build browser JS that downloads a CSV blob with the given filename."""
    return (
        "(function(){"
        f"const csvText='\\ufeff'+{json.dumps(csv_payload)};"
        f"const fileName={json.dumps(filename)};"
        "const blob=new Blob([csvText],{type:'text/csv;charset=utf-8;'});"
        "const objectUrl=URL.createObjectURL(blob);"
        "const anchor=document.createElement('a');"
        "anchor.href=objectUrl;"
        "anchor.download=fileName;"
        "anchor.style.display='none';"
        "document.body.appendChild(anchor);"
        "anchor.click();"
        "window.setTimeout(function(){URL.revokeObjectURL(objectUrl);anchor.remove();},0);"
        "})();"
    )
