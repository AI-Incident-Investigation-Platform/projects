import logging

from aiip_kit.messaging.consumer import Binding, Consumer, QueueSpec
from aiip_kit.messaging.message import MessageV1
from aiip_kit.messaging.topology import commands_exchange
from aio_pika.abc import AbstractChannel
from dishka import AsyncContainer

from src.config import cfg
from src.core.db.exc import DatabaseUnavailableError
from src.worker.token_usage.schemas import TokenUsedData
from src.worker.token_usage.service import TokenUsageService

log = logging.getLogger(__name__)

TOKEN_USED = "token.used"

SPEC = QueueSpec(
    name=f"{cfg.service.name}.token-usage",
    bindings=[Binding(commands_exchange(cfg.service.name), "direct", TOKEN_USED)],
    # БД недоступна — повтор; битое тело и прочее — dead
    transient=(DatabaseUnavailableError,),
)


class TokenUsageConsumer:
    """Очередь `projects.token-usage`: команда `token.used` от ingest."""

    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    async def start(self, channel: AbstractChannel) -> None:
        await Consumer(channel, SPEC, self.handle).start()

    async def handle(self, message: MessageV1, attempt: int) -> None:
        data = TokenUsedData.model_validate(message.data)
        async with self._container() as scope:
            service = await scope.get(TokenUsageService)
            await service.record(data)
        log.debug(
            "Отмечено использование API-токенов",
            extra={"event": "api_token.usage_recorded", "count": len(data.items)},
        )
