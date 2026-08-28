from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Service


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, service_id: int) -> Service | None:
        return await self.session.get(Service, service_id)

    async def get_for_master(self, service_id: int, master_id: int) -> Service | None:
        result = await self.session.execute(
            select(Service).where(
                Service.id == service_id,
                Service.master_id == master_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_master(self, master_id: int, *, active_only: bool = False) -> list[Service]:
        stmt = select(Service).where(Service.master_id == master_id)
        if active_only:
            stmt = stmt.where(Service.is_active.is_(True))
        stmt = stmt.order_by(Service.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        master_id: int,
        name: str,
        duration_minutes: int,
        price: Decimal,
    ) -> Service:
        service = Service(
            master_id=master_id,
            name=name,
            duration_minutes=duration_minutes,
            price=price,
            is_active=True,
        )
        self.session.add(service)
        await self.session.flush()
        return service

    async def save(self, service: Service) -> Service:
        await self.session.flush()
        return service
