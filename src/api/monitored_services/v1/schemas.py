from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

type HttpUrlString = Annotated[str, Field(max_length=2048, pattern=r"^https?://\S+$")]
type ExternalName = Annotated[str, Field(min_length=1, max_length=160)]


class ServiceWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: UUID
    name: str = Field(min_length=1, max_length=160)
    external_names: list[ExternalName] = Field(default_factory=list, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    repository_url: HttpUrlString | None = None
    health_url: HttpUrlString | None = None


class ServiceUpdateRequest(BaseModel):
    """Частичное изменение: не переданное поле не меняется; null очищает только URL."""

    model_config = ConfigDict(extra="forbid")

    environment_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    external_names: list[ExternalName] | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    repository_url: HttpUrlString | None = None
    health_url: HttpUrlString | None = None

    @model_validator(mode="after")
    def _forbid_null(self) -> Self:
        nullable = {"repository_url", "health_url"}
        nulls = [f for f in self.model_fields_set - nullable if getattr(self, f) is None]
        if nulls:
            raise ValueError(f"поля не могут быть null: {', '.join(sorted(nulls))}")
        return self


class ServiceResponse(BaseModel):
    id: UUID
    project_id: UUID
    environment_id: UUID
    name: str
    external_names: list[str]
    description: str
    repository_url: str | None
    health_url: str | None
    created_at: datetime


class ServicesPageResponse(BaseModel):
    items: list[ServiceResponse]
    next_cursor: str | None
