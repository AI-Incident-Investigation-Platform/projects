from collections.abc import Collection
from uuid import UUID

from src.core.access.exc import PermissionDeniedError, ProjectNotFoundError, RoleNotGrantableError
from src.core.db.enums import Permission
from src.core.db.uow import UnitOfWork


class ProjectAccess:
    """Право пользователя на действие в проекте по его членству и роли."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def require(
        self, project_id: UUID, user_id: UUID, permission: Permission
    ) -> frozenset[str]:
        """Пропускает участника с правом и отдаёт все его права в проекте.

        Raises:
            ProjectNotFoundError: пользователь не участник проекта или проекта нет — 404.
            PermissionDeniedError: участник без нужного права — 403.
        """
        permissions = await self._uow.memberships.get_permissions(project_id, user_id)
        if permissions is None:
            raise ProjectNotFoundError({"project_id": str(project_id)})
        if permission not in permissions:
            raise PermissionDeniedError(
                {"project_id": str(project_id), "permission": permission.value},
                {"permission": permission.value},
            )
        return permissions

    async def member_permissions(self, project_id: UUID, user_id: UUID) -> frozenset[str]:
        """Права участника без требования конкретного.

        Raises:
            ProjectNotFoundError: пользователь не участник проекта или проекта нет — 404.
        """
        permissions = await self._uow.memberships.get_permissions(project_id, user_id)
        if permissions is None:
            raise ProjectNotFoundError({"project_id": str(project_id)})
        return permissions

    @staticmethod
    def require_grantable(
        granter_permissions: frozenset[str], role_permissions: Collection[str], role_key: str
    ) -> None:
        """Назначить, снять или пригласить с ролью можно, только если её права есть у тебя.

        Raises:
            RoleNotGrantableError: в роли есть право, которого нет у назначающего — 403.
        """
        if not set(role_permissions) <= granter_permissions:
            raise RoleNotGrantableError({"role": role_key}, {"role": role_key})
