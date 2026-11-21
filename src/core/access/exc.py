from src.core.errors import ForbiddenError, IntegrationUnavailableError, NotFoundError


class ProjectNotFoundError(NotFoundError):
    """Проекта нет или пользователь в нём не участник: чужой не отличить от несуществующего."""

    code = "project.not_found"
    message = "Проект не найден"


class PermissionDeniedError(ForbiddenError):
    code = "access.permission_denied"
    message = "Недостаточно прав в проекте"


class RoleNotGrantableError(ForbiddenError):
    """Роль шире прав того, кто её назначает или снимает: admin не трогает owner'а."""

    code = "access.role_not_grantable"
    message = "Нельзя назначить или изменить роль шире своих прав"


class AccessUnavailableError(IntegrationUnavailableError):
    """Права не проверить: Dragonfly или БД недоступны. Пропустить без проверки нельзя."""

    code = "access.unavailable"
    message = "Не удалось проверить права, повторите позже"
