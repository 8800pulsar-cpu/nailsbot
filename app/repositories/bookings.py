from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Booking, BookingStatus


class BookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _with_relations(self, stmt: Select[tuple[Booking]]) -> Select[tuple[Booking]]:
        return stmt.options(
            selectinload(Booking.user),
            selectinload(Booking.service),
        )

    async def get_by_id(self, booking_id: int) -> Booking | None:
        result = await self.session.execute(
            self._with_relations(select(Booking).where(Booking.id == booking_id))
        )
        return result.scalar_one_or_none()

    async def list_confirmed_for_master_on_date(
        self,
        master_id: int,
        day_start: datetime,
        day_end: datetime,
    ) -> list[Booking]:
        result = await self.session.execute(
            select(Booking).where(
                Booking.master_id == master_id,
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.start_time < day_end,
                Booking.end_time > day_start,
            )
        )
        return list(result.scalars().all())

    async def list_user_confirmed(self, user_id: int, master_id: int) -> list[Booking]:
        result = await self.session.execute(
            self._with_relations(
                select(Booking)
                .where(
                    Booking.user_id == user_id,
                    Booking.master_id == master_id,
                    Booking.status == BookingStatus.CONFIRMED.value,
                    Booking.end_time > datetime.now(tz=datetime.now().astimezone().tzinfo),
                )
                .order_by(Booking.start_time)
            )
        )
        return list(result.scalars().all())

    async def list_user_upcoming(self, user_id: int, master_id: int, now: datetime) -> list[Booking]:
        result = await self.session.execute(
            self._with_relations(
                select(Booking)
                .where(
                    Booking.user_id == user_id,
                    Booking.master_id == master_id,
                    Booking.status == BookingStatus.CONFIRMED.value,
                    Booking.end_time > now,
                )
                .order_by(Booking.start_time)
            )
        )
        return list(result.scalars().all())

    async def list_user_history(self, user_id: int, master_id: int) -> list[Booking]:
        result = await self.session.execute(
            self._with_relations(
                select(Booking)
                .where(
                    Booking.user_id == user_id,
                    Booking.master_id == master_id,
                )
                .order_by(Booking.start_time.desc())
            )
        )
        return list(result.scalars().all())

    async def list_for_day(
        self,
        master_id: int,
        day_start: datetime,
        day_end: datetime,
    ) -> list[Booking]:
        result = await self.session.execute(
            self._with_relations(
                select(Booking)
                .where(
                    Booking.master_id == master_id,
                    Booking.status == BookingStatus.CONFIRMED.value,
                    Booking.start_time >= day_start,
                    Booking.start_time < day_end,
                )
                .order_by(Booking.start_time)
            )
        )
        return list(result.scalars().all())

    async def list_upcoming(self, master_id: int, now: datetime, limit: int = 20) -> list[Booking]:
        result = await self.session.execute(
            self._with_relations(
                select(Booking)
                .where(
                    Booking.master_id == master_id,
                    Booking.status == BookingStatus.CONFIRMED.value,
                    Booking.start_time >= now,
                )
                .order_by(Booking.start_time)
                .limit(limit)
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        master_id: int,
        user_id: int,
        service_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Booking:
        booking = Booking(
            master_id=master_id,
            user_id=user_id,
            service_id=service_id,
            start_time=start_time,
            end_time=end_time,
            status=BookingStatus.CONFIRMED.value,
        )
        self.session.add(booking)
        await self.session.flush()
        return booking
