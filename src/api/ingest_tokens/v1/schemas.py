from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class IngestTokenResponse(BaseModel):
    """Формат — `backend/decisions.md`, пункт 2."""

    state: Literal["active", "revoked", "expired"]
    token_id: UUID
    project_id: UUID
    environment_id: UUID | None
    scopes: list[str]
    lifecycle_version: int
    ver: int
    expires_at: datetime | None
    observed_at_ms: int
    fresh_until_ms: int
