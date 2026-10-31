from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectInput:
    name: str
    slug: str
    description: str | None


@dataclass(frozen=True)
class ProjectChanges:
    """Частичное изменение проекта: None — поле не меняется."""

    name: str | None = None
    slug: str | None = None
    description: str | None = None
