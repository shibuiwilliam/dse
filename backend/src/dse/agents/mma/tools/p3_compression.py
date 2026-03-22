from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def compress_memories_tool(
    namespace: str,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """エピソード記憶群をセマンティック記憶に蒸留する。

    Args:
        namespace: 対象のNamespace
        lookback_days: 蒸留対象期間（日数）

    Returns:
        dict: status, distilled count, skipped count
    """
    from dse.api.deps import (
        get_embedding_service,
        get_graph_service,
        get_llm_service,
        get_search_service,
    )
    from dse.intelligence.compression import cluster_episodes_by_similarity, distill_cluster

    search = get_search_service()
    embedding_svc = get_embedding_service()
    llm = get_llm_service()
    graph = get_graph_service()

    episodes = await search.search(
        "", namespace=namespace, memory_types=["episodic"], top_k=500, filter_archived=True
    )

    if len(episodes) < 5:
        return {"status": "skipped", "reason": "too_few_episodes", "count": len(episodes)}

    embeddings = [await embedding_svc.encode(ep.get("summary", "")) for ep in episodes]
    clusters = cluster_episodes_by_similarity(episodes, embeddings, min_cluster_size=5)

    distilled = 0
    skipped = 0
    for cluster in clusters:
        result = await distill_cluster(
            namespace, cluster, search=search, embedding_svc=embedding_svc, llm=llm, graph=graph
        )
        if result.skipped_reason:
            skipped += 1
        else:
            distilled += 1

    logger.info("mma.compression_complete", distilled=distilled, skipped=skipped)
    return {"status": "completed", "distilled": distilled, "skipped": skipped}
