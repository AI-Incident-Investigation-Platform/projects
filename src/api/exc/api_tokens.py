from src.core.errors import NotFoundError, RuleViolationError


class ApiTokenNotFoundError(NotFoundError):
    code = "api_token.not_found"
    message = "API-токен не найден"


class ApiTokenEnvironmentInvalidError(RuleViolationError):
    code = "api_token.environment_invalid"
    message = "Окружение не найдено в этом проекте"


class ApiTokenExpiryInvalidError(RuleViolationError):
    code = "api_token.expiry_invalid"
    message = "Срок действия токена должен быть в будущем"
