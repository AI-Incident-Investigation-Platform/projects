from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update

from src.core.db.models.api_token import ApiToken
from src.core.db.repositories.base import BaseRepository


class ApiTokenRepository(BaseRepository[ApiToken]):
    model = ApiToken

    async def list_for_project(
        self, project_id: UUID, after: UUID | None, limit: int
    ) -> Sequence[ApiToken]:
        query = (
            select(ApiToken)
            .where(ApiToken.project_id == project_id)
            .order_by(ApiToken.id)
            .limit(limit)
        )
        if after is not None:
            query = query.where(ApiToken.id > after)
        return (await self._session.scalars(query)).all()

    async def get_in_project(self, project_id: UUID, token_id: UUID) -> ApiToken | None:
        return await self._session.scalar(
            select(ApiToken).where(ApiToken.project_id == project_id, ApiToken.id == token_id)
        )

    async def get_by_hash(self, token_hash: str) -> ApiToken | None:
        return await self._session.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash))

    async def mark_used(self, token_id: UUID, used_at: datetime) -> None:
        """Сдвигает `last_used_at` только вперёд: повтор или опоздавшая пачка ничего не портят."""
        await self._session.execute(
            update(ApiToken)
            .where(ApiToken.id == token_id)
            .values(
                last_used_at=func.greatest(func.coalesce(ApiToken.last_used_at, used_at), used_at)
            )
        )
