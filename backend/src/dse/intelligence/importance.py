from __future__ import annotations

from dataclasses import dataclass

import structlog

from dse.services.llm import LLMService

logger = structlog.get_logger(__name__)

# Signal weights — design ref: PROJECT.md Section 6.6
CONTENT_SIGNALS: dict[str, float] = {
    "contains_decision": 0.30,
    "contains_error_correction": 0.25,
    "contains_user_preference": 0.20,
    "contains_factual_claim": 0.15,
    "contains_deadline": 0.25,
}

BEHAVIOR_SIGNALS: dict[str, float] = {
    "user_explicitly_marked": 0.50,
    "agent_re_referenced": 0.10,
    "led_to_successful_action": 0.20,
    "led_to_failed_action": -0.10,
}

STRUCTURAL_SIGNALS: dict[str, float] = {
    "many_dependents_in_graph": 0.15,
    "unique_in_namespace": 0.10,
}

BASELINE = 0.5


@dataclass
class ImportanceContext:
    """Context for importance scoring."""

    user_explicitly_marked: bool = False
    agent_re_referenced_count: int = 0
    led_to_successful_action: bool = False
    led_to_failed_action: bool = False
    graph_dependent_count: int = 0
    similar_memory_count: int = 0
    utility_score: float | None = None


def _clamp(v: float) -> float:
    from dse.config import settings

    return max(settings.importance_score_min, min(settings.importance_score_max, v))


class ImportanceEstimator:
    """Evaluate memory importance from content, behavior, and structural signals.

    Design ref: PROJECT.md Section 6.6
    """

    def __init__(self, llm: LLMService | None = None) -> None:
        self._llm = llm

    async def estimate(
        self,
        memory_id: str,
        summary: str,
        memory_type: str,
        context: ImportanceContext,
    ) -> float:
        """Compute importance score (0.0-1.0)."""
        score = BASELINE

        # Content signals (LLM-detected)
        if self._llm and summary:
            content_flags = await self._detect_content_signals(summary)
            for signal, weight in CONTENT_SIGNALS.items():
                if content_flags.get(signal, False):
                    score += weight

        # Behavior signals
        if context.user_explicitly_marked:
            score += BEHAVIOR_SIGNALS["user_explicitly_marked"]
        if context.agent_re_referenced_count > 0:
            score += BEHAVIOR_SIGNALS["agent_re_referenced"] * min(
                context.agent_re_referenced_count, 5
            )
        if context.led_to_successful_action:
            score += BEHAVIOR_SIGNALS["led_to_successful_action"]
        if context.led_to_failed_action:
            score += BEHAVIOR_SIGNALS["led_to_failed_action"]

        # Structural signals
        if context.graph_dependent_count >= 3:
            score += STRUCTURAL_SIGNALS["many_dependents_in_graph"]
        if context.similar_memory_count == 0:
            score += STRUCTURAL_SIGNALS["unique_in_namespace"]

        # Procedural memories maintain minimum score
        if memory_type == "procedural":
            score = max(score, 0.60)

        final = _clamp(score)
        logger.info("importance.estimated", memory_id=memory_id, score=round(final, 3))
        return final

    async def reinforce(
        self,
        current_score: float,
        utility_score: float,
        accessor_type: str,
    ) -> float:
        """Reinforce importance based on access feedback.

        Design ref: PROJECT.md Section 7.2
        """
        recovery_rate = 0.15 if accessor_type == "user" else 0.05
        recovery = utility_score * recovery_rate
        return _clamp(current_score + recovery)

    async def _detect_content_signals(self, summary: str) -> dict[str, bool]:
        """Detect content signals via LLM."""
        assert self._llm is not None
        prompt = f"""以下のメモリサマリーから、該当するシグナルをすべて検出してください。

メモリ: {summary}

シグナル一覧（true/false で回答）:
- contains_decision: 意思決定・決定事項の記録か
- contains_error_correction: 誤りや修正の記録か
- contains_user_preference: ユーザーの嗜好・好みか
- contains_factual_claim: 検証可能な事実の主張か
- contains_deadline: 期限・締め切り・予定が含まれるか

必ず以下のJSONのみを返すこと:
{{"contains_decision": true|false, "contains_error_correction": true|false, "contains_user_preference": true|false, "contains_factual_claim": true|false, "contains_deadline": true|false}}"""
        try:
            return await self._llm.generate_json(prompt)  # type: ignore[return-value]
        except Exception:
            logger.warning("importance.content_signal_detection_failed")
            return {}
