from src.core.errors import IntegrationBadResponseError, IntegrationUnavailableError


class UsersUnavailableError(IntegrationUnavailableError):
    code = "users.unavailable"
    message = "Сервис пользователей недоступен"


class UsersBadResponseError(IntegrationBadResponseError):
    code = "users.bad_response"
    message = "Сервис пользователей вернул некорректный ответ"
