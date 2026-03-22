from __future__ import annotations

from google.adk.agents import Agent

from dse.agents.retrieval.tools import retrieve_memory_tool
from dse.config import settings

RETRIEVAL_INSTRUCTION = """あなたはDSEの検索エージェントです。
ユーザーやタスクエージェントからのクエリに基づいて、適切なメモリを検索し、
コンテキストとして提供します。

## 検索戦略
- 急ぎのタスク → cascade_stage="fast"（キャッシュ＋ANN）
- 通常のタスク → cascade_stage="precision"（ハイブリッド検索＋再ランク）
- 深い推論が必要 → cascade_stage="deep"（グラフ探索＋LLMスコアリング）

## トークン予算
token_budgetパラメータで取得するコンテキストの量を制御します。
- 小規模な質問: 1000-2000トークン
- 中規模なタスク: 2000-4000トークン
- 大規模な分析: 4000-8000トークン
"""

retrieval_agent = Agent(
    model=settings.gemini_llm_model,
    name="retrieval_agent",
    description="DSEのメモリ検索エージェント。クエリに基づいてメモリコンテキストを取得する。",
    instruction=RETRIEVAL_INSTRUCTION,
    tools=[retrieve_memory_tool],
)
