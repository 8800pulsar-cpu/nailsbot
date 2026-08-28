from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.overlap import slot_fits_workday
from app.services.schedule_service import (
    BusyInterval,
    DaySchedule,
    available_dates,
    generate_slots,
)

TZ = ZoneInfo("Europe/Moscow")
MONDAY = date(2026, 8, 24)  # Monday


def _workday() -> DaySchedule:
    return DaySchedule(weekday=0, start_time=time(10, 0), end_time=time(20, 0), is_working=True)


def _dt(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


def test_generate_slots_30_min_step_and_duration():
    now = _dt(MONDAY, 9, 0)
    slots = generate_slots(
        target_date=MONDAY,
        now=now,
        schedule=_workday(),
        duration=timedelta(minutes=120),
        busy=[],
        is_closed=False,
        tz=TZ,
    )
    assert slots[0] == _dt(MONDAY, 10, 0)
    assert slots[1] == _dt(MONDAY, 10, 30)
    assert slots[-1] == _dt(MONDAY, 18, 0)
    assert _dt(MONDAY, 18, 30) not in slots


def test_busy_interval_blocks_overlapping_slots():
    now = _dt(MONDAY, 9, 0)
    busy = [BusyInterval(start=_dt(MONDAY, 12, 0), end=_dt(MONDAY, 14, 0))]
    slots = generate_slots(
        target_date=MONDAY,
        now=now,
        schedule=_workday(),
        duration=timedelta(minutes=120),
        busy=busy,
        is_closed=False,
        tz=TZ,
    )
    assert _dt(MONDAY, 11, 0) not in slots
    assert _dt(MONDAY, 12, 0) not in slots
    assert _dt(MONDAY, 13, 30) not in slots
    assert _dt(MONDAY, 10, 0) in slots
    assert _dt(MONDAY, 14, 0) in slots


def test_cancelled_booking_does_not_block_slot():
    now = _dt(MONDAY, 9, 0)
    busy = [
        BusyInterval(
            start=_dt(MONDAY, 12, 0),
            end=_dt(MONDAY, 14, 0),
            status="cancelled",
        )
    ]
    slots = generate_slots(
        target_date=MONDAY,
        now=now,
        schedule=_workday(),
        duration=timedelta(minutes=120),
        busy=busy,
        is_closed=False,
        tz=TZ,
    )
    assert _dt(MONDAY, 12, 0) in slots


def test_service_must_fit_working_hours():
    work_start = _dt(MONDAY, 10, 0)
    work_end = _dt(MONDAY, 20, 0)
    duration = timedelta(minutes=120)
    assert slot_fits_workday(_dt(MONDAY, 18, 0), duration, work_start, work_end)
    assert not slot_fits_workday(_dt(MONDAY, 18, 30), duration, work_start, work_end)

    now = _dt(MONDAY, 9, 0)
    slots = generate_slots(
        target_date=MONDAY,
        now=now,
        schedule=_workday(),
        duration=duration,
        busy=[],
        is_closed=False,
        tz=TZ,
    )
    assert all(slot + duration <= work_end for slot in slots)


def test_closed_date_has_no_slots():
    now = _dt(MONDAY, 9, 0)
    slots = generate_slots(
        target_date=MONDAY,
        now=now,
        schedule=_workday(),
        duration=timedelta(minutes=60),
        busy=[],
        is_closed=True,
        tz=TZ,
    )
    assert slots == []

    dates = available_dates(
        today=MONDAY,
        now=now,
        schedules_by_weekday={0: _workday()},
        closed_dates={MONDAY},
        duration=timedelta(minutes=60),
        busy_by_date={},
        tz=TZ,
        days=1,
    )
    assert dates == []


def test_day_off_has_no_slots():
    off = DaySchedule(weekday=0, start_time=time(10, 0), end_time=time(20, 0), is_working=False)
    slots = generate_slots(
        target_date=MONDAY,
        now=_dt(MONDAY, 9, 0),
        schedule=off,
        duration=timedelta(minutes=60),
        busy=[],
        is_closed=False,
        tz=TZ,
    )
    assert slots == []


def test_past_slots_are_hidden():
    now = _dt(MONDAY, 12, 10)
    slots = generate_slots(
        target_date=MONDAY,
        now=now,
        schedule=_workday(),
        duration=timedelta(minutes=60),
        busy=[],
        is_closed=False,
        tz=TZ,
    )
    assert all(slot >= now for slot in slots)
    assert _dt(MONDAY, 12, 0) not in slots
    assert _dt(MONDAY, 12, 30) in slots
