from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from dse.config import settings

logger = structlog.get_logger(__name__)


class EventPublisher:
    """Publishes CDC events to Kafka/Redpanda for downstream processing."""

    def __init__(self) -> None:
        self._producer: Any = None

    async def _get_producer(self) -> Any:
        if self._producer is None:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()
        return self._producer

    async def close(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish_memory_event(
        self,
        event_type: str,
        memory_id: str,
        namespace: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Publish a memory lifecycle event."""
        event = {
            "event_type": event_type,
            "memory_id": memory_id,
            "namespace": namespace,
            "payload": payload or {},
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            producer = await self._get_producer()
            await producer.send_and_wait(
                topic="dse.memory.events",
                value=event,
                key=memory_id.encode("utf-8"),
            )
            logger.info(
                "event.published",
                event_type=event_type,
                memory_id=memory_id,
            )
        except Exception:
            logger.error(
                "event.publish_failed",
                event_type=event_type,
                memory_id=memory_id,
                exc_info=True,
            )


class MockEventPublisher(EventPublisher):
    """In-memory mock for testing."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    async def close(self) -> None:
        pass

    async def publish_memory_event(
        self,
        event_type: str,
        memory_id: str,
        namespace: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._events.append(
            {
                "event_type": event_type,
                "memory_id": memory_id,
                "namespace": namespace,
                "payload": payload or {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
