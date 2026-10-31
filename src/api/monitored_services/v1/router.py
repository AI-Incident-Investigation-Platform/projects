from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query, status

from src.api.monitored_services.dto import ServiceChanges, ServiceInput
from src.api.monitored_services.service import MonitoredServiceService
from src.api.monitored_services.v1.schemas import (
    ServiceResponse,
    ServicesPageResponse,
    ServiceUpdateRequest,
    ServiceWriteRequest,
)
from src.config import cfg
from src.core.security.dto import CurrentUser

router = APIRouter(tags=["services"], route_class=DishkaRoute)


@router.get("/projects/{project_id}/services")
async def list_services(
    project_id: UUID,
    service: FromDishka[MonitoredServiceService],
    current_user: FromDishka[CurrentUser],
    environment_id: UUID | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=cfg.pagination.max_limit)] = cfg.pagination.default_limit,
) -> ServicesPageResponse:
    page = await service.list_services(current_user, project_id, environment_id, cursor, limit)
    return ServicesPageResponse(
        items=[ServiceResponse.model_validate(item, from_attributes=True) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.post("/projects/{project_id}/services", status_code=status.HTTP_201_CREATED)
async def create_service(
    project_id: UUID,
    body: ServiceWriteRequest,
    service: FromDishka[MonitoredServiceService],
    current_user: FromDishka[CurrentUser],
) -> ServiceResponse:
    created = await service.create_service(
        current_user,
        project_id,
        ServiceInput(
            environment_id=body.environment_id,
            name=body.name,
            external_names=tuple(body.external_names),
            description=body.description,
            repository_url=body.repository_url,
            health_url=body.health_url,
        ),
    )
    return ServiceResponse.model_validate(created, from_attributes=True)


@router.get("/services/{service_id}")
async def get_service(
    service_id: UUID,
    service: FromDishka[MonitoredServiceService],
    current_user: FromDishka[CurrentUser],
) -> ServiceResponse:
    found = await service.get_service(current_user, service_id)
    return ServiceResponse.model_validate(found, from_attributes=True)


@router.patch("/services/{service_id}")
async def update_service(
    service_id: UUID,
    body: ServiceUpdateRequest,
    service: FromDishka[MonitoredServiceService],
    current_user: FromDishka[CurrentUser],
) -> ServiceResponse:
    updated = await service.update_service(
        current_user,
        service_id,
        ServiceChanges(
            provided=frozenset(body.model_fields_set),
            environment_id=body.environment_id,
            name=body.name,
            external_names=tuple(body.external_names) if body.external_names is not None else None,
            description=body.description,
            repository_url=body.repository_url,
            health_url=body.health_url,
        ),
    )
    return ServiceResponse.model_validate(updated, from_attributes=True)
