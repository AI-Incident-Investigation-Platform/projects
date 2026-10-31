from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

type EnvironmentSlug = Annotated[
    str, Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
]


class EnvironmentWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: EnvironmentSlug
    is_production: bool = False


class EnvironmentUpdateRequest(BaseModel):
    """Частичное изменение: не переданное поле не меняется, null не принимается."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: EnvironmentSlug | None = None
    is_production: bool | None = None

    @model_validator(mode="after")
    def _forbid_null(self) -> Self:
        if nulls := [f for f in self.model_fields_set if getattr(self, f) is None]:
            raise ValueError(f"поля не могут быть null: {', '.join(sorted(nulls))}")
        return self


class EnvironmentResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    slug: str
    is_production: bool


class EnvironmentsPageResponse(BaseModel):
    items: list[EnvironmentResponse]
    next_cursor: str | None
