from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import Master
from app.repositories.masters import MasterRepository


class MasterNotConfiguredError(RuntimeError):
    pass


class MasterService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.repo = MasterRepository(session)
        self.settings = settings

    async def get_current(self) -> Master:
        if self.settings.master_id is not None:
            master = await self.repo.get_by_id(self.settings.master_id)
            if master is None or not master.is_active:
                raise MasterNotConfiguredError(
                    "MASTER_ID из .env не найден или мастер неактивен."
                )
            return master

        active = await self.repo.list_active()
        if not active:
            raise MasterNotConfiguredError(
                "Мастер ещё не создан. Запустите: python -m app.bootstrap"
            )
        if len(active) > 1:
            raise MasterNotConfiguredError(
                "В базе несколько мастеров. Укажите MASTER_ID в .env."
            )
        return active[0]

    async def update(self, master: Master, **fields: str) -> Master:
        if "timezone" in fields:
            from zoneinfo import ZoneInfo

            ZoneInfo(fields["timezone"])
        return await self.repo.update_fields(master, **fields)
