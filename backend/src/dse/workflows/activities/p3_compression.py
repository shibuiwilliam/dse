from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from temporalio import activity

from dse.config import settings

logger = structlog.get_logger(__name__)


@activity.defn
async def cluster_episodes_activity(namespace: str, lookback_days: int) -> list[dict[str, Any]]:
    """Fetch episodic memories and cluster them via HDBSCAN.

    Returns lightweight cluster dicts (IDs + summaries only, no embeddings)
    to stay well under Temporal's 4MB gRPC payload limit.
    """
    from dse.api.deps import get_search_service
    from dse.intelligence.compression import cluster_episodes_by_similarity

    search = get_search_service()

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    episodes = await search.search(
        "",
        namespace=namespace,
        memory_types=["episodic"],
        top_k=500,
        filter_archived=True,
    )

    # Filter by date and importance
    episodes = [
        ep
        for ep in episodes
        if ep.get("created_at", "") >= cutoff.isoformat()
        and float(ep.get("importance_score", 0)) >= 0.3
    ]

    if len(episodes) < settings.compression_min_cluster_size:
        return []

    # Use embeddings already stored in Elasticsearch (no Gemini API calls)
    embeddings: list[list[float]] = []
    valid_episodes: list[dict[str, Any]] = []
    for ep in episodes:
        vec = ep.get("embedding")
        if vec and isinstance(vec, list) and len(vec) > 0:
            embeddings.append(vec)
            valid_episodes.append(ep)

    if len(valid_episodes) < settings.compression_min_cluster_size:
        return []

    clusters = cluster_episodes_by_similarity(
        valid_episodes, embeddings, settings.compression_min_cluster_size
    )

    # Return lightweight data only — NO embeddings (they'd blow the 4MB Temporal limit)
    return [
        {
            "episode_ids": c.episode_ids,
            "episode_summaries": c.episode_summaries,
            "avg_confidence": c.avg_confidence,
            # Embeddings are NOT passed through Temporal. The distill activity
            # will re-fetch them from Elasticsearch if needed.
        }
        for c in clusters
    ]


@activity.defn
async def distill_cluster_activity(namespace: str, cluster_dict: dict[str, Any]) -> dict[str, Any]:
    """Distill a single cluster into a semantic memory."""
    from dse.api.deps import (
        get_embedding_service,
        get_graph_service,
        get_llm_service,
        get_search_service,
    )
    from dse.intelligence.compression import CompressionCluster, distill_cluster

    cluster = CompressionCluster(
        episode_ids=cluster_dict["episode_ids"],
        episode_summaries=cluster_dict["episode_summaries"],
        avg_confidence=cluster_dict["avg_confidence"],
        embeddings=cluster_dict.get("embeddings", []),
    )

    result = await distill_cluster(
        namespace,
        cluster,
        search=get_search_service(),
        embedding_svc=get_embedding_service(),
        llm=get_llm_service(),
        graph=get_graph_service(),
    )

    return {
        "semantic_memory_id": result.semantic_memory_id,
        "source_episode_ids": result.source_episode_ids,
        "generated_summary": result.generated_summary,
        "confidence": result.confidence,
        "skipped_reason": result.skipped_reason,
    }
