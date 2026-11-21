from src.core.errors import ForbiddenError, UnauthenticatedError


class NotAuthenticatedError(UnauthenticatedError):
    code = "security.not_authenticated"
    message = "Требуется вход в систему"


class OriginForbiddenError(ForbiddenError):
    code = "security.origin_forbidden"
    message = "Запрос с этого адреса не принимается"


class ServiceScopeDeniedError(ForbiddenError):
    """Служебный токен верный, но без scope этого эндпоинта."""

    code = "security.scope_denied"
    message = "У сервиса нет права на этот вызов"
