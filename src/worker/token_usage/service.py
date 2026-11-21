from src.core.db.uow import UnitOfWork
from src.worker.token_usage.schemas import TokenUsedData


class TokenUsageService:
    """Отметка использования API-токенов, которую присылает ingest."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def record(self, data: TokenUsedData) -> None:
        """Сдвигает `last_used_at` вперёд; повторная доставка пачки ничего не меняет.

        Идемпотентность — в самой операции (`greatest`), поэтому inbox по
        `message_id` не нужен. Неизвестный или удалённый токен пропускается.
        """
        for item in sorted(data.items, key=lambda usage: usage.token_id):
            await self._uow.api_tokens.mark_used(item.token_id, item.last_used_at)
        await self._uow.commit()
