from __future__ import annotations

from typing import Any

import structlog

from dse.api.deps import get_retrieval_pipeline
from dse.core.enums import CascadeStage

logger = structlog.get_logger(__name__)


async def retrieve_memory_tool(
    query: str,
    namespace: str,
    token_budget: int = 4000,
    cascade_stage: str = "precision",
    task_context: str = "",
) -> dict[str, Any]:
    """エージェントのためにメモリコンテキストを取得する。

    Args:
        query: 検索クエリ（自然言語）
        namespace: メモリの検索スコープ
        token_budget: コンテキストのトークン上限
        cascade_stage: 検索の深さ ("fast", "precision", "deep")
        task_context: 現在のタスクの説明（検索品質の向上に使用）

    Returns:
        dict: items (list), total_tokens (int), query (str)
    """
    pipeline = get_retrieval_pipeline()

    context = await pipeline.retrieve(
        query=query,
        namespace=namespace,
        token_budget=token_budget,
        cascade_stage=CascadeStage(cascade_stage),
        task_context=task_context,
    )

    return {
        "items": [
            {
                "memory_id": item.memory_id,
                "memory_type": item.memory_type.value,
                "content": item.content,
                "tier": item.tier,
                "score": item.score,
                "confidence": item.confidence,
            }
            for item in context.items
        ],
        "total_tokens": context.total_tokens,
        "query": context.query,
    }
