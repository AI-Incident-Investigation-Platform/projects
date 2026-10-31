from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from src.core.db.enums import TokenScope


class ApiTokenCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    environment_id: UUID | None = None
    scopes: list[TokenScope] = Field(
        default_factory=lambda: list(TokenScope), min_length=1, max_length=len(TokenScope)
    )
    expires_at: AwareDatetime | None = None


class ApiTokenResponse(BaseModel):
    id: UUID
    project_id: UUID
    environment_id: UUID | None
    name: str
    prefix: str
    scopes: list[TokenScope]
    created_by: UUID
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiTokenIssuedResponse(BaseModel):
    token: ApiTokenResponse
    secret: str


class ApiTokensPageResponse(BaseModel):
    items: list[ApiTokenResponse]
    next_cursor: str | None
