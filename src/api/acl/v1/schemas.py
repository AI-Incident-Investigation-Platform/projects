from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class AclMemberResponse(BaseModel):
    role_key: str
    version: int


class AclRoleResponse(BaseModel):
    key: str
    version: int
    permissions: list[str]


class AclResponse(BaseModel):
    """Формат — `backend/decisions.md`, пункт 1; не участник — `member` и `role` равны null."""

    project_id: UUID
    user_id: UUID
    project_state: Literal["active", "deleting", "missing"]
    lifecycle_version: int
    acl_version: int
    member: AclMemberResponse | None
    role: AclRoleResponse | None
    observed_at_ms: int
    fresh_until_ms: int
