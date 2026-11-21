from uuid import UUID

from src.api.exc.monitored_services import (
    ServiceEnvironmentInvalidError,
    ServiceNameTakenError,
    ServiceNotFoundError,
)
from src.api.monitored_services.dto import ServiceChanges, ServiceInput
from src.core.access.exc import ProjectNotFoundError
from src.core.access.service import ProjectAccess
from src.core.db.dto.monitored_service import MonitoredServiceDTO
from src.core.db.enums import Permission
from src.core.db.exc import IntegrityViolationError
from src.core.db.models.monitored_service import MonitoredService
from src.core.db.pagination import Page
from src.core.db.uow import UnitOfWork
from src.core.security.dto import CurrentUser


class MonitoredServiceService:
    def __init__(self, uow: UnitOfWork, access: ProjectAccess) -> None:
        self._uow = uow
        self._access = access

    async def list_services(
        self,
        current_user: CurrentUser,
        project_id: UUID,
        environment_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> Page[MonitoredServiceDTO]:
        await self._access.require(project_id, current_user, Permission.PROJECT_READ)
        rows = await self._uow.services.list_for_project(
            project_id, environment_id, Page.decode_cursor(cursor), limit + 1
        )
        return Page.from_rows(rows, limit, MonitoredServiceDTO.from_orm)

    async def create_service(
        self, current_user: CurrentUser, project_id: UUID, data: ServiceInput
    ) -> MonitoredServiceDTO:
        await self._access.require(project_id, current_user, Permission.PROJECT_MANAGE)
        await self._require_environment(project_id, data.environment_id)
        service = MonitoredService(
            project_id=project_id,
            environment_id=data.environment_id,
            name=data.name,
            external_names=list(data.external_names),
            description=data.description or "",
            repository_url=data.repository_url,
            health_url=data.health_url,
        )
        self._uow.services.add(service)
        await self._flush_unique_name(data.name)
        await self._uow.commit()
        return MonitoredServiceDTO.from_orm(service)

    async def get_service(self, current_user: CurrentUser, service_id: UUID) -> MonitoredServiceDTO:
        service = await self._load(current_user, service_id, Permission.PROJECT_READ)
        return MonitoredServiceDTO.from_orm(service)

    async def update_service(
        self, current_user: CurrentUser, service_id: UUID, changes: ServiceChanges
    ) -> MonitoredServiceDTO:
        service = await self._load(current_user, service_id, Permission.PROJECT_MANAGE)
        if changes.environment_id is not None:
            await self._require_environment(service.project_id, changes.environment_id)
            service.environment_id = changes.environment_id
        if changes.name is not None:
            service.name = changes.name
        if changes.external_names is not None:
            service.external_names = list(changes.external_names)
        if changes.description is not None:
            service.description = changes.description
        if "repository_url" in changes.provided:
            service.repository_url = changes.repository_url
        if "health_url" in changes.provided:
            service.health_url = changes.health_url
        await self._flush_unique_name(service.name)
        await self._uow.commit()
        return MonitoredServiceDTO.from_orm(service)

    async def _load(
        self, current_user: CurrentUser, service_id: UUID, permission: Permission
    ) -> MonitoredService:
        service = await self._uow.services.get_by_id(service_id)
        if service is None:
            raise ServiceNotFoundError({"service_id": str(service_id)})
        try:
            await self._access.require(service.project_id, current_user, permission)
        except ProjectNotFoundError as exc:
            # не участник не узнаёт, что сервис существует
            raise ServiceNotFoundError({"service_id": str(service_id)}) from exc
        return service

    async def _require_environment(self, project_id: UUID, environment_id: UUID) -> None:
        environment = await self._uow.environments.get_by_id(environment_id)
        if environment is None or environment.project_id != project_id:
            raise ServiceEnvironmentInvalidError(
                {"project_id": str(project_id), "environment_id": str(environment_id)},
                {"environment_id": str(environment_id)},
            )

    async def _flush_unique_name(self, name: str) -> None:
        try:
            await self._uow.flush()
        except IntegrityViolationError as exc:
            if exc.constraint == "uq_monitored_services_environment_id_name":
                raise ServiceNameTakenError({"name": name}) from exc
            raise
