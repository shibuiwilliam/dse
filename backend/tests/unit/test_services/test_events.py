from __future__ import annotations

import pytest

from dse.infrastructure.events import MockEventPublisher


class TestMockEventPublisher:
    @pytest.mark.asyncio
    async def test_publish_event(self) -> None:
        publisher = MockEventPublisher()
        await publisher.publish_memory_event(
            event_type="create",
            memory_id="m1",
            namespace="test",
            payload={"summary": "test"},
        )
        assert len(publisher._events) == 1
        assert publisher._events[0]["event_type"] == "create"
        assert publisher._events[0]["memory_id"] == "m1"

    @pytest.mark.asyncio
    async def test_publish_multiple_events(self) -> None:
        publisher = MockEventPublisher()
        for i in range(5):
            await publisher.publish_memory_event(
                event_type="update",
                memory_id=f"m{i}",
                namespace="test",
            )
        assert len(publisher._events) == 5

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        publisher = MockEventPublisher()
        await publisher.close()  # Should not raise
