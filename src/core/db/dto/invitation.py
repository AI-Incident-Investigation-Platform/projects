from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from src.core.db.dto.project import ProjectDTO
from src.core.db.dto.role import RoleDTO
from src.core.db.enums import InvitationStatus


@dataclass(frozen=True)
class InvitationDTO:
    id: UUID
    project: ProjectDTO
    user_id: UUID
    role: RoleDTO
    invited_by: UUID
    status: InvitationStatus
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None

    @classmethod
    def from_orm(cls, obj: Any) -> Self:
        """Из `Invitation` с загруженными проектом и ролью."""
        return cls(
            id=obj.id,
            project=ProjectDTO.from_orm(obj.project),
            user_id=obj.user_id,
            role=RoleDTO.from_orm(obj.role),
            invited_by=obj.invited_by,
            status=obj.status,
            created_at=obj.created_at,
            expires_at=obj.expires_at,
            responded_at=obj.responded_at,
        )
