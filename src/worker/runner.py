import asyncio
import contextlib
import logging

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from aio_pika.exceptions import AMQPError
from dishka import AsyncContainer

from src.config import cfg
from src.worker.token_usage.consumer import TokenUsageConsumer

log = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5


async def run_consumers(container: AsyncContainer, stop: asyncio.Event) -> None:
    """Консьюмеры процесса: подключается к брокеру, пока не выйдет; дальше переподключается сам.

    Недоступный при старте брокер не мешает HTTP: попытки повторяются в фоне.
    """
    connection: AbstractRobustConnection | None = None
    while connection is None and not stop.is_set():
        try:
            connection = await aio_pika.connect_robust(
                cfg.rabbitmq.url, timeout=cfg.rabbitmq.connect_timeout_seconds
            )
            channel = await connection.channel(publisher_confirms=True)
            await TokenUsageConsumer(container).start(channel)
        except AMQPError, OSError, TimeoutError:
            if connection is not None:
                await connection.close()
                connection = None
            log.warning(
                "Брокер недоступен, консьюмеры не запущены",
                extra={"event": "consumer.connect_failed"},
            )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), RECONNECT_DELAY_SECONDS)
    await stop.wait()
    if connection is not None:
        await connection.close()
