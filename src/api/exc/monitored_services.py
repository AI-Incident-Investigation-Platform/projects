from src.core.errors import ConflictError, NotFoundError, RuleViolationError


class ServiceNotFoundError(NotFoundError):
    code = "service.not_found"
    message = "Сервис не найден"


class ServiceNameTakenError(ConflictError):
    code = "service.name_taken"
    message = "Сервис с таким именем в окружении уже есть"


class ServiceEnvironmentInvalidError(RuleViolationError):
    code = "service.environment_invalid"
    message = "Окружение не найдено в этом проекте"
