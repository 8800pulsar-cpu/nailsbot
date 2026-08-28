from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.schedule_service import BusyInterval, DaySchedule, generate_slots

TZ = ZoneInfo("Europe/Moscow")
DAY = date(2026, 8, 24)


@dataclass
class FakeService:
    master_id: int
    is_active: bool
    name: str = "Маникюр"


def visible_client_services(services: list[FakeService], master_id: int) -> list[FakeService]:
    return [item for item in services if item.master_id == master_id and item.is_active]


def bookings_for_master(bookings: list[BusyInterval], master_id: int, owner_ids: list[int]) -> list[BusyInterval]:
    return [item for item, owner in zip(bookings, owner_ids, strict=True) if owner == master_id]


def test_inactive_service_is_hidden_from_client():
    services = [
        FakeService(master_id=1, is_active=True, name="Активная"),
        FakeService(master_id=1, is_active=False, name="Старая"),
    ]
    visible = visible_client_services(services, master_id=1)
    assert [item.name for item in visible] == ["Активная"]


def test_other_master_services_are_not_shown():
    services = [
        FakeService(master_id=1, is_active=True, name="Мастер 1"),
        FakeService(master_id=2, is_active=True, name="Мастер 2"),
    ]
    visible = visible_client_services(services, master_id=1)
    assert [item.name for item in visible] == ["Мастер 1"]


def test_other_master_bookings_do_not_block_slots():
    schedule = DaySchedule(weekday=0, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
    start = datetime(2026, 8, 24, 12, 0, tzinfo=TZ)
    end = datetime(2026, 8, 24, 14, 0, tzinfo=TZ)
    all_busy = [BusyInterval(start=start, end=end)]
    owner_ids = [2]
    master_1_busy = bookings_for_master(all_busy, master_id=1, owner_ids=owner_ids)
    slots = generate_slots(
        target_date=DAY,
        now=datetime(2026, 8, 24, 9, 0, tzinfo=TZ),
        schedule=schedule,
        duration=timedelta(minutes=120),
        busy=master_1_busy,
        is_closed=False,
        tz=TZ,
    )
    assert start in slots

    master_2_busy = bookings_for_master(all_busy, master_id=2, owner_ids=owner_ids)
    slots_m2 = generate_slots(
        target_date=DAY,
        now=datetime(2026, 8, 24, 9, 0, tzinfo=TZ),
        schedule=schedule,
        duration=timedelta(minutes=120),
        busy=master_2_busy,
        is_closed=False,
        tz=TZ,
    )
    assert start not in slots_m2


def test_other_master_closed_date_does_not_close_this_master():
    schedule = DaySchedule(weekday=0, start_time=time(10, 0), end_time=time(20, 0), is_working=True)
    closed_by_master = {1: set(), 2: {DAY}}
    slots = generate_slots(
        target_date=DAY,
        now=datetime(2026, 8, 24, 9, 0, tzinfo=TZ),
        schedule=schedule,
        duration=timedelta(minutes=60),
        busy=[],
        is_closed=DAY in closed_by_master[1],
        tz=TZ,
    )
    assert slots
    slots_m2 = generate_slots(
        target_date=DAY,
        now=datetime(2026, 8, 24, 9, 0, tzinfo=TZ),
        schedule=schedule,
        duration=timedelta(minutes=60),
        busy=[],
        is_closed=DAY in closed_by_master[2],
        tz=TZ,
    )
    assert slots_m2 == []
