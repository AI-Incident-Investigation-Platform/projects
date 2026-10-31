from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status

from src.api.members.service import MemberService
from src.api.members.v1.schemas import (
    MemberResponse,
    MembersResponse,
    MemberUpdateRequest,
    RoleResponse,
    RolesResponse,
)
from src.core.security.dto import CurrentUser

router = APIRouter(prefix="/projects/{project_id}", tags=["members"], route_class=DishkaRoute)


@router.get("/members")
async def list_members(
    project_id: UUID, service: FromDishka[MemberService], current_user: FromDishka[CurrentUser]
) -> MembersResponse:
    members = await service.list_members(current_user, project_id)
    return MembersResponse(
        items=[MemberResponse.model_validate(member, from_attributes=True) for member in members]
    )


@router.patch("/members/{user_id}")
async def change_member_role(
    project_id: UUID,
    user_id: UUID,
    body: MemberUpdateRequest,
    service: FromDishka[MemberService],
    current_user: FromDishka[CurrentUser],
) -> MemberResponse:
    member = await service.change_role(current_user, project_id, user_id, body.role)
    return MemberResponse.model_validate(member, from_attributes=True)


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    service: FromDishka[MemberService],
    current_user: FromDishka[CurrentUser],
) -> None:
    await service.remove(current_user, project_id, user_id)


@router.get("/roles")
async def list_roles(
    project_id: UUID, service: FromDishka[MemberService], current_user: FromDishka[CurrentUser]
) -> RolesResponse:
    roles = await service.list_roles(current_user, project_id)
    return RolesResponse(
        items=[RoleResponse.model_validate(role, from_attributes=True) for role in roles]
    )
