from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field


class TokenUsage(BaseModel):
    token_id: UUID
    last_used_at: AwareDatetime


class TokenUsedData(BaseModel):
    """`data` команды `token.used` (`backend/messaging.md`): пачка от ingest раз в минуту."""

    items: list[TokenUsage] = Field(max_length=10_000)
