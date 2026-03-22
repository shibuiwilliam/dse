from __future__ import annotations

import json
from typing import Any

import structlog
from temporalio import activity

from dse.agents.mma.prompts import CONTRADICTION_JUDGE_PROMPT
from dse.config import settings
from dse.core.enums import RelationType, VerificationStatus
from dse.core.models import MemoryRecord, RelationRecord

logger = structlog.get_logger(__name__)


@activity.defn
async def search_contradiction_candidates(memory_id: str, namespace: str) -> list[str]:
    """Find existing memories that are semantically similar to the new one.

    Returns IDs of candidates with cosine similarity above threshold.
    """
    from dse.api.deps import get_embedding_service, get_search_service

    search = get_search_service()
    embedding = get_embedding_service()

    # Fetch the new memory's summary
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        return []

    new_summary = results[0].get("summary", "")
    if not new_summary:
        return []

    new_vec = await embedding.encode(new_summary)

    # Search for similar existing memories
    candidates = await search.search(
        new_summary,
        namespace=namespace,
        top_k=10,
        filter_archived=True,
    )

    similar_ids: list[str] = []
    for candidate in candidates:
        cid = candidate.get("id", "")
        if cid == memory_id:
            continue
        c_summary = candidate.get("summary", "")
        if not c_summary:
            continue
        c_vec = await embedding.encode(c_summary)
        sim = await embedding.compute_similarity(new_vec, c_vec)
        if sim > settings.contradiction_cosine_threshold:
            similar_ids.append(cid)

    logger.info(
        "contradiction.candidates_found",
        memory_id=memory_id,
        count=len(similar_ids),
    )
    return similar_ids


@activity.defn
async def llm_judge_contradiction(memory_id: str, candidate_id: str) -> dict[str, Any]:
    """Use LLM to judge the relationship between two similar memories."""
    from dse.api.deps import get_llm_service, get_search_service

    search = get_search_service()
    llm = get_llm_service()

    results_a = await search.search(memory_id, top_k=1, filter_archived=False)
    results_b = await search.search(candidate_id, top_k=1, filter_archived=False)

    if not results_a or not results_b:
        return {"relation": "UNRELATED", "confidence": 0.0, "auto_resolvable": False}

    a = results_a[0]
    b = results_b[0]

    prompt = CONTRADICTION_JUDGE_PROMPT.format(
        id_a=memory_id,
        type_a=a.get("memory_type", ""),
        created_at_a=a.get("created_at", ""),
        confidence_a=a.get("confidence", 0.5),
        summary_a=a.get("summary", ""),
        id_b=candidate_id,
        type_b=b.get("memory_type", ""),
        created_at_b=b.get("created_at", ""),
        confidence_b=b.get("confidence", 0.5),
        summary_b=b.get("summary", ""),
    )

    raw = await llm.generate(prompt, json_mode=True)
    try:
        judgment = json.loads(raw)
    except json.JSONDecodeError:
        judgment = {"relation": "UNRELATED", "confidence": 0.0, "auto_resolvable": False}

    logger.info(
        "contradiction.judged",
        memory_id=memory_id,
        candidate_id=candidate_id,
        relation=judgment.get("relation"),
    )
    return judgment


@activity.defn
async def auto_resolve_contradiction(
    memory_id: str,
    candidate_id: str,
    judgment: dict[str, Any],
) -> None:
    """Auto-resolve a contradiction: newer/higher-confidence wins."""
    from dse.api.deps import get_graph_service, get_search_service

    search = get_search_service()
    graph = get_graph_service()

    results_a = await search.search(memory_id, top_k=1, filter_archived=False)
    results_b = await search.search(candidate_id, top_k=1, filter_archived=False)

    if not results_a or not results_b:
        return

    a = results_a[0]
    b = results_b[0]

    recommended = judgment.get("recommended_keep", "B")
    conf_a = float(a.get("confidence", 0.5))
    conf_b = float(b.get("confidence", 0.5))
    delta = settings.contradiction_auto_resolve_confidence_delta

    # Determine winner: recommended_keep, or highest confidence, or newest
    if recommended == "A" or conf_a - conf_b > delta:
        winner_id, loser_id = memory_id, candidate_id
    elif recommended == "B" or conf_b - conf_a > delta:
        winner_id, loser_id = candidate_id, memory_id
    else:
        # Default: newer wins
        winner_id, loser_id = memory_id, candidate_id

    # Mark loser as superseded
    loser_data = a if loser_id == memory_id else b
    record = MemoryRecord(**{**loser_data, "verification_status": VerificationStatus.SUPERSEDED})
    await search.upsert(record)

    # Create SUPERSEDED_BY edge
    await graph.create_relation(
        RelationRecord(
            from_id=loser_id,
            to_id=winner_id,
            relation_type=RelationType.SUPERSEDED_BY,
            confidence=float(judgment.get("confidence", 0.8)),
            created_by="auto_resolve",
            method="contradiction_auto_resolve",
        )
    )
    logger.info("contradiction.auto_resolved", winner=winner_id, loser=loser_id)


@activity.defn
async def enqueue_manual_resolution(
    memory_id: str,
    candidate_id: str,
    judgment: dict[str, Any],
) -> None:
    """Flag both memories as 'pending' and create a CONTRADICTS edge."""
    from dse.api.deps import get_graph_service, get_search_service

    search = get_search_service()
    graph = get_graph_service()

    # Mark both as contradicted/pending
    for mid in [memory_id, candidate_id]:
        results = await search.search(mid, top_k=1, filter_archived=False)
        if results:
            record = MemoryRecord(
                **{**results[0], "verification_status": VerificationStatus.PENDING}
            )
            await search.upsert(record)

    # Create CONTRADICTS edge
    await graph.create_relation(
        RelationRecord(
            from_id=memory_id,
            to_id=candidate_id,
            relation_type=RelationType.CONTRADICTS,
            confidence=float(judgment.get("confidence", 0.5)),
            created_by="contradiction_check",
            method="llm_judge",
        )
    )
    logger.info(
        "contradiction.enqueued",
        memory_id=memory_id,
        candidate_id=candidate_id,
    )


@activity.defn
async def create_graph_relation(
    memory_id: str,
    candidate_id: str,
    relation_type_str: str,
    confidence: float,
) -> None:
    """Create a generic graph relation between two memories."""
    from dse.api.deps import get_graph_service

    graph = get_graph_service()
    await graph.create_relation(
        RelationRecord(
            from_id=memory_id,
            to_id=candidate_id,
            relation_type=RelationType(relation_type_str),
            confidence=confidence,
            created_by="contradiction_check",
            method="llm_classify",
        )
    )


@activity.defn
async def create_supersedes_relation(memory_id: str, candidate_id: str) -> None:
    """Create a SUPERSEDED_BY relation (new memory supersedes the candidate)."""
    from dse.api.deps import get_graph_service, get_search_service

    search = get_search_service()
    graph = get_graph_service()

    # Mark candidate as superseded
    results = await search.search(candidate_id, top_k=1, filter_archived=False)
    if results:
        record = MemoryRecord(
            **{**results[0], "verification_status": VerificationStatus.SUPERSEDED}
        )
        await search.upsert(record)

    await graph.create_relation(
        RelationRecord(
            from_id=candidate_id,
            to_id=memory_id,
            relation_type=RelationType.SUPERSEDED_BY,
            confidence=0.8,
            created_by="contradiction_check",
            method="duplicate_or_supersede",
        )
    )
    logger.info(
        "contradiction.superseded",
        new_id=memory_id,
        old_id=candidate_id,
    )
