from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.core.db.models.membership import Membership
from src.core.db.models.role import Role
from src.core.db.repositories.base import BaseRepository


class MembershipRepository(BaseRepository[Membership]):
    model = Membership

    async def get_permissions(self, project_id: UUID, user_id: UUID) -> frozenset[str] | None:
        """Права участника в проекте; не участник — None."""
        permissions = await self._session.scalar(
            select(Role.permissions)
            .join(Membership, Membership.role_id == Role.id)
            .where(Membership.project_id == project_id, Membership.user_id == user_id)
        )
        return None if permissions is None else frozenset(permissions)

    async def get_for_update(self, project_id: UUID, user_id: UUID) -> Membership | None:
        query = (
            select(Membership)
            .options(joinedload(Membership.role))
            .where(Membership.project_id == project_id, Membership.user_id == user_id)
            .with_for_update(of=Membership)
        )
        return await self._session.scalar(query)

    async def list_for_project(self, project_id: UUID) -> Sequence[Membership]:
        query = (
            select(Membership)
            .options(joinedload(Membership.role))
            .where(Membership.project_id == project_id)
            .order_by(Membership.created_at, Membership.user_id)
        )
        return (await self._session.scalars(query)).all()

    async def lock_holders(self, project_id: UUID, permission: str) -> Sequence[UUID]:
        """Участники с правом под блокировкой: параллельное снятие не оставит проект без них."""
        query = (
            select(Membership.user_id)
            .join(Role, Role.id == Membership.role_id)
            .where(Membership.project_id == project_id, Role.permissions.contains([permission]))
            .order_by(Membership.user_id)
            .with_for_update(of=Membership)
        )
        return (await self._session.scalars(query)).all()

    async def delete(self, membership: Membership) -> None:
        await self._session.delete(membership)
