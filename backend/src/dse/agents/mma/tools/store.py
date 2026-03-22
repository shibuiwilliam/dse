from __future__ import annotations

from typing import Any

import structlog

from dse.api.deps import (
    get_embedding_service,
    get_graph_service,
    get_llm_service,
    get_search_service,
    get_storage_service,
)
from dse.config import settings
from dse.core.enums import MemoryType, RelationType, SourceType
from dse.core.models import MemoryRecord, RelationRecord

logger = structlog.get_logger(__name__)


async def store_memory_tool(
    namespace: str,
    content_text: str,
    memory_type: str,
    confidence: float = 0.5,
    source_type: str = "observation",
    source_id: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """新規メモリを登録する。

    Args:
        namespace: メモリのスコープ（例: "agent:alice/project:alpha"）
        content_text: メモリの内容テキスト
        memory_type: メモリの種別（"episodic", "semantic", "procedural", "prospective"）
        confidence: 確信度（0.0〜1.0）
        source_type: 情報源の種類（"observation", "inference", "user_explicit", "external_api"）
        source_id: 情報源の識別子
        tags: タグリスト

    Returns:
        dict: memory_id, status, summary を含む結果
    """
    search = get_search_service()
    embedding = get_embedding_service()
    storage = get_storage_service()
    graph = get_graph_service()
    llm = get_llm_service()

    summary = await llm.generate_summary(content_text)
    importance = await llm.assess_importance(content_text)
    importance_score = float(importance.get("importance_score", 0.5))
    vector = await embedding.encode(f"{summary} {content_text[:500]}")

    # Duplicate/contradiction check
    existing_results = await search.search(summary, namespace=namespace, top_k=5)
    contradicting_ids: list[tuple[str, float]] = []

    for existing in existing_results:
        existing_summary = existing.get("summary", "")
        if existing_summary:
            existing_vec = await embedding.encode(existing_summary)
            similarity = await embedding.compute_similarity(vector, existing_vec)
            if similarity > settings.contradiction_cosine_threshold:
                contradiction = await llm.detect_contradiction(summary, existing_summary)
                if contradiction.get("is_contradictory"):
                    contradicting_ids.append(
                        (
                            existing["id"],
                            float(contradiction.get("confidence", 0.5)),
                        )
                    )
                else:
                    return {
                        "memory_id": existing["id"],
                        "status": "duplicate_detected",
                        "summary": existing_summary,
                    }

    record = MemoryRecord(
        namespace=namespace,
        content_text=content_text,
        summary=summary,
        embedding=vector,
        memory_type=MemoryType(memory_type),
        confidence=confidence,
        source_type=SourceType(source_type),
        source_id=source_id,
        importance_score=importance_score,
        tags=tags or [],
        entities=list(importance.get("entities", [])),
    )

    content_path = await storage.store_content(namespace, record.id, content_text)
    record.content_path = content_path
    await search.upsert(record)
    await graph.register_node(record)

    for existing_id, conf in contradicting_ids:
        await graph.create_relation(
            RelationRecord(
                from_id=existing_id,
                to_id=record.id,
                relation_type=RelationType.CONTRADICTS,
                confidence=conf,
                created_by="mma",
                method="store_memory_duplicate_check",
            )
        )

    logger.info("mma.memory_stored", memory_id=record.id, memory_type=memory_type)
    return {
        "memory_id": record.id,
        "status": "created",
        "summary": summary,
        "importance_score": importance_score,
    }
