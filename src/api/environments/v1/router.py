from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query, status

from src.api.environments.dto import EnvironmentChanges, EnvironmentInput
from src.api.environments.service import EnvironmentService
from src.api.environments.v1.schemas import (
    EnvironmentResponse,
    EnvironmentsPageResponse,
    EnvironmentUpdateRequest,
    EnvironmentWriteRequest,
)
from src.config import cfg
from src.core.security.dto import CurrentUser

router = APIRouter(tags=["environments"], route_class=DishkaRoute)


@router.get("/projects/{project_id}/environments")
async def list_environments(
    project_id: UUID,
    service: FromDishka[EnvironmentService],
    current_user: FromDishka[CurrentUser],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=cfg.pagination.max_limit)] = cfg.pagination.default_limit,
) -> EnvironmentsPageResponse:
    page = await service.list_environments(current_user, project_id, cursor, limit)
    return EnvironmentsPageResponse(
        items=[
            EnvironmentResponse.model_validate(item, from_attributes=True) for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.post("/projects/{project_id}/environments", status_code=status.HTTP_201_CREATED)
async def create_environment(
    project_id: UUID,
    body: EnvironmentWriteRequest,
    service: FromDishka[EnvironmentService],
    current_user: FromDishka[CurrentUser],
) -> EnvironmentResponse:
    environment = await service.create_environment(
        current_user,
        project_id,
        EnvironmentInput(name=body.name, slug=body.slug, is_production=body.is_production),
    )
    return EnvironmentResponse.model_validate(environment, from_attributes=True)


@router.patch("/environments/{environment_id}")
async def update_environment(
    environment_id: UUID,
    body: EnvironmentUpdateRequest,
    service: FromDishka[EnvironmentService],
    current_user: FromDishka[CurrentUser],
) -> EnvironmentResponse:
    environment = await service.update_environment(
        current_user,
        environment_id,
        EnvironmentChanges(name=body.name, slug=body.slug, is_production=body.is_production),
    )
    return EnvironmentResponse.model_validate(environment, from_attributes=True)
