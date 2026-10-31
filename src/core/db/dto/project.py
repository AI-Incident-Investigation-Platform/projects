from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.core.db.dto.base import BaseDTO


@dataclass(frozen=True)
class ProjectDTO(BaseDTO):
    id: UUID
    slug: str
    name: str
    description: str
    created_at: datetime
    archived_at: datetime | None
