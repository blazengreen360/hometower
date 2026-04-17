"""Friendly validation feedback helpers for UI forms and dialogs."""
from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
import html
import json

import httpx

_LOCATION_SEGMENTS: set[str] = {"body", "query", "path", "response"}


def _clean_text(value: str) -> str:
    return html.unescape(value).strip()


def _looks_like_json(value: str) -> bool:
    text = value.lstrip()
    return text.startswith("[") or text.startswith("{")


def _strip_outer_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _extract_field_name(loc: object) -> str | None:
    if not isinstance(loc, Sequence) or isinstance(loc, (str, bytes)):
        return None

    for part in reversed(loc):
        if not isinstance(part, str):
            continue
        candidate = part.strip()
        if candidate and candidate not in _LOCATION_SEGMENTS:
            return candidate
    return None


def _normalize_detail(detail: object) -> object:
    if not isinstance(detail, str):
        return detail

    cleaned = _clean_text(detail)
    for _ in range(3):
        if not cleaned:
            return cleaned

        unquoted = _clean_text(_strip_outer_quotes(cleaned))
        if unquoted != cleaned:
            cleaned = unquoted
            continue

        if not _looks_like_json(cleaned):
            return cleaned

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(cleaned)
            except (SyntaxError, ValueError):
                return cleaned

        if isinstance(parsed, str):
            cleaned = _clean_text(parsed)
            continue
        return parsed

    return cleaned


def _extract_first_message(detail: object) -> tuple[str | None, str | None]:
    normalized = _normalize_detail(detail)
    if isinstance(normalized, str):
        return None, normalized or None

    if isinstance(normalized, dict):
        loc = _extract_field_name(normalized.get("loc"))
        msg = normalized.get("msg")
        if isinstance(msg, str):
            return loc, _clean_text(msg)
        nested = normalized.get("detail")
        if nested is not None:
            return _extract_first_message(nested)
        return None, None

    if isinstance(normalized, Sequence) and not isinstance(
        normalized,
        (str, bytes, bytearray),
    ):
        for item in normalized:
            field_name, message = _extract_first_message(item)
            if message:
                return field_name, message
    return None, None


def _is_required_message(message_lower: str) -> bool:
    return (
        "field required" in message_lower
        or "empty or whitespace-only" in message_lower
        or "must not be blank" in message_lower
        or "string should have at least 1 character" in message_lower
    )


def _humanize_message(message: str) -> str:
    cleaned = _clean_text(message)
    if not cleaned:
        return ""
    if cleaned.lower().startswith("value error, "):
        cleaned = cleaned[len("value error, ") :]
    if cleaned and cleaned[0].islower():
        return cleaned[0].upper() + cleaned[1:]
    return cleaned


def _looks_like_payload_blob(message: str) -> bool:
    lowered = message.lower()
    return (
        ("loc" in lowered and "msg" in lowered and ("{" in message or "[" in message))
        or "&quot;" in lowered
        or '\\"' in message
    )


def _response_detail(response: httpx.Response) -> object:
    try:
        payload = response.json()
    except Exception:
        return None

    if isinstance(payload, dict):
        if "detail" in payload:
            return payload.get("detail")
        if "message" in payload:
            return payload.get("message")
        if "error" in payload:
            return payload.get("error")
    return payload


def friendly_error_message(
    response: httpx.Response,
    *,
    fallback: str,
    field_labels: Mapping[str, str] | None = None,
    status_overrides: Mapping[int, str] | None = None,
    message_overrides: Mapping[str, str] | None = None,
) -> str:
    """Return concise, user-facing text from an HTTP error response."""
    if status_overrides and response.status_code in status_overrides:
        return status_overrides[response.status_code]

    if response.status_code >= 500:
        return fallback

    field_name, detail_message = _extract_first_message(_response_detail(response))
    if not detail_message:
        return fallback

    lowered = detail_message.lower()
    if message_overrides:
        for needle, replacement in message_overrides.items():
            if needle in lowered:
                return replacement

    if field_name and field_labels and _is_required_message(lowered):
        label = field_labels.get(field_name, field_name.replace("_", " ").capitalize())
        return f"{label} is required."

    message = _humanize_message(detail_message)
    if not message or _looks_like_payload_blob(message):
        return fallback

    return message