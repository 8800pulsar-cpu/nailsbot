from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.repositories.users import UserRepository


class ClientService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = UserRepository(session)

    async def ensure_user(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        return await self.repo.upsert(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )

    async def list_clients(self) -> list[User]:
        return await self.repo.list_all()
