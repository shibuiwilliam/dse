from __future__ import annotations

from typing import Any

import structlog
from temporalio import activity

from dse.api.deps import (
    get_embedding_service,
    get_graph_service,
    get_llm_service,
    get_search_service,
)
from dse.core.enums import RelationType

logger = structlog.get_logger(__name__)


@activity.defn
async def discover_relations(namespace: str) -> dict[str, Any]:
    """Discover latent relationships between memories in a namespace.

    Finds similar memory pairs via embedding similarity and uses LLM
    to classify the relationship type.
    """
    search = get_search_service()
    embedding = get_embedding_service()
    llm = get_llm_service()
    graph = get_graph_service()

    # Get all active memories
    results = await search.search(
        "",
        namespace=namespace,
        top_k=200,
        filter_archived=False,
    )

    if len(results) < 2:
        return {"namespace": namespace, "discovered": 0}

    discovered = 0

    # Compare pairs (limited to avoid quadratic explosion)
    for i, record_a in enumerate(results[:50]):
        summary_a = record_a.get("summary", "")
        if not summary_a:
            continue

        vec_a = await embedding.encode(summary_a)

        for record_b in results[i + 1 : i + 11]:  # Check next 10 only
            summary_b = record_b.get("summary", "")
            if not summary_b:
                continue

            vec_b = await embedding.encode(summary_b)
            similarity = await embedding.compute_similarity(vec_a, vec_b)

            if similarity > 0.75:
                # Classify relationship
                relation = await llm.classify_relation(summary_a, summary_b)
                rel_type = str(relation.get("type", "NONE"))
                confidence = float(relation.get("confidence", 0.0))

                if rel_type != "NONE" and confidence > 0.7:
                    try:
                        await graph.create_edge(
                            record_a.get("id", ""),
                            record_b.get("id", ""),
                            RelationType(rel_type),
                            {
                                "confidence": confidence,
                                "discovered_by": "auto",
                                "method": "embedding_similarity + llm_classification",
                            },
                        )
                        discovered += 1
                    except (ValueError, Exception):
                        logger.warning(
                            "discover.edge_failed",
                            rel_type=rel_type,
                        )

    logger.info("discover.complete", namespace=namespace, discovered=discovered)
    return {"namespace": namespace, "discovered": discovered}
