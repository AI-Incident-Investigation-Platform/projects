from dataclasses import dataclass
from uuid import UUID

from src.core.db.dto.base import BaseDTO


@dataclass(frozen=True)
class EnvironmentDTO(BaseDTO):
    id: UUID
    project_id: UUID
    slug: str
    name: str
    is_production: bool
