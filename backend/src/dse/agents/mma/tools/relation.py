from __future__ import annotations

from typing import Any

import structlog

from dse.api.deps import get_graph_service, get_llm_service, get_search_service
from dse.core.enums import RelationType
from dse.core.models import RelationRecord

logger = structlog.get_logger(__name__)


async def classify_relation_tool(
    memory_a_id: str,
    memory_b_id: str,
) -> dict[str, Any]:
    """2つのメモリ間の関係性を分類する。

    Args:
        memory_a_id: メモリAのID
        memory_b_id: メモリBのID

    Returns:
        dict: type (str), confidence (float), reason (str)
    """
    search = get_search_service()
    llm = get_llm_service()
    graph = get_graph_service()

    results_a = await search.search(memory_a_id, top_k=1, filter_archived=False)
    results_b = await search.search(memory_b_id, top_k=1, filter_archived=False)

    if not results_a or not results_b:
        return {"type": "NONE", "confidence": 0.0, "reason": "Memory not found"}

    result = await llm.classify_relation(
        results_a[0].get("summary", ""),
        results_b[0].get("summary", ""),
    )

    relation_type = str(result.get("type", "NONE"))
    confidence = float(result.get("confidence", 0.0))

    if relation_type != "NONE" and confidence > 0.7:
        try:
            await graph.create_relation(
                RelationRecord(
                    from_id=memory_a_id,
                    to_id=memory_b_id,
                    relation_type=RelationType(relation_type),
                    confidence=confidence,
                    created_by="mma",
                    method="llm_classification",
                )
            )
        except ValueError:
            logger.warning("mma.invalid_relation_type", relation_type=relation_type)

    return {
        "type": relation_type,
        "confidence": confidence,
        "reason": str(result.get("reason", "")),
    }


async def create_relation_tool(
    from_id: str,
    to_id: str,
    relation_type: str,
    confidence: float = 0.8,
    reason: str = "",
) -> dict[str, Any]:
    """2つのメモリ間に関係を直接作成する。

    Args:
        from_id: 始点メモリID
        to_id: 終点メモリID
        relation_type: 関係タイプ（"SUPERSEDED_BY", "COMPLEMENTS", etc.）
        confidence: 関係の確信度（0.0〜1.0）
        reason: 作成理由

    Returns:
        dict: status (str)
    """
    graph = get_graph_service()

    try:
        await graph.create_relation(
            RelationRecord(
                from_id=from_id,
                to_id=to_id,
                relation_type=RelationType(relation_type),
                confidence=confidence,
                created_by="mma",
                method=reason or "manual_creation",
            )
        )
        return {"status": "created", "from_id": from_id, "to_id": to_id, "type": relation_type}
    except (ValueError, Exception) as e:
        return {"status": "error", "error": str(e)}
