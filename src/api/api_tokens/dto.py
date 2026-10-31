from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.core.db.dto.api_token import ApiTokenDTO
from src.core.db.enums import TokenScope


@dataclass(frozen=True)
class ApiTokenInput:
    name: str
    environment_id: UUID | None
    scopes: frozenset[TokenScope]
    expires_at: datetime | None


@dataclass(frozen=True)
class IssuedApiToken:
    """Выпущенный токен; `secret` показывается один раз и больше нигде не хранится."""

    token: ApiTokenDTO
    secret: str
