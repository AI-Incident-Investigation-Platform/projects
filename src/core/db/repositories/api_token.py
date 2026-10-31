from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

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
