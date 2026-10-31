from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

type Slug = Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")]


class ProjectWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    slug: Slug
    description: str | None = Field(default=None, max_length=2000)


class ProjectUpdateRequest(BaseModel):
    """Частичное изменение: не переданное поле не меняется, null не принимается."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: Slug | None = None
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _forbid_null(self) -> Self:
        if nulls := [f for f in self.model_fields_set if getattr(self, f) is None]:
            raise ValueError(f"поля не могут быть null: {', '.join(sorted(nulls))}")
        return self


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    created_at: datetime
    archived_at: datetime | None


class ProjectsPageResponse(BaseModel):
    items: list[ProjectResponse]
    next_cursor: str | None
