from __future__ import annotations

import pytest

from dse.services.cache import MockWorkingMemoryService


@pytest.fixture
def wm() -> MockWorkingMemoryService:
    return MockWorkingMemoryService()


class TestSetGetContext:
    @pytest.mark.asyncio
    async def test_set_and_get(self, wm: MockWorkingMemoryService) -> None:
        await wm.set_context("s1", {"task": "test", "entities": ["A"]})
        ctx = await wm.get_context("s1")
        assert ctx == {"task": "test", "entities": ["A"]}

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, wm: MockWorkingMemoryService) -> None:
        ctx = await wm.get_context("nonexistent")
        assert ctx is None

    @pytest.mark.asyncio
    async def test_delete_context(self, wm: MockWorkingMemoryService) -> None:
        await wm.set_context("s1", {"key": "value"})
        await wm.delete_context("s1")
        assert await wm.get_context("s1") is None


class TestAppendGetTurns:
    @pytest.mark.asyncio
    async def test_append_and_get(self, wm: MockWorkingMemoryService) -> None:
        await wm.append_turn("s1", {"role": "user", "content": "hello"})
        await wm.append_turn("s1", {"role": "assistant", "content": "hi"})
        turns = await wm.get_recent_turns("s1", count=10)
        assert len(turns) == 2
        # Most recent first
        assert turns[0]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_maxlen_200(self, wm: MockWorkingMemoryService) -> None:
        for i in range(250):
            await wm.append_turn("s1", {"i": i})
        turns = await wm.get_recent_turns("s1", count=300)
        assert len(turns) <= 200


class TestSnapshotForPersistence:
    @pytest.mark.asyncio
    async def test_snapshot(self, wm: MockWorkingMemoryService) -> None:
        await wm.set_context("s1", {"task": "test"})
        await wm.append_turn("s1", {"role": "user", "content": "hello"})
        snapshot = await wm.snapshot_for_persistence("s1")
        assert snapshot["session_id"] == "s1"
        assert snapshot["context"] == {"task": "test"}
        assert len(snapshot["turns"]) == 1


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_deletes_all(self, wm: MockWorkingMemoryService) -> None:
        await wm.set_context("s1", {"key": "val"})
        await wm.append_turn("s1", {"role": "user", "content": "test"})
        await wm.delete_session("s1")
        assert await wm.get_context("s1") is None
        turns = await wm.get_recent_turns("s1")
        assert len(turns) == 0


class TestSearchCache:
    @pytest.mark.asyncio
    async def test_cache_and_get(self, wm: MockWorkingMemoryService) -> None:
        await wm.cache_search_result("hash1", [{"id": "m1"}])
        result = await wm.get_cached_search_result("hash1")
        assert result == [{"id": "m1"}]

    @pytest.mark.asyncio
    async def test_cache_miss(self, wm: MockWorkingMemoryService) -> None:
        assert await wm.get_cached_search_result("missing") is None


class TestEmbeddingCache:
    @pytest.mark.asyncio
    async def test_cache_and_get(self, wm: MockWorkingMemoryService) -> None:
        await wm.cache_embedding("hash1", [0.1, 0.2, 0.3])
        result = await wm.get_cached_embedding("hash1")
        assert result == [0.1, 0.2, 0.3]
