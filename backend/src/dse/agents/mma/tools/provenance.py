from __future__ import annotations

from typing import Any

import structlog

from dse.api.deps import get_storage_service
from dse.core.models import ProvenanceEntry
from dse.infrastructure.provenance import ProvenanceService

logger = structlog.get_logger(__name__)


async def record_provenance_tool(
    memory_id: str,
    namespace: str,
    step: str,
    performed_by: str,
    description: str = "",
    model_used: str | None = None,
    input_memory_ids: list[str] | None = None,
) -> dict[str, Any]:
    """メモリの来歴（Provenance）にステップを記録する。

    Args:
        memory_id: 対象メモリのID
        namespace: メモリのNamespace
        step: ステップ名（"observation", "summarization", "inference"等）
        performed_by: 実行者（"agent:mma", "user:alice"等）
        description: ステップの説明
        model_used: 使用したモデル名（任意）
        input_memory_ids: 入力元のメモリIDリスト（任意）

    Returns:
        dict: status (str), memory_id (str)
    """
    storage = get_storage_service()
    prov = ProvenanceService(storage)

    entry = ProvenanceEntry(
        step=step,
        performed_by=performed_by,
        description=description,
        model_used=model_used,
        input_memory_ids=input_memory_ids or [],
    )

    await prov.record_transformation(memory_id, namespace, entry)
    logger.info("mma.provenance_recorded", memory_id=memory_id, step=step)
    return {"status": "recorded", "memory_id": memory_id, "step": step}
