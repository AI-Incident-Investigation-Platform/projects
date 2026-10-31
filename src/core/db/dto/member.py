from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from src.core.db.dto.role import RoleDTO


@dataclass(frozen=True)
class MemberDTO:
    project_id: UUID
    user_id: UUID
    role: RoleDTO
    joined_at: datetime

    @classmethod
    def from_orm(cls, obj: Any) -> Self:
        """Из `Membership` с загруженной ролью."""
        return cls(
            project_id=obj.project_id,
            user_id=obj.user_id,
            role=RoleDTO.from_orm(obj.role),
            joined_at=obj.created_at,
        )
