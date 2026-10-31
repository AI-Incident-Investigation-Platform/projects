from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status

from src.api.invitations.service import InvitationService
from src.api.invitations.v1.schemas import (
    InvitationCreateRequest,
    InvitationResponse,
    InvitationsResponse,
)
from src.core.security.dto import CurrentUser

router = APIRouter(tags=["invitations"], route_class=DishkaRoute)


@router.post("/projects/{project_id}/invitations", status_code=status.HTTP_201_CREATED)
async def invite(
    project_id: UUID,
    body: InvitationCreateRequest,
    service: FromDishka[InvitationService],
    current_user: FromDishka[CurrentUser],
) -> InvitationResponse:
    invitation = await service.invite(current_user, project_id, body.user_id, body.role)
    return InvitationResponse.model_validate(invitation, from_attributes=True)


@router.get("/projects/{project_id}/invitations")
async def list_project_invitations(
    project_id: UUID,
    service: FromDishka[InvitationService],
    current_user: FromDishka[CurrentUser],
) -> InvitationsResponse:
    invitations = await service.list_for_project(current_user, project_id)
    return InvitationsResponse(
        items=[InvitationResponse.model_validate(i, from_attributes=True) for i in invitations]
    )


@router.delete(
    "/projects/{project_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_invitation(
    project_id: UUID,
    invitation_id: UUID,
    service: FromDishka[InvitationService],
    current_user: FromDishka[CurrentUser],
) -> None:
    await service.revoke(current_user, project_id, invitation_id)


@router.get("/invitations")
async def list_my_invitations(
    service: FromDishka[InvitationService], current_user: FromDishka[CurrentUser]
) -> InvitationsResponse:
    invitations = await service.list_mine(current_user)
    return InvitationsResponse(
        items=[InvitationResponse.model_validate(i, from_attributes=True) for i in invitations]
    )


@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: UUID,
    service: FromDishka[InvitationService],
    current_user: FromDishka[CurrentUser],
) -> InvitationResponse:
    invitation = await service.accept(current_user, invitation_id)
    return InvitationResponse.model_validate(invitation, from_attributes=True)


@router.post("/invitations/{invitation_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_invitation(
    invitation_id: UUID,
    service: FromDishka[InvitationService],
    current_user: FromDishka[CurrentUser],
) -> None:
    await service.decline(current_user, invitation_id)
