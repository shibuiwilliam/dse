from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import structlog
from temporalio import activity

from dse.config import settings
from dse.core.enums import RelationType
from dse.intelligence.temporal_reasoning import AllenRelation, TimeInterval, classify_allen_relation

logger = structlog.get_logger(__name__)


@activity.defn
async def build_temporal_edges_activity(namespace: str) -> dict[str, Any]:
    """Build TEMPORALLY_PRECEDES edges between memories in a namespace."""
    from dse.api.deps import get_graph_service, get_search_service

    search = get_search_service()
    graph = get_graph_service()

    window = timedelta(days=settings.temporal_window_days)
    memories = await search.search("", namespace=namespace, top_k=500, filter_archived=True)

    created_count = 0
    for i, mem_a in enumerate(memories):
        created_at_a_str = mem_a.get("created_at", "")
        if not created_at_a_str:
            continue
        try:
            created_at_a = datetime.fromisoformat(str(created_at_a_str))
        except (ValueError, TypeError):
            continue

        for mem_b in memories[i + 1 :]:
            created_at_b_str = mem_b.get("created_at", "")
            if not created_at_b_str:
                continue
            try:
                created_at_b = datetime.fromisoformat(str(created_at_b_str))
            except (ValueError, TypeError):
                continue

            # Skip if outside time window
            if abs((created_at_a - created_at_b).total_seconds()) > window.total_seconds():
                continue

            updated_at_a = created_at_a
            updated_at_b = created_at_b
            try:
                if mem_a.get("updated_at"):
                    updated_at_a = datetime.fromisoformat(str(mem_a["updated_at"]))
                if mem_b.get("updated_at"):
                    updated_at_b = datetime.fromisoformat(str(mem_b["updated_at"]))
            except (ValueError, TypeError):
                pass

            interval_a = TimeInterval(start=created_at_a, end=updated_at_a)
            interval_b = TimeInterval(start=created_at_b, end=updated_at_b)
            relation = classify_allen_relation(interval_a, interval_b)

            if relation in (AllenRelation.BEFORE, AllenRelation.MEETS):
                created = await graph.create_relation_if_not_exists(
                    from_id=mem_a["id"],
                    to_id=mem_b["id"],
                    relation_type=RelationType.TEMPORALLY_PRECEDES,
                    properties={
                        "method": f"allen:{relation.value}",
                        "confidence": 0.9,
                    },
                )
                if created:
                    created_count += 1

    logger.info("temporal.edges_built", namespace=namespace, created=created_count)
    return {"namespace": namespace, "edges_created": created_count}
