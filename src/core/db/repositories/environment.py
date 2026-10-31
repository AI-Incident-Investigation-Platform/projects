from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from src.core.db.models.environment import Environment
from src.core.db.repositories.base import BaseRepository


class EnvironmentRepository(BaseRepository[Environment]):
    model = Environment

    async def list_for_project(
        self, project_id: UUID, after: UUID | None, limit: int
    ) -> Sequence[Environment]:
        query = (
            select(Environment)
            .where(Environment.project_id == project_id)
            .order_by(Environment.id)
            .limit(limit)
        )
        if after is not None:
            query = query.where(Environment.id > after)
        return (await self._session.scalars(query)).all()
