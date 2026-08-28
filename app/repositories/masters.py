from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Master


class MasterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, master_id: int) -> Master | None:
        return await self.session.get(Master, master_id)

    async def list_active(self) -> list[Master]:
        result = await self.session.execute(
            select(Master).where(Master.is_active.is_(True)).order_by(Master.id)
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        name: str,
        description: str,
        contact: str,
        address: str,
        timezone: str,
    ) -> Master:
        ZoneInfo(timezone)
        master = Master(
            name=name,
            description=description,
            contact=contact,
            address=address,
            timezone=timezone,
            is_active=True,
        )
        self.session.add(master)
        await self.session.flush()
        return master

    async def update_fields(self, master: Master, **fields: str) -> Master:
        for key, value in fields.items():
            setattr(master, key, value)
        await self.session.flush()
        return master
