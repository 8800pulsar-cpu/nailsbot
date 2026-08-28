from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Booking, BookingStatus, Master, Service
from app.repositories.bookings import BookingRepository
from app.repositories.schedules import ClosedDateRepository, ScheduleRepository
from app.repositories.services import ServiceRepository
from app.services.schedule_service import (
    BusyInterval,
    DaySchedule,
    available_dates,
    generate_slots,
)
from app.utils.format import master_tz, now_in_tz


class SlotUnavailableError(Exception):
    pass


class InactiveServiceError(Exception):
    pass


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bookings = BookingRepository(session)
        self.services = ServiceRepository(session)
        self.schedules = ScheduleRepository(session)
        self.closed_dates = ClosedDateRepository(session)

    async def list_client_services(self, master_id: int) -> list[Service]:
        return await self.services.list_by_master(master_id, active_only=True)

    async def get_bookable_service(self, service_id: int, master_id: int) -> Service:
        service = await self.services.get_for_master(service_id, master_id)
        if service is None or not service.is_active:
            raise InactiveServiceError
        return service

    async def list_available_dates(self, master: Master, service: Service) -> list[date]:
        tz = master_tz(master)
        now = now_in_tz(tz)
        schedules = await self._schedules_map(master.id)
        closed = {row.date for row in await self.closed_dates.list_for_master(master.id, now.date())}
        busy_by_date = await self._busy_map(
            master.id,
            now.date(),
            now.date() + timedelta(days=14),
            tz,
        )
        return available_dates(
            today=now.date(),
            now=now,
            schedules_by_weekday=schedules,
            closed_dates=closed,
            duration=timedelta(minutes=service.duration_minutes),
            busy_by_date=busy_by_date,
            tz=tz,
        )

    async def list_available_slots(
        self,
        master: Master,
        service: Service,
        day: date,
    ) -> list[datetime]:
        tz = master_tz(master)
        now = now_in_tz(tz)
        if day < now.date():
            return []
        closed = await self.closed_dates.get_on_date(master.id, day)
        schedule_row = await self.schedules.get_weekday(master.id, day.weekday())
        schedule = _to_day_schedule(schedule_row)
        day_start = datetime.combine(day, time.min, tzinfo=tz)
        day_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
        bookings = await self.bookings.list_confirmed_for_master_on_date(
            master.id, day_start, day_end
        )
        busy = [
            BusyInterval(start=item.start_time, end=item.end_time, status=item.status)
            for item in bookings
        ]
        return generate_slots(
            target_date=day,
            now=now,
            schedule=schedule,
            duration=timedelta(minutes=service.duration_minutes),
            busy=busy,
            is_closed=closed is not None,
            tz=tz,
        )

    async def create_booking(
        self,
        *,
        master: Master,
        user_id: int,
        service_id: int,
        start_local: datetime,
    ) -> Booking:
        service = await self.get_bookable_service(service_id, master.id)
        tz = master_tz(master)
        start = start_local.astimezone(tz)
        end = start + timedelta(minutes=service.duration_minutes)

        await self.session.execute(
            select(Master).where(Master.id == master.id).with_for_update()
        )

        if not await self._is_slot_free(master, service, start, tz):
            raise SlotUnavailableError

        try:
            async with self.session.begin_nested():
                booking = await self.bookings.create(
                    master_id=master.id,
                    user_id=user_id,
                    service_id=service.id,
                    start_time=start,
                    end_time=end,
                )
                await self.session.flush()
        except IntegrityError as exc:
            raise SlotUnavailableError from exc
        loaded = await self.bookings.get_by_id(booking.id)
        return loaded or booking

    async def cancel_booking(self, booking: Booking, master_id: int, user_id: int | None) -> Booking:
        if booking.master_id != master_id:
            raise SlotUnavailableError
        if user_id is not None and booking.user_id != user_id:
            raise SlotUnavailableError
        booking.status = BookingStatus.CANCELLED.value
        await self.session.flush()
        return booking

    async def _is_slot_free(
        self,
        master: Master,
        service: Service,
        start: datetime,
        tz: ZoneInfo,
    ) -> bool:
        day = start.astimezone(tz).date()
        slots = await self.list_available_slots(master, service, day)
        return any(abs((slot - start).total_seconds()) < 1 for slot in slots)

    async def _schedules_map(self, master_id: int) -> dict[int, DaySchedule]:
        rows = await self.schedules.list_for_master(master_id)
        return {row.weekday: _to_day_schedule(row) for row in rows if _to_day_schedule(row)}

    async def _busy_map(
        self,
        master_id: int,
        start_day: date,
        end_day: date,
        tz: ZoneInfo,
    ) -> dict[date, list[BusyInterval]]:
        day_start = datetime.combine(start_day, time.min, tzinfo=tz)
        day_end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)
        bookings = await self.bookings.list_confirmed_for_master_on_date(
            master_id, day_start, day_end
        )
        result: dict[date, list[BusyInterval]] = {}
        for item in bookings:
            local_start = item.start_time.astimezone(tz)
            result.setdefault(local_start.date(), []).append(
                BusyInterval(start=item.start_time, end=item.end_time, status=item.status)
            )
        return result


def _to_day_schedule(row) -> DaySchedule | None:
    if row is None:
        return None
    return DaySchedule(
        weekday=row.weekday,
        start_time=row.start_time,
        end_time=row.end_time,
        is_working=row.is_working,
    )


def format_booking_card(booking: Booking, tz: ZoneInfo) -> str:
    from app.utils.format import format_price

    local_start = booking.start_time.astimezone(tz)
    service_name = booking.service.name if booking.service else "Услуга"
    price = booking.service.price if booking.service else Decimal("0")
    return (
        f"💅 {service_name}\n"
        f"📅 {local_start.strftime('%d.%m.%Y')}\n"
        f"🕒 {local_start.strftime('%H:%M')}\n"
        f"💰 {format_price(price)}"
    )
