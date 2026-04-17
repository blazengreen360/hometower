"""Power service — summary and global settings orchestration (HT-044)."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from src.domain import power as power_domain
from src.models.power_settings import (
    PowerSettings,
    PowerSettingsResponse,
    PowerSettingsUpdate,
)
from src.models.power_summary import PowerLocationSummary, PowerSummaryResponse
from src.repositories import power_repository
from src.utils.logger import logger


def get_settings(session: Session) -> PowerSettingsResponse:
    """Return global settings, or null defaults when not configured yet."""
    settings_row = power_repository.get_settings(session)
    if settings_row is None:
        return PowerSettingsResponse(cost_per_kwh=None, currency=None, updated_at=None)

    cost_per_kwh, currency = power_domain.validate_cost_settings(
        settings_row.cost_per_kwh,
        settings_row.currency,
    )
    return PowerSettingsResponse(
        cost_per_kwh=cost_per_kwh,
        currency=currency,
        updated_at=settings_row.updated_at,
    )


def upsert_settings(
    data: PowerSettingsUpdate,
    session: Session,
) -> PowerSettingsResponse:
    """Create or update singleton global power settings."""
    cost_per_kwh, currency = power_domain.validate_cost_settings(
        data.cost_per_kwh,
        data.currency,
    )

    now = datetime.now(timezone.utc)
    settings_row = power_repository.get_settings(session)

    try:
        if settings_row is None:
            settings_row = power_repository.create_settings(
                session,
                PowerSettings(
                    scope="global",
                    cost_per_kwh=cost_per_kwh,
                    currency=currency,
                    updated_at=now,
                ),
            )
        else:
            settings_row.cost_per_kwh = cost_per_kwh
            settings_row.currency = currency
            settings_row.updated_at = now
            settings_row = power_repository.update_settings(session, settings_row)

        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Power settings conflict") from exc

    logger.info("Power settings upserted: scope={}", settings_row.scope)
    return PowerSettingsResponse(
        cost_per_kwh=settings_row.cost_per_kwh,
        currency=settings_row.currency,
        updated_at=settings_row.updated_at,
    )


def get_summary(session: Session) -> PowerSummaryResponse:
    """Return global and per-location power summary for Reader+ consumers."""
    device_rows = power_repository.list_device_rows(session)
    location_rows = power_repository.list_location_rows(session)
    settings_row = power_repository.get_settings(session)

    if settings_row is None:
        cost_per_kwh, currency = None, None
    else:
        cost_per_kwh, currency = power_domain.validate_cost_settings(
            settings_row.cost_per_kwh,
            settings_row.currency,
        )

    total_devices = len(device_rows)
    devices_with_power = sum(
        1 for row in device_rows if row["power_watts"] is not None
    )
    devices_without_power = total_devices - devices_with_power
    total_watts = sum(
        row["power_watts"]
        for row in device_rows
        if row["power_watts"] is not None
    )

    location_rollups = power_domain.build_recursive_location_rollups(
        device_rows,
        location_rows,
        cost_per_kwh,
    )

    return PowerSummaryResponse(
        total_watts=total_watts,
        total_devices=total_devices,
        devices_with_power=devices_with_power,
        devices_without_power=devices_without_power,
        estimated_monthly_kwh=power_domain.estimate_monthly_kwh(total_watts),
        estimated_monthly_cost=power_domain.estimate_monthly_cost(
            total_watts,
            cost_per_kwh,
        ),
        currency=currency,
        cost_per_kwh=cost_per_kwh,
        by_location=[
            PowerLocationSummary.model_validate(row) for row in location_rollups
        ],
    )
