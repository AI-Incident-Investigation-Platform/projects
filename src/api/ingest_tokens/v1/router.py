from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Path, Request, Response

from src.api.ingest_tokens.service import IngestTokenService
from src.api.ingest_tokens.v1.schemas import IngestTokenResponse

router = APIRouter(tags=["internal"], route_class=DishkaRoute)


@router.get("/api-tokens/{token_hash}")
async def get_ingest_token(
    token_hash: Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")],
    request: Request,
    response: Response,
    service: FromDishka[IngestTokenService],
) -> IngestTokenResponse:
    snapshot = await service.get(request.headers.get("authorization"), token_hash)
    response.headers["Cache-Control"] = "no-store"
    return IngestTokenResponse.model_validate(snapshot)
