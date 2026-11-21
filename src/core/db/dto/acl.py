from dataclasses import dataclass


@dataclass(frozen=True)
class AclEntryDTO:
    """Доступ пользователя к проекту из БД: роль и её права; не участник — роль `None`."""

    acl_version: int
    role_key: str | None
    role_version: int | None
    permissions: tuple[str, ...]
