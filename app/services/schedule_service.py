from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.overlap import ranges_overlap, slot_fits_workday

SLOT_STEP = timedelta(minutes=30)
LOOKAHEAD_DAYS = 14


@dataclass(frozen=True, slots=True)
class DaySchedule:
    weekday: int
    start_time: time
    end_time: time
    is_working: bool


@dataclass(frozen=True, slots=True)
class BusyInterval:
    start: datetime
    end: datetime
    status: str = "confirmed"


def is_active_booking(status: str) -> bool:
    return status == "confirmed"


def generate_slots(
    *,
    target_date: date,
    now: datetime,
    schedule: DaySchedule | None,
    duration: timedelta,
    busy: list[BusyInterval],
    is_closed: bool,
    tz: ZoneInfo,
) -> list[datetime]:
    if schedule is None or not schedule.is_working or is_closed:
        return []
    if duration <= timedelta(0):
        return []

    work_start = datetime.combine(target_date, schedule.start_time, tzinfo=tz)
    work_end = datetime.combine(target_date, schedule.end_time, tzinfo=tz)
    active_busy = [item for item in busy if is_active_booking(item.status)]

    slots: list[datetime] = []
    cursor = work_start
    while slot_fits_workday(cursor, duration, work_start, work_end):
        slot_end = cursor + duration
        if cursor >= now and not _conflicts(cursor, slot_end, active_busy):
            slots.append(cursor)
        cursor += SLOT_STEP
    return slots


def _conflicts(start: datetime, end: datetime, busy: list[BusyInterval]) -> bool:
    return any(ranges_overlap(start, end, item.start, item.end) for item in busy)


def available_dates(
    *,
    today: date,
    now: datetime,
    schedules_by_weekday: dict[int, DaySchedule],
    closed_dates: set[date],
    duration: timedelta,
    busy_by_date: dict[date, list[BusyInterval]],
    tz: ZoneInfo,
    days: int = LOOKAHEAD_DAYS,
) -> list[date]:
    result: list[date] = []
    for offset in range(days):
        day = today + timedelta(days=offset)
        if day in closed_dates:
            continue
        schedule = schedules_by_weekday.get(day.weekday())
        slots = generate_slots(
            target_date=day,
            now=now,
            schedule=schedule,
            duration=duration,
            busy=busy_by_date.get(day, []),
            is_closed=False,
            tz=tz,
        )
        if slots:
            result.append(day)
    return result
