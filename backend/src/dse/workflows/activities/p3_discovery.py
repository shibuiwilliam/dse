from __future__ import annotations

from typing import Any

import structlog
from temporalio import activity

logger = structlog.get_logger(__name__)


@activity.defn
async def discover_relations_activity(namespace: str) -> dict[str, Any]:
    """Run the relation discovery pipeline for a namespace."""
    from dse.api.deps import (
        get_embedding_service,
        get_graph_service,
        get_llm_service,
        get_search_service,
    )
    from dse.intelligence.relation_discovery import discover_relations

    results = await discover_relations(
        namespace,
        search=get_search_service(),
        embedding_svc=get_embedding_service(),
        llm=get_llm_service(),
        graph=get_graph_service(),
    )

    registered = sum(1 for r in results if r.registered)
    return {"namespace": namespace, "checked": len(results), "registered": registered}
