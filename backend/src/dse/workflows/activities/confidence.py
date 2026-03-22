from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from temporalio import activity

from dse.core.enums import EvidenceType
from dse.core.models import Evidence

logger = structlog.get_logger(__name__)

# Evidence type → confidence delta
# Design ref: PROJECT.md Section 6.2
EVIDENCE_DELTA: dict[EvidenceType, float] = {
    EvidenceType.USER_EXPLICIT_CORRECTION: 1.0,
    EvidenceType.CORROBORATING_SOURCE: 0.15,
    EvidenceType.CONTRADICTING_SOURCE: -0.20,
    EvidenceType.PASSAGE_OF_TIME: -0.01,
    EvidenceType.REPEATED_ACCESS: 0.05,
    EvidenceType.RELATION_DERIVED: -0.05,
}


def compute_confidence_update(prior: float, evidence: Evidence) -> float:
    """Compute the posterior confidence given prior and new evidence.

    For USER_EXPLICIT_CORRECTION: forces to evidence.forced_value (or 1.0).
    For all others: applies delta clamped to [0.0, 1.0].
    """
    if evidence.type == EvidenceType.USER_EXPLICIT_CORRECTION:
        return evidence.forced_value if evidence.forced_value is not None else 1.0

    delta = EVIDENCE_DELTA.get(evidence.type, 0.0)

    # Independent corroborating sources are weighted more heavily
    if evidence.type == EvidenceType.CORROBORATING_SOURCE:
        delta *= 1.5 if evidence.source_independent else 0.7

    return max(0.0, min(1.0, prior + delta))


@activity.defn
async def update_confidence_activity(memory_id: str, evidence_dict: dict[str, Any]) -> float:
    """Update a memory's confidence score based on new evidence.

    Returns the updated confidence value.
    """
    from dse.api.deps import get_search_service

    evidence = Evidence(**evidence_dict)
    search = get_search_service()

    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise ValueError(f"Memory not found: {memory_id}")

    current = results[0]
    prior = float(current.get("confidence", 0.5))
    new_confidence = compute_confidence_update(prior, evidence)

    # Build patch
    from dse.core.models import MemoryRecord

    patch_data = {
        **current,
        "confidence": new_confidence,
        "confidence_updated_at": datetime.now(UTC).isoformat(),
    }
    if evidence.type == EvidenceType.CORROBORATING_SOURCE:
        patch_data["corroborating_sources"] = int(current.get("corroborating_sources", 0)) + 1
    elif evidence.type == EvidenceType.CONTRADICTING_SOURCE:
        patch_data["contradicting_sources"] = int(current.get("contradicting_sources", 0)) + 1

    record = MemoryRecord(**patch_data)
    await search.upsert(record)

    logger.info(
        "confidence.updated",
        memory_id=memory_id,
        prior=round(prior, 3),
        posterior=round(new_confidence, 3),
        evidence_type=evidence.type,
    )
    return new_confidence
