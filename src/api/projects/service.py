import logging
from uuid import UUID

from src.api.exc.projects import ProjectSlugTakenError
from src.api.projects.dto import ProjectChanges, ProjectInput
from src.core.access.exc import ProjectNotFoundError
from src.core.access.service import ProjectAccess
from src.core.db.dto.project import ProjectDTO
from src.core.db.enums import BuiltinRole, Permission
from src.core.db.exc import IntegrityViolationError
from src.core.db.models.membership import Membership
from src.core.db.models.project import Project
from src.core.db.pagination import Page
from src.core.db.uow import UnitOfWork
from src.core.security.dto import CurrentUser

log = logging.getLogger(__name__)


class ProjectService:
    def __init__(self, uow: UnitOfWork, access: ProjectAccess) -> None:
        self._uow = uow
        self._access = access

    async def list_projects(
        self, current_user: CurrentUser, cursor: str | None, limit: int
    ) -> Page[ProjectDTO]:
        rows = await self._uow.projects.list_for_member(
            current_user.user_id, Page.decode_cursor(cursor), limit + 1
        )
        return Page.from_rows(rows, limit, ProjectDTO.from_orm)

    async def create_project(self, current_user: CurrentUser, data: ProjectInput) -> ProjectDTO:
        owner = await self._uow.roles.get_by_key(BuiltinRole.OWNER)
        if owner is None:
            raise RuntimeError("built-in role owner is missing: migrations are not applied")
        project = Project(name=data.name, slug=data.slug, description=data.description or "")
        self._uow.projects.add(project)
        await self._flush_unique_slug(data.slug)
        self._uow.memberships.add(
            Membership(project_id=project.id, user_id=current_user.user_id, role_id=owner.id)
        )
        await self._uow.commit()
        log.info(
            "Создан проект, создатель стал владельцем",
            extra={"event": "project.created", "project_id": str(project.id)},
        )
        return ProjectDTO.from_orm(project)

    async def get_project(self, current_user: CurrentUser, project_id: UUID) -> ProjectDTO:
        await self._access.require(project_id, current_user.user_id, Permission.PROJECT_READ)
        return ProjectDTO.from_orm(await self._load(project_id))

    async def update_project(
        self, current_user: CurrentUser, project_id: UUID, changes: ProjectChanges
    ) -> ProjectDTO:
        await self._access.require(project_id, current_user.user_id, Permission.PROJECT_MANAGE)
        project = await self._load(project_id)
        if changes.name is not None:
            project.name = changes.name
        if changes.slug is not None:
            project.slug = changes.slug
        if changes.description is not None:
            project.description = changes.description
        await self._flush_unique_slug(project.slug)
        await self._uow.commit()
        return ProjectDTO.from_orm(project)

    async def _load(self, project_id: UUID) -> Project:
        project = await self._uow.projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError({"project_id": str(project_id)})
        return project

    async def _flush_unique_slug(self, slug: str) -> None:
        try:
            await self._uow.flush()
        except IntegrityViolationError as exc:
            if exc.constraint == "uq_projects_slug":
                raise ProjectSlugTakenError({"slug": slug}) from exc
            raise
