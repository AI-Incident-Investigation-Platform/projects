from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.core.db.enums import InvitationStatus


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    role: str = Field(min_length=1, max_length=32)


class InvitationProjectResponse(BaseModel):
    id: UUID
    name: str
    slug: str


class InvitationRoleResponse(BaseModel):
    key: str
    name: str


class InvitationResponse(BaseModel):
    id: UUID
    project: InvitationProjectResponse
    user_id: UUID
    role: InvitationRoleResponse
    invited_by: UUID
    status: InvitationStatus
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None


class InvitationsResponse(BaseModel):
    items: list[InvitationResponse]
