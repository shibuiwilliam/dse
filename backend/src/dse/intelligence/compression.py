from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from dse.config import settings
from dse.core.enums import MemorySubtype, MemoryType, RelationType, SourceType
from dse.core.models import MemoryRecord

logger = structlog.get_logger(__name__)


@dataclass
class CompressionCluster:
    """A cluster of episodic memories eligible for semantic compression."""

    episode_ids: list[str]
    episode_summaries: list[str]
    avg_confidence: float
    embeddings: list[list[float]] = field(default_factory=list)


@dataclass
class CompressionResult:
    """Result of distilling a cluster."""

    semantic_memory_id: str
    source_episode_ids: list[str]
    generated_summary: str
    confidence: float
    skipped_reason: str | None = None


def cluster_episodes_by_similarity(
    episodes: list[dict[str, Any]],
    embeddings: list[list[float]],
    min_cluster_size: int,
) -> list[CompressionCluster]:
    """Cluster episodes using HDBSCAN on embedding vectors.

    Falls back to a simpler approach if HDBSCAN is not available.
    """
    if len(episodes) < min_cluster_size:
        return []

    try:
        import hdbscan
        import numpy as np

        matrix = np.array(embeddings, dtype=np.float32)
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        labels = clusterer.fit_predict(matrix)

        cluster_map: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            if label >= 0:
                cluster_map.setdefault(label, []).append(idx)

    except ImportError:
        # Fallback: simple tag-based grouping when HDBSCAN unavailable
        logger.warning("compression.hdbscan_unavailable_using_fallback")
        cluster_map = {0: list(range(len(episodes)))}

    clusters: list[CompressionCluster] = []
    for indices in cluster_map.values():
        if len(indices) < min_cluster_size:
            continue
        cluster_eps = [episodes[i] for i in indices]
        avg_conf = sum(ep.get("confidence", 0.5) for ep in cluster_eps) / len(cluster_eps)
        clusters.append(
            CompressionCluster(
                episode_ids=[ep["id"] for ep in cluster_eps],
                episode_summaries=[ep.get("summary", "") for ep in cluster_eps],
                avg_confidence=avg_conf,
                embeddings=[embeddings[i] for i in indices],
            )
        )
    return clusters


async def generalize_summaries(
    summaries: list[str],
    llm: Any,
) -> str:
    """Use LLM to generalize a cluster of episode summaries into semantic knowledge."""
    episodes_text = "\n".join(f"- {s}" for s in summaries)
    prompt = f"""あなたはAIエージェントのメモリ管理AIです。
以下の複数のエピソード記憶から、共通するパターン・知識・ルールを
1つのセマンティック記憶（一般的な事実・傾向・知識）として表現してください。

エピソード群:
{episodes_text}

要件:
- 具体的な日時・固有名詞は避け、一般化された知識として表現する
- 1〜3文で簡潔にまとめる
- 日本語で記述する
- JSON などの構造は不要、テキストのみ

セマンティック記憶:"""
    return (await llm.generate(prompt)).strip()


async def distill_cluster(
    namespace: str,
    cluster: CompressionCluster,
    *,
    search: Any,
    embedding_svc: Any,
    llm: Any,
    graph: Any,
) -> CompressionResult:
    """Distill a single cluster into a semantic memory.

    Idempotent: checks for existing similar semantic memory first.
    """
    # Skip if avg confidence too low
    if cluster.avg_confidence < settings.compression_min_avg_confidence:
        return CompressionResult(
            semantic_memory_id="",
            source_episode_ids=cluster.episode_ids,
            generated_summary="",
            confidence=0.0,
            skipped_reason=f"avg_confidence={cluster.avg_confidence:.2f} < threshold",
        )

    # Idempotency: check for existing similar semantic memory
    # Search for similar existing semantic memories
    existing = await search.search(
        cluster.episode_summaries[0],
        namespace=namespace,
        memory_types=["semantic"],
        top_k=3,
    )
    for ex in existing:
        ex_tags = ex.get("tags", [])
        if "compressed" in ex_tags or ex.get("memory_subtype") == "inference":
            return CompressionResult(
                semantic_memory_id=ex["id"],
                source_episode_ids=cluster.episode_ids,
                generated_summary=ex.get("summary", ""),
                confidence=float(ex.get("confidence", 0.5)),
                skipped_reason="similar_semantic_already_exists",
            )

    # Generate summary
    summary = await generalize_summaries(cluster.episode_summaries, llm)

    # Create semantic memory
    vector = await embedding_svc.encode(summary)
    record = MemoryRecord(
        namespace=namespace,
        memory_type=MemoryType.SEMANTIC,
        memory_subtype=MemorySubtype.INFERENCE,
        summary=summary,
        content_text=summary,
        embedding=vector,
        confidence=round(cluster.avg_confidence * 0.9, 4),
        source_type=SourceType.INFERENCE,
        importance_score=0.70,
        decay_score=1.0,
        tags=["compressed", "semantic-compression"],
    )
    await search.upsert(record)
    await graph.register_node(record)

    # DERIVES edges
    for ep_id in cluster.episode_ids:
        await graph.create_relation_if_not_exists(
            from_id=record.id,
            to_id=ep_id,
            relation_type=RelationType.DERIVES,
            properties={
                "method": "semantic_compression",
                "confidence": cluster.avg_confidence,
            },
        )

    # Decay source episode importance
    for ep_id in cluster.episode_ids:
        ep_results = await search.search(ep_id, top_k=1, filter_archived=False)
        if ep_results:
            ep = ep_results[0]
            new_imp = (
                float(ep.get("importance_score", 0.5))
                * settings.compression_source_importance_decay
            )
            ep_record = MemoryRecord(**{**ep, "importance_score": max(0.1, new_imp)})
            await search.upsert(ep_record)

    logger.info(
        "compression.distilled",
        semantic_id=record.id,
        source_count=len(cluster.episode_ids),
    )
    return CompressionResult(
        semantic_memory_id=record.id,
        source_episode_ids=cluster.episode_ids,
        generated_summary=summary,
        confidence=cluster.avg_confidence,
    )
