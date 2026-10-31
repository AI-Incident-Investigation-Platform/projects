from uuid import UUID

from src.api.environments.dto import EnvironmentChanges, EnvironmentInput
from src.api.exc.environments import EnvironmentNotFoundError, EnvironmentSlugTakenError
from src.core.access.exc import ProjectNotFoundError
from src.core.access.service import ProjectAccess
from src.core.db.dto.environment import EnvironmentDTO
from src.core.db.enums import Permission
from src.core.db.exc import IntegrityViolationError
from src.core.db.models.environment import Environment
from src.core.db.pagination import Page
from src.core.db.uow import UnitOfWork
from src.core.security.dto import CurrentUser


class EnvironmentService:
    def __init__(self, uow: UnitOfWork, access: ProjectAccess) -> None:
        self._uow = uow
        self._access = access

    async def list_environments(
        self, current_user: CurrentUser, project_id: UUID, cursor: str | None, limit: int
    ) -> Page[EnvironmentDTO]:
        await self._access.require(project_id, current_user.user_id, Permission.PROJECT_READ)
        rows = await self._uow.environments.list_for_project(
            project_id, Page.decode_cursor(cursor), limit + 1
        )
        return Page.from_rows(rows, limit, EnvironmentDTO.from_orm)

    async def create_environment(
        self, current_user: CurrentUser, project_id: UUID, data: EnvironmentInput
    ) -> EnvironmentDTO:
        await self._access.require(project_id, current_user.user_id, Permission.PROJECT_MANAGE)
        environment = Environment(
            project_id=project_id,
            name=data.name,
            slug=data.slug,
            is_production=data.is_production,
        )
        self._uow.environments.add(environment)
        await self._flush_unique_slug(data.slug)
        await self._uow.commit()
        return EnvironmentDTO.from_orm(environment)

    async def update_environment(
        self, current_user: CurrentUser, environment_id: UUID, changes: EnvironmentChanges
    ) -> EnvironmentDTO:
        environment = await self._uow.environments.get_by_id(environment_id)
        if environment is None:
            raise EnvironmentNotFoundError({"environment_id": str(environment_id)})
        try:
            await self._access.require(
                environment.project_id, current_user.user_id, Permission.PROJECT_MANAGE
            )
        except ProjectNotFoundError as exc:
            # не участник не узнаёт, что окружение существует
            raise EnvironmentNotFoundError({"environment_id": str(environment_id)}) from exc
        if changes.name is not None:
            environment.name = changes.name
        if changes.slug is not None:
            environment.slug = changes.slug
        if changes.is_production is not None:
            environment.is_production = changes.is_production
        await self._flush_unique_slug(environment.slug)
        await self._uow.commit()
        return EnvironmentDTO.from_orm(environment)

    async def _flush_unique_slug(self, slug: str) -> None:
        try:
            await self._uow.flush()
        except IntegrityViolationError as exc:
            if exc.constraint == "uq_environments_project_id_slug":
                raise EnvironmentSlugTakenError({"slug": slug}) from exc
            raise
