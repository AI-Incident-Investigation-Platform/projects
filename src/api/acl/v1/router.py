from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Request, Response

from src.api.acl.service import AclService
from src.api.acl.v1.schemas import AclResponse

router = APIRouter(tags=["internal"], route_class=DishkaRoute)


@router.get("/acl")
async def get_acl(
    project_id: UUID,
    user_id: UUID,
    request: Request,
    response: Response,
    service: FromDishka[AclService],
) -> AclResponse:
    snapshot = await service.get(request.headers.get("authorization"), project_id, user_id)
    # ответ — момент чтения со своей свежестью: промежуточным кэшам его хранить нельзя
    response.headers["Cache-Control"] = "no-store"
    return AclResponse.model_validate(snapshot.to_json())
