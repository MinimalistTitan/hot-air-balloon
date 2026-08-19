import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from confluent_kafka import KafkaError, Message, Producer


@dataclass(frozen=True, slots=True)
class PublishResult:
    topic: str
    key: str
    
class MessagePublisher(Protocol):
    async def publish(
        self,
        *,
        topic: str,
        key: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
    ) -> None: ...

    async def flush(self, timeout_seconds: float = 30.0) -> None: ...
    
class ConfluentKafkaPublisher:
    def __init__(
        self,
        *,
        bootstrap_servers: list[str],
        client_id: str,
    ) -> None:
        self._producer = Producer(
            {
                "bootstrap.servers": ",".join(bootstrap_servers),
                "client.id": client_id,
                "enable.idempotence": True,
                "acks": "all",
                "retries": 10,
                "retry.backoff.ms": 100,
                "delivery.timeout.ms": 120_000,
                "request.timeout.ms": 30_000,
                "linger.ms": 5,
                "max.in.flight.requests.per.connection": 5,
            }
        )

    async def publish(
        self,
        *,
        topic: str,
        key: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
    ) -> None:
        payload_bytes = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
        encoded_headers: list[tuple[str, str | bytes | None]] = [
            (header_key, header_value.encode("utf-8")) for header_key, header_value in headers.items()
        ]
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()

        def on_delivery(err: KafkaError | None, msg: Message) -> None:  # confluent-kafka callback signature
            if future.done():
                return
            if err is not None:
                loop.call_soon_threadsafe(
                    future.set_exception,
                    RuntimeError(f"kafka delivery failed: {err}"),
                )
                return
            loop.call_soon_threadsafe(future.set_result, None)

        for attempt in range(6):
            try:
                self._producer.produce(
                    topic=topic,
                    key=key.encode("utf-8"),
                    value=payload_bytes,
                    headers=encoded_headers,
                    on_delivery=on_delivery,
                )
                break
            except BufferError:
                if attempt == 5:
                    raise
                await asyncio.sleep(min(0.5, 0.05 * (2**attempt)))

        while not future.done():
            self._producer.poll(0.1)
            await asyncio.sleep(0)

        await future

    async def flush(self, timeout_seconds: float = 30.0) -> None:
        await asyncio.to_thread(self._producer.flush, timeout_seconds)