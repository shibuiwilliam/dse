from __future__ import annotations

import pytest

from dse.core.enums import RelationType
from dse.core.exceptions import StorageError
from dse.core.models import MemoryNode, MemoryRecord, RelationRecord
from dse.services.cache import MockWorkingMemoryService
from dse.services.embedding import MockEmbeddingService
from dse.services.graph import MockGraphService
from dse.services.llm import MockLLMService
from dse.services.search import MockSearchService
from dse.services.storage import MockStorageService


class TestMockSearchService:
    @pytest.mark.asyncio
    async def test_upsert_and_search(self) -> None:
        service = MockSearchService()
        record = MemoryRecord(
            namespace="test",
            content_text="Python is a programming language",
            summary="Python language",
        )
        await service.upsert(record)

        results = await service.search("Python", namespace="test")
        assert len(results) == 1
        assert results[0]["id"] == record.id

    @pytest.mark.asyncio
    async def test_search_filters_namespace(self) -> None:
        service = MockSearchService()
        r1 = MemoryRecord(namespace="ns1", content_text="hello", summary="hello")
        r2 = MemoryRecord(namespace="ns2", content_text="hello", summary="hello")
        await service.upsert(r1)
        await service.upsert(r2)

        results = await service.search("hello", namespace="ns1")
        assert len(results) == 1
        assert results[0]["namespace"] == "ns1"

    @pytest.mark.asyncio
    async def test_search_filters_archived(self) -> None:
        service = MockSearchService()
        record = MemoryRecord(
            namespace="test",
            content_text="archived content",
            summary="archived",
            is_archived=True,
        )
        await service.upsert(record)

        results = await service.search("archived", namespace="test")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        service = MockSearchService()
        record = MemoryRecord(namespace="test", content_text="to delete", summary="delete")
        await service.upsert(record)
        await service.delete(record.id)

        results = await service.search("delete", namespace="test")
        assert len(results) == 0


class TestMockStorageService:
    @pytest.mark.asyncio
    async def test_store_and_fetch(self) -> None:
        service = MockStorageService()
        path = await service.store_content("ns", "id1", "Hello content")
        content = await service.fetch_content(path)
        assert content == "Hello content"

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        service = MockStorageService()
        await service.store_content("ns", "id1", "content")
        await service.delete_content("ns", "id1")
        with pytest.raises(StorageError):
            await service.fetch_content("gs://mock-bucket/memories/ns/id1.txt")


class TestMockGraphService:
    @pytest.mark.asyncio
    async def test_upsert_and_get_neighbors(self) -> None:
        service = MockGraphService()
        a = MemoryNode(id="a", namespace="test")
        b = MemoryNode(id="b", namespace="test")
        await service.upsert_memory_node(a)
        await service.upsert_memory_node(b)
        await service.create_relation(
            RelationRecord(from_id="a", to_id="b", relation_type=RelationType.COMPLEMENTS)
        )
        neighbors = await service.get_neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0]["id"] == "b"

    @pytest.mark.asyncio
    async def test_excludes_contradictions(self) -> None:
        service = MockGraphService()
        a = MemoryNode(id="a", namespace="test")
        b = MemoryNode(id="b", namespace="test")
        await service.upsert_memory_node(a)
        await service.upsert_memory_node(b)
        await service.create_relation(
            RelationRecord(from_id="a", to_id="b", relation_type=RelationType.CONTRADICTS)
        )
        neighbors = await service.get_neighbors(
            "a", exclude_relation_types=[RelationType.CONTRADICTS]
        )
        assert len(neighbors) == 0

    @pytest.mark.asyncio
    async def test_register_node_compat(self) -> None:
        """Test the register_node compatibility helper."""
        service = MockGraphService()
        record = MemoryRecord(id="m1", namespace="test")
        await service.register_node(record)
        node = await service.get_memory_node("m1")
        assert node is not None
        assert node.id == "m1"


class TestMockWorkingMemoryService:
    @pytest.mark.asyncio
    async def test_session_context(self) -> None:
        service = MockWorkingMemoryService()
        await service.set_context("s1", {"key": "value"})
        ctx = await service.get_context("s1")
        assert ctx == {"key": "value"}

    @pytest.mark.asyncio
    async def test_append_and_get_turns(self) -> None:
        service = MockWorkingMemoryService()
        await service.append_turn("s1", {"role": "user", "content": "hi"})
        turns = await service.get_recent_turns("s1")
        assert len(turns) == 1

    @pytest.mark.asyncio
    async def test_delete_session(self) -> None:
        service = MockWorkingMemoryService()
        await service.set_context("s1", {"key": "val"})
        await service.delete_session("s1")
        assert await service.get_context("s1") is None


class TestMockEmbeddingService:
    @pytest.mark.asyncio
    async def test_encode_deterministic(self) -> None:
        service = MockEmbeddingService()
        v1 = await service.encode("hello")
        v2 = await service.encode("hello")
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_encode_different_for_different_text(self) -> None:
        service = MockEmbeddingService()
        v1 = await service.encode("hello")
        v2 = await service.encode("world")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_encode_returns_correct_dims(self) -> None:
        service = MockEmbeddingService()
        v = await service.encode("test")
        assert len(v) == 3072


class TestMockLLMService:
    @pytest.mark.asyncio
    async def test_generate(self) -> None:
        service = MockLLMService()
        result = await service.generate("test prompt")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_classify_relation(self) -> None:
        service = MockLLMService()
        result = await service.classify_relation("A", "B")
        assert "type" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_assess_importance(self) -> None:
        service = MockLLMService()
        result = await service.assess_importance("test content")
        assert "importance_score" in result

    @pytest.mark.asyncio
    async def test_generate_summary(self) -> None:
        service = MockLLMService()
        text = "x" * 300
        summary = await service.generate_summary(text)
        assert len(summary) <= 150
