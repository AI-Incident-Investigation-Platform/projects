from src.core.errors import NotFoundError


class IngestTokenNotFoundError(NotFoundError):
    """Digest не соответствует ни одному выпущенному токену: `ingest` отвечает 401."""

    code = "api_token.unknown"
    message = "API-токен не найден"
