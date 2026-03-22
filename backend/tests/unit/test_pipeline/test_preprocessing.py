from __future__ import annotations

import pytest

from dse.core.enums import CascadeStage
from dse.pipeline.preprocessing import QueryPreprocessor, SearchIntent
from dse.services.embedding import MockEmbeddingService
from dse.services.llm import MockLLMService


class TestSearchIntent:
    def test_default_values(self) -> None:
        intent = SearchIntent(primary_intent="test query")
        assert intent.urgency == "medium"
        assert intent.memory_types == []
        assert intent.entities == []
        assert intent.time_range is None


class TestQueryPreprocessor:
    @pytest.fixture
    def preprocessor(self) -> QueryPreprocessor:
        return QueryPreprocessor(
            llm=MockLLMService(),
            embedding=MockEmbeddingService(),
        )

    @pytest.mark.asyncio
    async def test_process_returns_search_query(
        self,
        preprocessor: QueryPreprocessor,
    ) -> None:
        query = await preprocessor.process("find Python memories")
        assert len(query.text_queries) >= 1
        assert len(query.embedding) == 3072
        assert query.cascade_stage == CascadeStage.PRECISION

    @pytest.mark.asyncio
    async def test_process_with_fast_stage(
        self,
        preprocessor: QueryPreprocessor,
    ) -> None:
        query = await preprocessor.process(
            "urgent query",
            cascade_stage=CascadeStage.FAST,
        )
        assert query.cascade_stage == CascadeStage.FAST

    @pytest.mark.asyncio
    async def test_process_with_namespace(
        self,
        preprocessor: QueryPreprocessor,
    ) -> None:
        query = await preprocessor.process(
            "test",
            namespace="agent:alice",
        )
        assert query.namespace == "agent:alice"

    @pytest.mark.asyncio
    async def test_creative_task_exploration_factor(
        self,
        preprocessor: QueryPreprocessor,
    ) -> None:
        query = await preprocessor.process(
            "brainstorm ideas",
            task_context="creative brainstorm session",
        )
        assert query.exploration_factor == 0.20

    @pytest.mark.asyncio
    async def test_debug_task_exploration_factor(
        self,
        preprocessor: QueryPreprocessor,
    ) -> None:
        query = await preprocessor.process(
            "find the error",
            task_context="debug this error in production",
        )
        assert query.exploration_factor == 0.02
