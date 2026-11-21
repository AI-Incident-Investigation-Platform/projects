from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, update

from src.core.db.dto.acl import AclEntryDTO
from src.core.db.models.membership import Membership
from src.core.db.models.project import Project
from src.core.db.models.role import Role
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

    async def bump_acl_version(self, project_id: UUID) -> None:
        """Отмечает изменение доступа; строка проекта остаётся заблокированной до commit.

        Блокировка выстраивает изменения доступа одного проекта в очередь, и версия
        в Dragonfly растёт в том же порядке, что и commit'ы.
        """
        await self._session.execute(
            update(Project)
            .where(Project.id == project_id)
            # изменение участников не меняет сам проект: updated_at остаётся прежним
            .values(acl_version=Project.acl_version + 1, updated_at=Project.updated_at)
        )

    async def get_acl(self, project_id: UUID, user_id: UUID) -> AclEntryDTO | None:
        """Доступ пользователя к проекту; проекта нет — None."""
        query = (
            select(Project.acl_version, Role.key, Role.version, Role.permissions)
            .select_from(Project)
            .outerjoin(
                Membership,
                (Membership.project_id == Project.id) & (Membership.user_id == user_id),
            )
            .outerjoin(Role, Role.id == Membership.role_id)
            .where(Project.id == project_id)
        )
        row = (await self._session.execute(query)).one_or_none()
        if row is None:
            return None
        acl_version, role_key, role_version, permissions = row
        return AclEntryDTO(
            acl_version=acl_version,
            role_key=role_key,
            role_version=role_version,
            permissions=tuple(permissions or ()),
        )
