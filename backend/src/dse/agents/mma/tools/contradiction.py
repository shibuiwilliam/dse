from __future__ import annotations

from typing import Any

import structlog

from dse.api.deps import get_graph_service, get_llm_service, get_search_service
from dse.core.enums import RelationType, VerificationStatus
from dse.core.models import MemoryRecord, RelationRecord

logger = structlog.get_logger(__name__)


async def detect_contradiction_tool(
    memory_a_id: str,
    memory_b_id: str,
) -> dict[str, Any]:
    """2つのメモリ間の矛盾を検出する。

    Args:
        memory_a_id: メモリAのID
        memory_b_id: メモリBのID

    Returns:
        dict: is_contradictory (bool), reason (str), confidence (float)
    """
    search = get_search_service()
    llm = get_llm_service()

    results_a = await search.search(memory_a_id, top_k=1, filter_archived=False)
    results_b = await search.search(memory_b_id, top_k=1, filter_archived=False)

    if not results_a or not results_b:
        return {"is_contradictory": False, "reason": "Memory not found", "confidence": 0.0}

    result = await llm.detect_contradiction(
        results_a[0].get("summary", ""),
        results_b[0].get("summary", ""),
    )
    return {
        "is_contradictory": result.get("is_contradictory", False),
        "reason": str(result.get("reason", "")),
        "confidence": float(result.get("confidence", 0.0)),
    }


async def resolve_contradiction_tool(
    memory_a_id: str,
    memory_b_id: str,
    keep: str,
    reason: str = "",
) -> dict[str, Any]:
    """矛盾する2つのメモリを解決する。

    Args:
        memory_a_id: メモリAのID
        memory_b_id: メモリBのID
        keep: "A" または "B" または "both"
        reason: 解決理由

    Returns:
        dict: status (str), winner_id (str), loser_id (str)
    """
    search = get_search_service()
    graph = get_graph_service()

    if keep == "both":
        return {"status": "dismissed", "reason": reason}

    winner_id = memory_a_id if keep == "A" else memory_b_id
    loser_id = memory_b_id if keep == "A" else memory_a_id

    results = await search.search(loser_id, top_k=1, filter_archived=False)
    if results:
        record = MemoryRecord(
            **{**results[0], "verification_status": VerificationStatus.SUPERSEDED}
        )
        await search.upsert(record)

    await graph.create_relation(
        RelationRecord(
            from_id=loser_id,
            to_id=winner_id,
            relation_type=RelationType.SUPERSEDED_BY,
            confidence=0.9,
            created_by="mma_resolve",
            method=f"manual: {reason}",
        )
    )

    logger.info("mma.contradiction_resolved", winner=winner_id, loser=loser_id)
    return {"status": "resolved", "winner_id": winner_id, "loser_id": loser_id}
