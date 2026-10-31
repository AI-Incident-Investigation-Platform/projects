from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleResponse(BaseModel):
    key: str
    name: str
    permissions: list[str]


class RolesResponse(BaseModel):
    items: list[RoleResponse]


class MemberResponse(BaseModel):
    user_id: UUID
    role: RoleResponse
    joined_at: datetime


class MembersResponse(BaseModel):
    items: list[MemberResponse]


class MemberUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=32)
