from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select

from bot.db.models import ApiRequest
from bot.db.repositories.base import Repository


class ApiRequestRepo(Repository):
    async def get(self, user_id: int, key: str) -> ApiRequest | None:
        return await self.session.scalar(
            select(ApiRequest).where(ApiRequest.user_id == user_id, ApiRequest.key == key)
        )

    async def add(self, request: ApiRequest) -> ApiRequest:
        self.session.add(request)
        await self.session.flush()
        return request

    async def prune(self, user_id: int, before: datetime) -> None:
        """Forget a user's old requests: nobody retries a request that is a day old."""
        await self.session.execute(
            delete(ApiRequest)
            .where(ApiRequest.user_id == user_id, ApiRequest.created_at < before)
            .execution_options(synchronize_session=False)
        )
