from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentInput:
    name: str
    slug: str
    is_production: bool


@dataclass(frozen=True)
class EnvironmentChanges:
    """Частичное изменение окружения: None — поле не меняется."""

    name: str | None = None
    slug: str | None = None
    is_production: bool | None = None
