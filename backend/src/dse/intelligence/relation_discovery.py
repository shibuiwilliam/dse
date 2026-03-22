from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from dse.config import settings
from dse.core.enums import RelationType

logger = structlog.get_logger(__name__)

RELATION_MAP: dict[str, RelationType | None] = {
    "SUPERSEDED_BY": RelationType.SUPERSEDED_BY,
    "COMPLEMENTS": RelationType.COMPLEMENTS,
    "CONTRADICTS": RelationType.CONTRADICTS,
    "DERIVES": RelationType.DERIVES,
    "CAUSES": RelationType.CAUSES,
    "REFERENCES": RelationType.REFERENCES,
    "NONE": None,
}


@dataclass
class DiscoveryResult:
    from_id: str
    to_id: str
    relation_type: RelationType | None
    confidence: float
    reason: str
    registered: bool = False


async def find_candidate_pairs(
    namespace: str,
    *,
    search: Any,
    embedding_svc: Any,
    graph: Any,
) -> list[dict[str, Any]]:
    """Find memory pairs that are semantically similar but have no existing edge.

    Uses embeddings already stored in Elasticsearch to compute cosine similarity
    locally — no Gemini API calls needed.
    """
    memories = await search.search(
        "",
        namespace=namespace,
        top_k=200,
        filter_archived=True,
    )

    # Filter to memories that have embeddings and summaries
    with_vecs: list[dict[str, Any]] = []
    for mem in memories:
        if mem.get("summary") and mem.get("embedding"):
            with_vecs.append(mem)

    pairs: list[dict[str, Any]] = []
    checked: set[tuple[str, str]] = set()

    for i, mem in enumerate(with_vecs):
        vec = mem["embedding"]

        for other in with_vecs[i + 1 : i + 11]:
            pair_key = tuple(sorted([mem["id"], other["id"]]))
            if pair_key in checked:
                continue
            checked.add(pair_key)

            other_vec = other["embedding"]
            sim = await embedding_svc.compute_similarity(vec, other_vec)

            if sim > settings.discovery_similarity_threshold:
                has_edge = await graph.any_relation_exists(mem["id"], other["id"])
                if not has_edge:
                    pairs.append(
                        {
                            "id_a": mem["id"],
                            "id_b": other["id"],
                            "summary_a": mem.get("summary", ""),
                            "summary_b": other.get("summary", ""),
                        }
                    )

    return pairs


async def classify_pair(
    id_a: str,
    id_b: str,
    summary_a: str,
    summary_b: str,
    *,
    llm: Any,
) -> DiscoveryResult:
    """Classify the relation between two memories using LLM."""
    prompt = f"""以下の2つのメモリの関係を分類してください。

Memory A: {summary_a}
Memory B: {summary_b}

関係タイプ（A→B 方向）:
- SUPERSEDED_BY: AがBに置き換えられた
- COMPLEMENTS: AとBが合わさってより完全な情報
- CONTRADICTS: AとBは相反する
- DERIVES: AからBが推論・要約された
- CAUSES: AがBを引き起こした
- REFERENCES: AはBを参照
- NONE: 関係なし

必ず以下のJSONのみを返すこと:
{{"relation_type": "...", "confidence": 0.0-1.0, "reason": "理由を30文字以内"}}"""

    try:
        result = await llm.generate_json(prompt)
    except Exception:
        result = {"relation_type": "NONE", "confidence": 0.0, "reason": "parse_error"}

    rel_type = RELATION_MAP.get(str(result.get("relation_type", "NONE")))
    return DiscoveryResult(
        from_id=id_a,
        to_id=id_b,
        relation_type=rel_type,
        confidence=float(result.get("confidence", 0.0)),
        reason=str(result.get("reason", "")),
    )


async def discover_relations(
    namespace: str,
    *,
    search: Any,
    embedding_svc: Any,
    llm: Any,
    graph: Any,
) -> list[DiscoveryResult]:
    """Run the full relation discovery pipeline for a namespace."""
    logger.info("discovery.started", namespace=namespace)

    pairs = await find_candidate_pairs(
        namespace, search=search, embedding_svc=embedding_svc, graph=graph
    )
    if not pairs:
        logger.info("discovery.no_candidates", namespace=namespace)
        return []

    results: list[DiscoveryResult] = []
    for pair in pairs[: settings.discovery_max_pairs_per_batch]:
        result = await classify_pair(
            pair["id_a"],
            pair["id_b"],
            pair["summary_a"],
            pair["summary_b"],
            llm=llm,
        )
        results.append(result)

        if (
            result.relation_type is not None
            and result.confidence >= settings.discovery_min_llm_confidence
        ):
            await graph.create_relation_if_not_exists(
                from_id=result.from_id,
                to_id=result.to_id,
                relation_type=result.relation_type,
                properties={
                    "confidence": result.confidence,
                    "discovered_by": "auto",
                    "method": "embedding_similarity+llm",
                },
            )
            result.registered = True

    registered = sum(1 for r in results if r.registered)
    logger.info(
        "discovery.completed", namespace=namespace, checked=len(results), registered=registered
    )
    return results
