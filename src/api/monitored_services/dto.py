from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ServiceInput:
    environment_id: UUID
    name: str
    external_names: tuple[str, ...]
    description: str | None
    repository_url: str | None
    health_url: str | None


@dataclass(frozen=True)
class ServiceChanges:
    """Частичное изменение сервиса: None — поле не меняется.

    URL можно очистить: присланные поля перечислены в `provided`, и присланный None стирает URL.
    """

    provided: frozenset[str]
    environment_id: UUID | None = None
    name: str | None = None
    external_names: tuple[str, ...] | None = None
    description: str | None = None
    repository_url: str | None = None
    health_url: str | None = None
