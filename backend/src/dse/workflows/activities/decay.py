from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from temporalio import activity

from dse.api.deps import get_search_service
from dse.core.models import MemoryRecord

logger = structlog.get_logger(__name__)


@activity.defn
async def update_decay_scores(namespace: str) -> dict[str, Any]:
    """Update decay scores for all active memories in a namespace.

    Runs as part of the daily maintenance workflow.
    """
    search = get_search_service()
    now = datetime.now(UTC)

    # Fetch all active memories in the namespace
    results = await search.search(
        "",
        namespace=namespace,
        top_k=1000,
        filter_archived=False,
    )

    updated = 0
    archived_candidates = 0

    for raw in results:
        try:
            record = MemoryRecord(**raw)
            new_decay = record.compute_decay_score(now)

            if abs(new_decay - record.decay_score) > 0.01:
                record.decay_score = new_decay
                record.updated_at = now
                await search.upsert(record)
                updated += 1

            if new_decay < 0.2:
                archived_candidates += 1

        except Exception:
            logger.warning("decay.update_failed", memory_id=raw.get("id"))

    logger.info(
        "decay.batch_complete",
        namespace=namespace,
        total=len(results),
        updated=updated,
        archive_candidates=archived_candidates,
    )

    return {
        "namespace": namespace,
        "total": len(results),
        "updated": updated,
        "archive_candidates": archived_candidates,
    }


@activity.defn
async def archive_decayed_memories(namespace: str, threshold: float = 0.2) -> int:
    """Archive memories whose decay score has fallen below the threshold."""
    search = get_search_service()
    now = datetime.now(UTC)

    results = await search.search(
        "",
        namespace=namespace,
        top_k=1000,
        filter_archived=False,
    )

    archived = 0
    for raw in results:
        try:
            decay = float(raw.get("decay_score", 1.0))
            if decay < threshold:
                record = MemoryRecord(**raw)
                record.is_archived = True
                record.archived_at = now
                record.archive_reason = f"decay_score={decay:.3f} < {threshold}"
                await search.upsert(record)
                archived += 1
        except Exception:
            logger.warning("archive.failed", memory_id=raw.get("id"))

    logger.info("archive.batch_complete", namespace=namespace, archived=archived)
    return archived
