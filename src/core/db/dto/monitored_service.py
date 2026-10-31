from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from src.core.db.dto.base import BaseDTO


@dataclass(frozen=True)
class MonitoredServiceDTO(BaseDTO):
    id: UUID
    project_id: UUID
    environment_id: UUID
    name: str
    external_names: tuple[str, ...]
    description: str
    repository_url: str | None
    health_url: str | None
    created_at: datetime

    @classmethod
    def from_orm(cls, obj: Any) -> Self:
        dto = super().from_orm(obj)
        return cls(**{**dto.__dict__, "external_names": tuple(obj.external_names)})
