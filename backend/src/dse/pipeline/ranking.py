from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime

import structlog

from dse.core.models import MemoryRecord, SearchResult
from dse.pipeline.preprocessing import SearchQuery

logger = structlog.get_logger(__name__)

# RRF constant (standard value from the literature)
RRF_K = 60


def reciprocal_rank_fusion(
    *result_lists: list[SearchResult],
) -> dict[str, float]:
    """Compute Reciprocal Rank Fusion scores across multiple result lists."""
    rrf_scores: dict[str, float] = defaultdict(float)
    for results in result_lists:
        for rank, result in enumerate(results):
            rrf_scores[result.record.id] += 1.0 / (RRF_K + rank + 1)
    return dict(rrf_scores)


def temporal_recency_score(created_at: datetime, now: datetime | None = None) -> float:
    """Score based on how recently the memory was created. Newer = higher."""
    now = now or datetime.now(UTC)
    age_hours = max(0, (now - created_at).total_seconds() / 3600)
    # Sigmoid-like decay: half-life of ~168 hours (7 days)
    return 1.0 / (1.0 + math.log1p(age_hours / 168))


def compute_final_score(
    record: MemoryRecord,
    rrf_score: float,
    query: SearchQuery,
    now: datetime | None = None,
) -> float:
    """Compute the final ranking score for a memory record.

    Combines relevance (RRF), quality (confidence * decay), temporal recency,
    and exploration bonus. Applies superseded penalty.
    """
    from dse.core.enums import VerificationStatus

    relevance = rrf_score
    quality = record.confidence * record.decay_score
    temporal = temporal_recency_score(record.created_at, now)

    # Exploration bonus: less-accessed memories get a boost
    exploration = query.exploration_factor / (1 + record.access_count_30d)

    # Superseded penalty: heavily penalize superseded memories
    superseded_penalty = 0.1 if record.superseded_by else 1.0

    # Contradicted penalty: reduce score for memories flagged as contradicted/pending
    contradiction_penalty = 1.0
    if record.verification_status in (
        VerificationStatus.CONTRADICTED,
        VerificationStatus.PENDING,
    ):
        contradiction_penalty = 0.3

    score = (
        (
            query.relevance_weight * relevance
            + query.quality_weight * quality
            + query.temporal_weight * temporal
            + query.exploration_factor * exploration
        )
        * superseded_penalty
        * contradiction_penalty
    )

    return score


def rerank(
    bm25_results: list[SearchResult],
    vector_results: list[SearchResult],
    query: SearchQuery,
) -> list[SearchResult]:
    """Merge and re-rank results from BM25 and vector search using RRF + custom scoring."""
    # Compute RRF scores
    rrf_scores = reciprocal_rank_fusion(bm25_results, vector_results)

    # Build a lookup of all results
    all_results: dict[str, SearchResult] = {}
    for r in bm25_results:
        all_results[r.record.id] = r
    for r in vector_results:
        all_results[r.record.id] = r

    # Score and sort
    scored: list[SearchResult] = []
    for doc_id, rrf_score in rrf_scores.items():
        result = all_results[doc_id]
        final = compute_final_score(result.record, rrf_score, query)
        scored.append(
            SearchResult(
                record=result.record,
                score=final,
                rrf_score=rrf_score,
                match_source=result.match_source,
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[: query.top_k]
