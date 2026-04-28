from __future__ import annotations

from datetime import datetime, time, timedelta, timezone


def _normalize_weekday(value: str) -> str:
    return value.strip().lower()


def _is_holiday(day: datetime, holiday_dates: set[str]) -> bool:
    return day.date().isoformat() in holiday_dates


def _is_quiet_day(day: datetime, quiet_days: set[str]) -> bool:
    return day.strftime("%A").lower() in quiet_days


def _shift_to_work_slot(
    dt: datetime,
    *,
    quiet_days: set[str],
    holiday_dates: set[str],
    workday_start: time,
) -> datetime:
    current = dt
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    while _is_quiet_day(current, quiet_days) or _is_holiday(current, holiday_dates):
        current = (current + timedelta(days=1)).replace(
            hour=workday_start.hour,
            minute=workday_start.minute,
            second=0,
            microsecond=0,
        )
    if current.time() < workday_start:
        current = current.replace(hour=workday_start.hour, minute=workday_start.minute, second=0, microsecond=0)
    return current


def next_action_for_new_assignment(
    *,
    now: datetime | None = None,
    quiet_days: list[str] | None = None,
    holiday_dates: list[str] | None = None,
    touch_hours: int = 24,
) -> datetime:
    base = (now or datetime.now(tz=timezone.utc)) + timedelta(hours=max(1, touch_hours))
    normalized_quiet = {_normalize_weekday(x) for x in (quiet_days or ["saturday", "sunday"])}
    normalized_holidays = {x.strip() for x in (holiday_dates or []) if x.strip()}
    return _shift_to_work_slot(
        base,
        quiet_days=normalized_quiet,
        holiday_dates=normalized_holidays,
        workday_start=time(hour=10, minute=0),
    )


def next_action_after_touchpoint(
    *,
    now: datetime | None = None,
    cadence_hours: int,
    quiet_days: list[str] | None = None,
    holiday_dates: list[str] | None = None,
) -> datetime:
    base = (now or datetime.now(tz=timezone.utc)) + timedelta(hours=max(1, cadence_hours))
    normalized_quiet = {_normalize_weekday(x) for x in (quiet_days or ["saturday", "sunday"])}
    normalized_holidays = {x.strip() for x in (holiday_dates or []) if x.strip()}
    return _shift_to_work_slot(
        base,
        quiet_days=normalized_quiet,
        holiday_dates=normalized_holidays,
        workday_start=time(hour=10, minute=0),
    )
