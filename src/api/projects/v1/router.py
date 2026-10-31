from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query, status

from src.api.projects.dto import ProjectChanges, ProjectInput
from src.api.projects.service import ProjectService
from src.api.projects.v1.schemas import (
    ProjectResponse,
    ProjectsPageResponse,
    ProjectUpdateRequest,
    ProjectWriteRequest,
)
from src.config import cfg
from src.core.security.dto import CurrentUser

router = APIRouter(prefix="/projects", tags=["projects"], route_class=DishkaRoute)


@router.get("")
async def list_projects(
    service: FromDishka[ProjectService],
    current_user: FromDishka[CurrentUser],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=cfg.pagination.max_limit)] = cfg.pagination.default_limit,
) -> ProjectsPageResponse:
    page = await service.list_projects(current_user, cursor, limit)
    return ProjectsPageResponse(
        items=[ProjectResponse.model_validate(item, from_attributes=True) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectWriteRequest,
    service: FromDishka[ProjectService],
    current_user: FromDishka[CurrentUser],
) -> ProjectResponse:
    project = await service.create_project(
        current_user, ProjectInput(name=body.name, slug=body.slug, description=body.description)
    )
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    service: FromDishka[ProjectService],
    current_user: FromDishka[CurrentUser],
) -> ProjectResponse:
    project = await service.get_project(current_user, project_id)
    return ProjectResponse.model_validate(project, from_attributes=True)


@router.patch("/{project_id}")
async def update_project(
    project_id: UUID,
    body: ProjectUpdateRequest,
    service: FromDishka[ProjectService],
    current_user: FromDishka[CurrentUser],
) -> ProjectResponse:
    project = await service.update_project(
        current_user,
        project_id,
        ProjectChanges(name=body.name, slug=body.slug, description=body.description),
    )
    return ProjectResponse.model_validate(project, from_attributes=True)
