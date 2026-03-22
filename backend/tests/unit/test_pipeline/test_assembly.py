from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dse.core.models import MemoryRecord, SearchResult
from dse.pipeline.assembly import ContextAssembler, estimate_tokens
from dse.services.storage import MockStorageService


def _make_result(
    id: str = "test",  # noqa: A002
    score: float = 0.9,
    summary: str = "Test memory summary",
    content_path: str = "",
) -> SearchResult:
    return SearchResult(
        record=MemoryRecord(
            id=id,
            namespace="test",
            summary=summary,
            content_path=content_path,
            confidence=0.8,
            created_at=datetime.now(UTC),
        ),
        score=score,
    )


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 1  # min 1

    def test_ascii(self) -> None:
        assert estimate_tokens("hello world") == 5

    def test_japanese(self) -> None:
        # Japanese: roughly 1 char = 0.5 tokens
        text = "これはテストです"
        tokens = estimate_tokens(text)
        assert tokens > 0


class TestContextAssembler:
    @pytest.fixture
    def assembler(self) -> ContextAssembler:
        return ContextAssembler(MockStorageService())

    @pytest.mark.asyncio
    async def test_empty_results(self, assembler: ContextAssembler) -> None:
        ctx = await assembler.assemble([], token_budget=1000)
        assert len(ctx.items) == 0
        assert ctx.total_tokens == 0

    @pytest.mark.asyncio
    async def test_summary_tier(self, assembler: ContextAssembler) -> None:
        results = [_make_result(score=0.5, summary="A short summary")]
        ctx = await assembler.assemble(results, token_budget=200)
        assert len(ctx.items) == 1
        assert ctx.items[0].tier == "summary"

    @pytest.mark.asyncio
    async def test_reference_tier_low_budget(self, assembler: ContextAssembler) -> None:
        results = [_make_result(score=0.5, summary="A summary")]
        ctx = await assembler.assemble(results, token_budget=30)
        assert len(ctx.items) == 1
        assert ctx.items[0].tier == "reference"

    @pytest.mark.asyncio
    async def test_respects_token_budget(self, assembler: ContextAssembler) -> None:
        results = [_make_result(id=f"m{i}", summary="x" * 200) for i in range(20)]
        ctx = await assembler.assemble(results, token_budget=100)
        assert ctx.total_tokens <= 100

    @pytest.mark.asyncio
    async def test_full_tier_with_storage(self) -> None:
        storage = MockStorageService()
        await storage.store_content("test", "m1", "Full content text here " * 10)
        assembler = ContextAssembler(storage)

        result = _make_result(
            id="m1",
            score=0.95,
            content_path="gs://mock-bucket/memories/test/m1.txt",
        )
        ctx = await assembler.assemble([result], token_budget=2000)
        assert len(ctx.items) == 1
        assert ctx.items[0].tier == "full"
        assert "Full content" in ctx.items[0].content
