from __future__ import annotations

from typing import Any

import structlog
from temporalio import activity

from dse.intelligence.prospective import compute_fire_patch, should_fire

logger = structlog.get_logger(__name__)


@activity.defn
async def scan_and_fire_prospective_activity(namespace: str) -> list[dict[str, Any]]:
    """Scan for prospective memories that should fire and fire them."""
    from dse.api.deps import get_search_service
    from dse.core.models import MemoryRecord

    search = get_search_service()

    records = await search.search(
        "",
        namespace=namespace,
        memory_types=["prospective"],
        top_k=200,
        filter_archived=True,
    )

    # Filter to unfired only
    records = [r for r in records if not r.get("is_triggered", False)]

    fired: list[dict[str, Any]] = []
    for record in records:
        if should_fire(record):
            patch = compute_fire_patch(record)
            updated = {**record, **patch}
            mem = MemoryRecord(**updated)
            await search.upsert(mem)
            fired.append({"id": record["id"], "summary": record.get("summary", "")})
            logger.info("prospective.fired", memory_id=record["id"])

    return fired


@activity.defn
async def publish_prospective_fired_events_activity(fired: list[dict[str, Any]]) -> None:
    """Publish events for fired prospective memories to Kafka."""
    from dse.infrastructure.events import MockEventPublisher

    publisher = MockEventPublisher()
    for item in fired:
        await publisher.publish_memory_event(
            event_type="prospective.fired",
            memory_id=item["id"],
            namespace="",
            payload={"summary": item.get("summary", "")},
        )
    logger.info("prospective.events_published", count=len(fired))
