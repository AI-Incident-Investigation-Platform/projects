from dataclasses import dataclass
from typing import Any, Self
from uuid import UUID

from src.core.db.dto.base import BaseDTO


@dataclass(frozen=True)
class RoleDTO(BaseDTO):
    id: UUID
    key: str
    name: str
    permissions: tuple[str, ...]

    @classmethod
    def from_orm(cls, obj: Any) -> Self:
        return cls(id=obj.id, key=obj.key, name=obj.name, permissions=tuple(obj.permissions))
