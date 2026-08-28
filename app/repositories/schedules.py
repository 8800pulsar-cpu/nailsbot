from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ClosedDate, WorkingSchedule


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_master(self, master_id: int) -> list[WorkingSchedule]:
        result = await self.session.execute(
            select(WorkingSchedule)
            .where(WorkingSchedule.master_id == master_id)
            .order_by(WorkingSchedule.weekday)
        )
        return list(result.scalars().all())

    async def get_weekday(self, master_id: int, weekday: int) -> WorkingSchedule | None:
        result = await self.session.execute(
            select(WorkingSchedule).where(
                WorkingSchedule.master_id == master_id,
                WorkingSchedule.weekday == weekday,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_weekday(
        self,
        *,
        master_id: int,
        weekday: int,
        start_time: time,
        end_time: time,
        is_working: bool,
    ) -> WorkingSchedule:
        row = await self.get_weekday(master_id, weekday)
        if row is None:
            row = WorkingSchedule(
                master_id=master_id,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                is_working=is_working,
            )
            self.session.add(row)
        else:
            row.start_time = start_time
            row.end_time = end_time
            row.is_working = is_working
        await self.session.flush()
        return row

    async def ensure_week(self, master_id: int) -> list[WorkingSchedule]:
        existing = {row.weekday: row for row in await self.list_for_master(master_id)}
        for weekday in range(7):
            if weekday not in existing:
                is_working = weekday < 6
                self.session.add(
                    WorkingSchedule(
                        master_id=master_id,
                        weekday=weekday,
                        start_time=time(10, 0),
                        end_time=time(20, 0),
                        is_working=is_working,
                    )
                )
        await self.session.flush()
        return await self.list_for_master(master_id)


class ClosedDateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_master(self, master_id: int, from_date: date | None = None) -> list[ClosedDate]:
        stmt = select(ClosedDate).where(ClosedDate.master_id == master_id)
        if from_date is not None:
            stmt = stmt.where(ClosedDate.date >= from_date)
        stmt = stmt.order_by(ClosedDate.date)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_on_date(self, master_id: int, day: date) -> ClosedDate | None:
        result = await self.session.execute(
            select(ClosedDate).where(
                ClosedDate.master_id == master_id,
                ClosedDate.date == day,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, *, master_id: int, day: date, reason: str | None) -> ClosedDate:
        row = ClosedDate(master_id=master_id, date=day, reason=reason)
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete(self, closed: ClosedDate) -> None:
        await self.session.delete(closed)
        await self.session.flush()
