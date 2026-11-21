from collections.abc import Collection
from uuid import UUID

from aiip_kit import errors as kit
from aiip_kit.access.checker import AccessChecker
from aiip_kit.access.model import Principal, ProjectGrant

from src.core.access.acl import AclStore
from src.core.access.exc import (
    AccessUnavailableError,
    PermissionDeniedError,
    ProjectNotFoundError,
    RoleNotGrantableError,
)
from src.core.db.enums import Permission
from src.core.db.uow import UnitOfWork
from src.core.security.dto import CurrentUser
from src.core.security.exc import NotAuthenticatedError


class ProjectAccess:
    """Право пользователя на действие в проекте и запись изменений доступа.

    Проверка — та же, что у остальных сервисов: Dragonfly через `aiip-kit`, при
    промахе — снимок из своей БД. Изменение доступа увеличивает версию доступа
    проекта в транзакции и после commit переписывает права в Dragonfly.
    """

    def __init__(self, uow: UnitOfWork, checker: AccessChecker, acl: AclStore) -> None:
        self._uow = uow
        self._checker = checker
        self._acl = acl

    async def require(
        self, project_id: UUID, current_user: CurrentUser, permission: Permission
    ) -> frozenset[str]:
        """Пропускает участника с правом и отдаёт все его права в проекте.

        Raises:
            NotAuthenticatedError: сессия закрыта — 401.
            ProjectNotFoundError: пользователь не участник проекта или проекта нет — 404.
            PermissionDeniedError: участник без нужного права — 403.
            AccessUnavailableError: права не проверить — 503.
        """
        permissions = await self.member_permissions(project_id, current_user)
        if permission not in permissions:
            raise PermissionDeniedError(
                {"project_id": str(project_id), "permission": permission.value},
                {"permission": permission.value},
            )
        return permissions

    async def member_permissions(
        self, project_id: UUID, current_user: CurrentUser
    ) -> frozenset[str]:
        """Права участника без требования конкретного.

        Raises:
            NotAuthenticatedError: сессия закрыта — 401.
            ProjectNotFoundError: пользователь не участник проекта или проекта нет — 404.
            AccessUnavailableError: права не проверить — 503.
        """
        return (await self._grant(project_id, current_user)).permissions

    async def record_change(self, project_id: UUID) -> None:
        """Отмечает в текущей транзакции, что доступ к проекту меняется."""
        await self._uow.projects.bump_acl_version(project_id)

    async def publish(self, project_id: UUID, user_id: UUID) -> None:
        """После commit: переписывает права участника в Dragonfly для всех сервисов."""
        await self._acl.refresh(project_id, user_id)

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

    async def _grant(self, project_id: UUID, current_user: CurrentUser) -> ProjectGrant:
        principal = Principal(current_user.user_id, current_user.session_id)
        try:
            return await self._checker.grant(principal, project_id)
        except kit.NotAuthenticatedError as exc:
            raise NotAuthenticatedError({"reason": "session_closed"}) from exc
        except kit.ProjectNotFoundError as exc:
            raise ProjectNotFoundError({"project_id": str(project_id)}) from exc
        except kit.DependencyUnavailableError as exc:
            raise AccessUnavailableError({"dependency": exc.dependency}) from exc
