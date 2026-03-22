from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from dse.api.deps import get_search_service
from dse.core.enums import EvidenceType
from dse.core.models import Evidence, MemoryRecord
from dse.workflows.activities.confidence import compute_confidence_update

logger = structlog.get_logger(__name__)


async def update_confidence_tool(
    memory_id: str,
    evidence_type: str,
    source_independent: bool = False,
    forced_value: float | None = None,
    description: str = "",
) -> dict[str, Any]:
    """メモリの信頼度を証拠に基づいて更新する。

    Args:
        memory_id: 対象メモリのID
        evidence_type: 証拠タイプ（"corroborating_source", "contradicting_source", etc.）
        source_independent: 独立した情報源からの証拠か
        forced_value: 強制値（user_explicit_correctionの場合のみ使用）
        description: 証拠の説明

    Returns:
        dict: memory_id, prior, posterior を含む結果
    """
    search = get_search_service()

    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        return {"error": f"Memory not found: {memory_id}"}

    existing = results[0]
    prior = float(existing.get("confidence", 0.5))

    evidence = Evidence(
        type=EvidenceType(evidence_type),
        source_independent=source_independent,
        forced_value=forced_value,
        description=description,
    )
    posterior = compute_confidence_update(prior, evidence)

    patch = {
        **existing,
        "confidence": posterior,
        "confidence_updated_at": datetime.now(UTC).isoformat(),
    }
    record = MemoryRecord(**patch)
    await search.upsert(record)

    logger.info(
        "mma.confidence_updated",
        memory_id=memory_id,
        prior=round(prior, 3),
        posterior=round(posterior, 3),
    )
    return {"memory_id": memory_id, "prior": prior, "posterior": posterior}
