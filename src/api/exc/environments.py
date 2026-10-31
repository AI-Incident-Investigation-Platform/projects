from src.core.errors import ConflictError, NotFoundError


class EnvironmentNotFoundError(NotFoundError):
    code = "environment.not_found"
    message = "Окружение не найдено"


class EnvironmentSlugTakenError(ConflictError):
    code = "environment.slug_taken"
    message = "Окружение с таким slug в проекте уже есть"
