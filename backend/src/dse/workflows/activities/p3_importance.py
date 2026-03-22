from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from temporalio import activity

from dse.config import settings

logger = structlog.get_logger(__name__)


@activity.defn
async def estimate_importance_activity(memory_id: str, context_dict: dict[str, Any]) -> float:
    """Estimate importance for a memory and update the search index."""
    from dse.api.deps import get_llm_service, get_search_service
    from dse.core.models import MemoryRecord
    from dse.intelligence.importance import ImportanceContext, ImportanceEstimator

    search = get_search_service()
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise ValueError(f"Memory not found: {memory_id}")

    record = results[0]
    estimator = ImportanceEstimator(llm=get_llm_service())
    context = ImportanceContext(**context_dict)

    new_score = await estimator.estimate(
        memory_id=memory_id,
        summary=str(record.get("summary", "")),
        memory_type=str(record.get("memory_type", "episodic")),
        context=context,
    )

    updated = MemoryRecord(**{**record, "importance_score": new_score})
    await search.upsert(updated)
    return new_score


@activity.defn
async def reinforce_memory_activity(
    memory_id: str,
    utility_score: float,
    accessor_type: str,
) -> float:
    """Reinforce a memory's importance and decay scores after access."""
    from dse.api.deps import get_search_service
    from dse.core.models import MemoryRecord
    from dse.intelligence.importance import ImportanceEstimator

    search = get_search_service()
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise ValueError(f"Memory not found: {memory_id}")

    record = results[0]
    estimator = ImportanceEstimator()

    new_importance = await estimator.reinforce(
        current_score=float(record.get("importance_score", 0.5)),
        utility_score=utility_score,
        accessor_type=accessor_type,
    )

    recovery_rate = (
        settings.importance_user_access_recovery
        if accessor_type == "user"
        else settings.importance_agent_access_recovery
    )
    new_decay = min(1.0, float(record.get("decay_score", 0.5)) + utility_score * recovery_rate)

    updated = MemoryRecord(
        **{
            **record,
            "importance_score": new_importance,
            "decay_score": new_decay,
            "access_count": int(record.get("access_count", 0)) + 1,
            "accessed_at": datetime.now(UTC).isoformat(),
            "last_access_utility": utility_score,
        }
    )
    await search.upsert(updated)

    logger.info(
        "importance.reinforced",
        memory_id=memory_id,
        importance=round(new_importance, 3),
        decay=round(new_decay, 3),
    )
    return new_importance
