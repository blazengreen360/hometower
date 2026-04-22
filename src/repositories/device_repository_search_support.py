"""Search query helpers for device repository filters."""

from sqlalchemy import func, or_
from sqlalchemy import select as sa_select
from sqlmodel import col

from src.domain.search import ParsedQuery, to_sql_like
from src.models.device import Device
from src.models.location import Location
from src.models.service import Service
from src.models.tag import DeviceTag, Tag


def build_search_statement():
    return (
        sa_select(Device, Location.name)  # type: ignore[call-overload]
        .outerjoin(Location, Device.location_id == Location.id)
    )


def apply_search_filters(statement, parsed: ParsedQuery):
    for apply_filter in (
        _apply_type_filter,
        _apply_ip_filter,
        _apply_os_filter,
        _apply_tag_filter,
        _apply_location_filter,
        _apply_service_filter,
        _apply_free_text_filter,
    ):
        statement = apply_filter(statement, parsed)
    return statement


def _apply_type_filter(statement, parsed: ParsedQuery):
    if parsed.types:
        return statement.where(
            or_(*[func.lower(col(Device.type)).ilike(value.lower()) for value in parsed.types])
        )
    return statement


def _apply_ip_filter(statement, parsed: ParsedQuery):
    if parsed.ip_patterns:
        return statement.where(
            or_(
                *[
                    col(Device.ip).ilike(to_sql_like(value), escape="\\")
                    for value in parsed.ip_patterns
                ]
            )
        )
    return statement


def _apply_os_filter(statement, parsed: ParsedQuery):
    if parsed.os_patterns:
        return statement.where(
            or_(
                *[
                    col(Device.os).ilike(f"%{to_sql_like(value)}%", escape="\\")
                    for value in parsed.os_patterns
                ]
            )
        )
    return statement


def _apply_tag_filter(statement, parsed: ParsedQuery):
    if parsed.tags:
        return statement.where(col(Device.id).in_(_tag_device_ids(parsed.tags)))
    return statement


def _apply_location_filter(statement, parsed: ParsedQuery):
    if parsed.location_patterns:
        return statement.where(
            or_(
                *[
                    col(Location.name).ilike(
                        f"%{to_sql_like(value)}%",
                        escape="\\",
                    )
                    for value in parsed.location_patterns
                ]
            )
        )
    return statement


def _apply_service_filter(statement, parsed: ParsedQuery):
    if parsed.service_patterns:
        return statement.where(
            col(Device.id).in_(_service_device_ids(parsed.service_patterns))
        )
    return statement


def _apply_free_text_filter(statement, parsed: ParsedQuery):
    if parsed.free_text:
        return statement.where(_free_text_clause(parsed.free_text))
    return statement


def _tag_device_ids(tags: list[str]):
    return (
        sa_select(DeviceTag.device_id)  # type: ignore[call-overload]
        .join(Tag, DeviceTag.tag_id == Tag.id)
        .where(or_(*[col(Tag.name).ilike(f"%{value}%") for value in tags]))
        .scalar_subquery()
    )


def _service_device_ids(service_patterns: list[str]):
    return (
        sa_select(Service.device_id)  # type: ignore[call-overload]
        .where(
            or_(
                *[
                    col(Service.name).ilike(
                        f"%{to_sql_like(value)}%",
                        escape="\\",
                    )
                    for value in service_patterns
                ]
            )
        )
        .scalar_subquery()
    )


def _free_text_clause(free_text: str):
    value = f"%{free_text}%"
    return or_(
        col(Device.name).ilike(value),
        col(Device.ip).ilike(value),
        col(Device.os).ilike(value),
        col(Device.notes).ilike(value),
        col(Location.name).ilike(value),
    )