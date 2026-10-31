from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UserProfile:
    """Профиль из сервиса users: то, что нужно проектам, — кто это и куда писать."""

    id: UUID
    username: str
    display_name: str | None
    email: str
