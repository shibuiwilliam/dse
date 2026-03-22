from __future__ import annotations

from google.adk.agents import Agent

from dse.agents.mma.prompts import MMA_SYSTEM_INSTRUCTION
from dse.agents.mma.tools import (
    classify_relation_tool,
    create_relation_tool,
    detect_contradiction_tool,
    record_provenance_tool,
    resolve_contradiction_tool,
    store_memory_tool,
    update_confidence_tool,
)
from dse.config import settings

memory_management_agent = Agent(
    model=settings.gemini_llm_model,
    name="memory_management_agent",
    description=(
        "DSEのメモリを管理するエージェント。"
        "新規メモリの登録、矛盾検出・解決、関係性分類、Confidence更新、"
        "Provenance記録を担当する。"
    ),
    instruction=MMA_SYSTEM_INSTRUCTION,
    tools=[
        store_memory_tool,
        detect_contradiction_tool,
        resolve_contradiction_tool,
        classify_relation_tool,
        create_relation_tool,
        update_confidence_tool,
        record_provenance_tool,
    ],
)
