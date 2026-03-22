from __future__ import annotations

from typing import Any

import structlog

from dse.api.deps import get_llm_service, get_search_service
from dse.core.models import MemoryRecord
from dse.intelligence.importance import ImportanceContext, ImportanceEstimator

logger = structlog.get_logger(__name__)


async def estimate_importance_tool(
    memory_id: str,
    user_explicitly_marked: bool = False,
    agent_re_referenced_count: int = 0,
    led_to_successful_action: bool = False,
    led_to_failed_action: bool = False,
    graph_dependent_count: int = 0,
    similar_memory_count: int = 0,
) -> dict[str, Any]:
    """メモリの重要度を文脈に応じて評価する。

    Args:
        memory_id: 対象メモリID
        user_explicitly_marked: ユーザーが重要とマークしたか
        agent_re_referenced_count: エージェントの再参照回数
        led_to_successful_action: 成功アクションに貢献したか
        led_to_failed_action: 失敗アクションに使用されたか
        graph_dependent_count: グラフ上の依存メモリ数
        similar_memory_count: 類似メモリ数

    Returns:
        dict: memory_id, score を含む結果
    """
    search = get_search_service()
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        return {"error": f"Memory not found: {memory_id}"}

    record = results[0]
    ctx = ImportanceContext(
        user_explicitly_marked=user_explicitly_marked,
        agent_re_referenced_count=agent_re_referenced_count,
        led_to_successful_action=led_to_successful_action,
        led_to_failed_action=led_to_failed_action,
        graph_dependent_count=graph_dependent_count,
        similar_memory_count=similar_memory_count,
    )

    estimator = ImportanceEstimator(llm=get_llm_service())
    score = await estimator.estimate(
        memory_id=memory_id,
        summary=str(record.get("summary", "")),
        memory_type=str(record.get("memory_type", "episodic")),
        context=ctx,
    )

    updated = MemoryRecord(**{**record, "importance_score": score})
    await search.upsert(updated)
    return {"memory_id": memory_id, "importance_score": score}


async def reinforce_memory_tool(
    memory_id: str,
    utility_score: float,
    accessor_type: str = "agent",
) -> dict[str, Any]:
    """メモリの重要度とDecayをアクセスフィードバックで強化する。

    Args:
        memory_id: 対象メモリID
        utility_score: フィードバックの有用度（0.0〜1.0）
        accessor_type: アクセス者タイプ（"user" or "agent"）

    Returns:
        dict: memory_id, importance_score を含む結果
    """
    search = get_search_service()
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        return {"error": f"Memory not found: {memory_id}"}

    estimator = ImportanceEstimator()
    new_importance = await estimator.reinforce(
        current_score=float(results[0].get("importance_score", 0.5)),
        utility_score=utility_score,
        accessor_type=accessor_type,
    )
    return {"memory_id": memory_id, "importance_score": new_importance}
