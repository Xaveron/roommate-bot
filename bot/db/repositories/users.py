from __future__ import annotations

from sqlalchemy import func, select

from bot.db.models import User
from bot.db.repositories.base import Repository


class UserRepo(Repository):
    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def upsert(
        self,
        *,
        user_id: int,
        first_name: str,
        last_name: str | None = None,
        username: str | None = None,
        language_code: str | None = None,
    ) -> User:
        """Create the user or refresh their profile fields if they changed."""
        user = await self.get(user_id)
        if user is None:
            user = User(
                id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                language_code=language_code,
                dm_available=False,
            )
            self.session.add(user)
            await self.session.flush()
            return user
        fields = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "language_code": language_code,
        }
        for field, value in fields.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
        return user

    async def count(self) -> int:
        return await self.session.scalar(select(func.count()).select_from(User)) or 0
