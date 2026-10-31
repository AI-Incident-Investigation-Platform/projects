from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from src.core.db.models.monitored_service import MonitoredService
from src.core.db.repositories.base import BaseRepository


class MonitoredServiceRepository(BaseRepository[MonitoredService]):
    model = MonitoredService

    async def list_for_project(
        self, project_id: UUID, environment_id: UUID | None, after: UUID | None, limit: int
    ) -> Sequence[MonitoredService]:
        query = (
            select(MonitoredService)
            .where(MonitoredService.project_id == project_id)
            .order_by(MonitoredService.id)
            .limit(limit)
        )
        if environment_id is not None:
            query = query.where(MonitoredService.environment_id == environment_id)
        if after is not None:
            query = query.where(MonitoredService.id > after)
        return (await self._session.scalars(query)).all()
