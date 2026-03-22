from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from dse.core.enums import CascadeStage
from dse.pipeline.retrieval import CascadeRetrieval
from dse.services.llm import LLMService

logger = structlog.get_logger(__name__)


@dataclass
class AgentState:
    """Represents the current state of an agent's execution."""

    namespace: str
    last_observation: str = ""
    task_description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    available_tokens: int = 16000


@dataclass
class ActionResult:
    """Result from an agent's action step."""

    action_id: str = ""
    content: str = ""
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class DSEMemoryMiddleware:
    """Memory-Augmented ReAct loop middleware.

    Automatically injects memory context before the Think step
    and stores important information after the Act step.
    """

    def __init__(
        self,
        retrieval: CascadeRetrieval,
        llm: LLMService,
    ) -> None:
        self._retrieval = retrieval
        self._llm = llm

    async def before_think(self, agent_state: AgentState) -> AgentState:
        """Before Think: retrieve relevant memories and inject into context."""
        if not agent_state.last_observation:
            return agent_state

        try:
            # Allocate 1/4 of available tokens to memory
            memory_budget = agent_state.available_tokens // 4

            context = await self._retrieval.retrieve(
                query=agent_state.last_observation,
                namespace=agent_state.namespace,
                token_budget=memory_budget,
                cascade_stage=CascadeStage.PRECISION,
                task_context=agent_state.task_description,
            )

            agent_state.context = {
                "memory_items": [
                    {
                        "id": item.memory_id,
                        "type": item.memory_type.value,
                        "content": item.content,
                        "confidence": item.confidence,
                    }
                    for item in context.items
                ],
                "memory_tokens": context.total_tokens,
            }

            logger.info(
                "middleware.context_injected",
                items=len(context.items),
                tokens=context.total_tokens,
            )
        except Exception:
            logger.warning("middleware.retrieval_failed", exc_info=True)
            agent_state.context = {}

        return agent_state

    async def after_act(
        self,
        agent_state: AgentState,
        action_result: ActionResult,
    ) -> None:
        """After Act: evaluate and store important results as memories."""
        if not action_result.content:
            return

        try:
            importance = await self._llm.assess_importance(
                action_result.content,
                context=agent_state.task_description,
            )

            score = float(importance.get("importance_score", 0.0))
            if score > 0.5:
                from dse.agents.mma.tools import store_memory_tool

                await store_memory_tool(
                    namespace=agent_state.namespace,
                    content_text=action_result.content,
                    memory_type=str(importance.get("memory_type", "episodic")),
                    confidence=score,
                    source_type="inference",
                    source_id=action_result.action_id,
                    tags=list(importance.get("entities", [])),
                )

                logger.info(
                    "middleware.memory_stored",
                    importance=score,
                    action_id=action_result.action_id,
                )
        except Exception:
            logger.warning("middleware.store_failed", exc_info=True)
