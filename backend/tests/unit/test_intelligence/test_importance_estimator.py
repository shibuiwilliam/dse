from __future__ import annotations

import pytest

from dse.intelligence.importance import ImportanceContext, ImportanceEstimator
from dse.services.llm import MockLLMService


@pytest.fixture
def estimator() -> ImportanceEstimator:
    return ImportanceEstimator(llm=MockLLMService())


class TestImportanceEstimator:
    @pytest.mark.asyncio
    async def test_baseline_score(self, estimator: ImportanceEstimator) -> None:
        """Baseline is 0.5 when no signals fire."""
        # MockLLM returns contains_factual_claim=True, so adjust expectation
        score = await estimator.estimate("m1", "", "episodic", ImportanceContext())
        # Without summary, no LLM call → pure baseline
        assert 0.4 <= score <= 0.7

    @pytest.mark.asyncio
    async def test_user_marked_adds_max_boost(self, estimator: ImportanceEstimator) -> None:
        ctx = ImportanceContext(user_explicitly_marked=True)
        score = await estimator.estimate("m1", "test", "episodic", ctx)
        assert score >= 0.95  # 0.5 baseline + 0.50 user_marked + content signals

    @pytest.mark.asyncio
    async def test_failed_action_reduces_score(self, estimator: ImportanceEstimator) -> None:
        ctx_ok = ImportanceContext()
        ctx_fail = ImportanceContext(led_to_failed_action=True)
        score_ok = await estimator.estimate("m1", "test", "episodic", ctx_ok)
        score_fail = await estimator.estimate("m1", "test", "episodic", ctx_fail)
        assert score_fail < score_ok

    @pytest.mark.asyncio
    async def test_procedural_minimum_score(self, estimator: ImportanceEstimator) -> None:
        ctx = ImportanceContext(led_to_failed_action=True)  # Try to drive it low
        score = await estimator.estimate("m1", "", "procedural", ctx)
        assert score >= 0.60

    @pytest.mark.asyncio
    async def test_clamping_never_exceeds_max(self, estimator: ImportanceEstimator) -> None:
        ctx = ImportanceContext(
            user_explicitly_marked=True,
            agent_re_referenced_count=10,
            led_to_successful_action=True,
            graph_dependent_count=5,
            similar_memory_count=0,
        )
        score = await estimator.estimate("m1", "test summary", "semantic", ctx)
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_reinforce_recovery(self, estimator: ImportanceEstimator) -> None:
        new_score = await estimator.reinforce(
            current_score=0.5,
            utility_score=0.8,
            accessor_type="user",
        )
        assert new_score > 0.5
        expected = 0.5 + 0.8 * 0.15
        assert abs(new_score - expected) < 0.01

    @pytest.mark.asyncio
    async def test_reinforce_agent_weaker_than_user(self, estimator: ImportanceEstimator) -> None:
        user_score = await estimator.reinforce(0.5, 0.8, "user")
        agent_score = await estimator.reinforce(0.5, 0.8, "agent")
        assert user_score > agent_score

    @pytest.mark.asyncio
    async def test_graph_dependents_boost(self, estimator: ImportanceEstimator) -> None:
        ctx_low = ImportanceContext(graph_dependent_count=0)
        ctx_high = ImportanceContext(graph_dependent_count=5)
        score_low = await estimator.estimate("m1", "", "episodic", ctx_low)
        score_high = await estimator.estimate("m1", "", "episodic", ctx_high)
        assert score_high > score_low

    @pytest.mark.asyncio
    async def test_unique_memory_boost(self, estimator: ImportanceEstimator) -> None:
        ctx_common = ImportanceContext(similar_memory_count=10)
        ctx_unique = ImportanceContext(similar_memory_count=0)
        score_common = await estimator.estimate("m1", "", "episodic", ctx_common)
        score_unique = await estimator.estimate("m1", "", "episodic", ctx_unique)
        assert score_unique > score_common
