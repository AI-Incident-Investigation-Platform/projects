from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from src.core.db.models.membership import Membership
from src.core.db.models.project import Project
from src.core.db.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def list_for_member(
        self, user_id: UUID, after: UUID | None, limit: int
    ) -> Sequence[Project]:
        query = (
            select(Project)
            .join(Membership, Membership.project_id == Project.id)
            .where(Membership.user_id == user_id)
            .order_by(Project.id)
            .limit(limit)
        )
        if after is not None:
            query = query.where(Project.id > after)
        return (await self._session.scalars(query)).all()
