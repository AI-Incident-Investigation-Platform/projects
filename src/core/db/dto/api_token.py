from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from src.core.db.dto.base import BaseDTO


@dataclass(frozen=True)
class ApiTokenDTO(BaseDTO):
    id: UUID
    project_id: UUID
    environment_id: UUID | None
    name: str
    prefix: str
    scopes: tuple[str, ...]
    created_by: UUID
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def from_orm(cls, obj: Any) -> Self:
        dto = super().from_orm(obj)
        return cls(**{**dto.__dict__, "scopes": tuple(obj.scopes)})
