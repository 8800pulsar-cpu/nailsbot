from __future__ import annotations

import asyncio
import logging
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import load_database_url
from app.database.session import create_engine, create_session_factory
from app.repositories.masters import MasterRepository
from app.repositories.schedules import ScheduleRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_first_master(session: AsyncSession) -> None:
    masters = MasterRepository(session)
    existing = await masters.list_active()
    if existing:
        master = existing[0]
        logger.info("Master already exists: id=%s name=%s", master.id, master.name)
        print(f"Мастер уже есть. ID={master.id}. Укажите MASTER_ID={master.id} в .env при нескольких мастерах.")
        return

    master = await masters.create(
        name="Мастер",
        description="Опишите услуги и опыт. Текст можно изменить в боте: /admin → Настройки мастера.",
        contact="Телефон или @username",
        address="Адрес студии",
        timezone="Europe/Moscow",
    )
    schedules = ScheduleRepository(session)
    for weekday in range(7):
        await schedules.upsert_weekday(
            master_id=master.id,
            weekday=weekday,
            start_time=time(10, 0),
            end_time=time(20, 0),
            is_working=weekday < 6,
        )
    await session.commit()
    print(
        "Создан первый мастер.\n"
        f"ID={master.id}\n"
        "Дальше:\n"
        "1. При нескольких мастерах добавьте MASTER_ID в .env\n"
        "2. Напишите боту /admin со своего Telegram\n"
        "3. Заполните имя, описание, контакт, адрес, услуги и расписание"
    )


async def main() -> None:
    engine = create_engine(load_database_url())
    factory = create_session_factory(engine)
    async with factory() as session:
        await create_first_master(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
