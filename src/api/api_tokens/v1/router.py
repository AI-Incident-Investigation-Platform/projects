from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query, Response, status

from src.api.api_tokens.dto import ApiTokenInput
from src.api.api_tokens.service import ApiTokenService
from src.api.api_tokens.v1.cookies import forbid_caching
from src.api.api_tokens.v1.schemas import (
    ApiTokenCreateRequest,
    ApiTokenIssuedResponse,
    ApiTokenResponse,
    ApiTokensPageResponse,
)
from src.config import cfg
from src.core.security.dto import CurrentUser

router = APIRouter(
    prefix="/projects/{project_id}/api-tokens", tags=["api-tokens"], route_class=DishkaRoute
)


@router.get("")
async def list_api_tokens(
    project_id: UUID,
    service: FromDishka[ApiTokenService],
    current_user: FromDishka[CurrentUser],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=cfg.pagination.max_limit)] = cfg.pagination.default_limit,
) -> ApiTokensPageResponse:
    page = await service.list_tokens(current_user, project_id, cursor, limit)
    return ApiTokensPageResponse(
        items=[ApiTokenResponse.model_validate(item, from_attributes=True) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def issue_api_token(
    project_id: UUID,
    body: ApiTokenCreateRequest,
    response: Response,
    service: FromDishka[ApiTokenService],
    current_user: FromDishka[CurrentUser],
) -> ApiTokenIssuedResponse:
    issued = await service.issue_token(
        current_user,
        project_id,
        ApiTokenInput(
            name=body.name,
            environment_id=body.environment_id,
            scopes=frozenset(body.scopes),
            expires_at=body.expires_at,
        ),
    )
    forbid_caching(response)
    return ApiTokenIssuedResponse(
        token=ApiTokenResponse.model_validate(issued.token, from_attributes=True),
        secret=issued.secret,
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_token(
    project_id: UUID,
    token_id: UUID,
    service: FromDishka[ApiTokenService],
    current_user: FromDishka[CurrentUser],
) -> None:
    await service.revoke_token(current_user, project_id, token_id)
