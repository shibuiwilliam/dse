"""Unit tests for the DSE MCP server tools."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from dse.services.cache import MockCacheService
from dse.services.embedding import MockEmbeddingService
from dse.services.graph import MockGraphService
from dse.services.llm import MockLLMService
from dse.services.search import MockSearchService


@pytest.fixture(autouse=True)
def _mock_deps() -> None:
    """Patch deps to return fresh mock services for each test."""
    search = MockSearchService()
    graph = MockGraphService()
    cache = MockCacheService()
    embedding = MockEmbeddingService()
    llm = MockLLMService()

    with (
        patch("dse.mcp.server.get_search_service", return_value=search),
        patch("dse.mcp.server.get_graph_service", return_value=graph),
        patch("dse.mcp.server.get_cache_service", return_value=cache),
        patch("dse.mcp.server.get_embedding_service", return_value=embedding),
        patch("dse.mcp.server.get_llm_service", return_value=llm),
    ):
        yield


class TestStoreMemory:
    async def test_store_returns_id_and_metadata(self) -> None:
        from dse.mcp.server import store_memory

        result = json.loads(
            await store_memory(
                namespace="agent:test",
                content_text="The capital of France is Paris.",
                summary="France capital",
                memory_type="semantic",
                tags=["geography"],
            )
        )

        assert "id" in result
        assert result["namespace"] == "agent:test"
        assert result["summary"] == "France capital"
        assert result["memory_type"] == "semantic"
        assert 0.0 <= result["confidence"] <= 1.0

    async def test_store_auto_generates_summary_from_content(self) -> None:
        from dse.mcp.server import store_memory

        result = json.loads(
            await store_memory(
                namespace="agent:test",
                content_text="Short note",
            )
        )

        assert result["summary"] == "Short note"

    async def test_store_infers_tags_and_entities_when_omitted(self) -> None:
        from dse.mcp.server import store_memory

        result = json.loads(
            await store_memory(
                namespace="agent:test",
                content_text="PyTorch outperforms TensorFlow on this benchmark.",
            )
        )

        # MockLLMService.enrich_memory extracts capitalized words as entities
        assert "tags" in result
        assert isinstance(result["tags"], list)
        assert len(result["tags"]) > 0
        assert "entities" in result
        assert isinstance(result["entities"], list)
        assert "importance_score" in result

    async def test_store_preserves_explicit_tags_and_entities(self) -> None:
        from dse.mcp.server import store_memory

        result = json.loads(
            await store_memory(
                namespace="agent:test",
                content_text="Some content",
                tags=["my-tag"],
                entities=["MyEntity"],
            )
        )

        # Explicit values should NOT be overwritten by LLM
        assert result["tags"] == ["my-tag"]
        assert result["entities"] == ["MyEntity"]

    async def test_store_clamps_confidence(self) -> None:
        from dse.mcp.server import store_memory

        result = json.loads(
            await store_memory(
                namespace="agent:test",
                content_text="Test",
                confidence=2.0,
            )
        )

        assert result["confidence"] == 1.0


class TestGetMemory:
    async def test_get_existing_memory(self) -> None:
        from dse.mcp.server import get_memory, store_memory

        stored = json.loads(await store_memory(namespace="agent:test", content_text="Hello world"))
        memory_id = stored["id"]

        result = json.loads(await get_memory(memory_id))

        assert result["id"] == memory_id
        assert result["namespace"] == "agent:test"
        assert "Hello world" in result["content_text"]

    async def test_get_nonexistent_memory(self) -> None:
        from dse.mcp.server import get_memory

        result = json.loads(await get_memory("nonexistent-id"))

        assert "error" in result


class TestUpdateMemory:
    async def test_update_fields(self) -> None:
        from dse.mcp.server import get_memory, store_memory, update_memory

        stored = json.loads(await store_memory(namespace="agent:test", content_text="Original"))
        memory_id = stored["id"]

        update_result = json.loads(
            await update_memory(
                memory_id=memory_id,
                summary="Updated summary",
                tags=["updated"],
            )
        )

        assert update_result["memory_id"] == memory_id
        assert "summary" in update_result["updated_fields"]
        assert "tags" in update_result["updated_fields"]

        # Verify the update persisted
        fetched = json.loads(await get_memory(memory_id))
        assert fetched["summary"] == "Updated summary"
        assert fetched["tags"] == ["updated"]

    async def test_update_nonexistent_memory(self) -> None:
        from dse.mcp.server import update_memory

        result = json.loads(await update_memory(memory_id="nonexistent", summary="test"))

        assert "error" in result


class TestDeleteMemory:
    async def test_delete_memory(self) -> None:
        from dse.mcp.server import delete_memory, get_memory, store_memory

        stored = json.loads(
            await store_memory(namespace="agent:test", content_text="To be deleted")
        )
        memory_id = stored["id"]

        result = json.loads(await delete_memory(memory_id))

        assert result["deleted"] is True
        assert result["memory_id"] == memory_id

        # Verify it's gone
        fetched = json.loads(await get_memory(memory_id))
        assert "error" in fetched


class TestSearchMemories:
    async def test_search_finds_stored_memory(self) -> None:
        from dse.mcp.server import search_memories, store_memory

        await store_memory(
            namespace="agent:test",
            content_text="Elasticsearch is a search engine",
            tags=["tech"],
        )

        results = json.loads(await search_memories(query="search engine", namespace="agent:test"))

        assert len(results) > 0
        assert any("search engine" in r["content_text"].lower() for r in results)

    async def test_search_empty_results(self) -> None:
        from dse.mcp.server import search_memories

        results = json.loads(await search_memories(query="nonexistent query xyz"))

        assert isinstance(results, list)


class TestRetrieveMemories:
    async def test_retrieve_returns_structured_result(self) -> None:
        from dse.mcp.server import retrieve_memories, store_memory

        await store_memory(
            namespace="agent:test",
            content_text="Python is a programming language",
        )

        result = json.loads(
            await retrieve_memories(
                query="programming language",
                namespace="agent:test",
            )
        )

        assert "items" in result
        assert "total_tokens" in result
        assert "query" in result


class TestGetRelatedMemories:
    async def test_get_related_empty_graph(self) -> None:
        from dse.mcp.server import get_related_memories

        result = json.loads(await get_related_memories(memory_id="some-id"))

        assert result["memory_id"] == "some-id"
        assert isinstance(result["neighbors"], list)


class TestCreateMemoryRelation:
    async def test_create_relation(self) -> None:
        from dse.mcp.server import create_memory_relation, store_memory

        a = json.loads(await store_memory(namespace="agent:test", content_text="Fact A"))
        b = json.loads(await store_memory(namespace="agent:test", content_text="Fact B"))

        result = json.loads(
            await create_memory_relation(
                from_id=a["id"],
                to_id=b["id"],
                relation_type="COMPLEMENTS",
                confidence=0.8,
            )
        )

        assert result["created"] is True
        assert result["relation_type"] == "COMPLEMENTS"


class TestNamespaceManagement:
    async def test_list_namespaces_empty(self) -> None:
        from dse.mcp.server import list_namespaces

        result = json.loads(await list_namespaces())
        assert isinstance(result, list)

    async def test_create_and_list_namespace(self) -> None:
        from dse.mcp.server import create_namespace, list_namespaces

        create_result = json.loads(await create_namespace(namespace="agent:mcp-test"))
        assert create_result["status"] == "created"
        assert create_result["namespace"] == "agent:mcp-test"

        ns_list = json.loads(await list_namespaces())
        assert "agent:mcp-test" in ns_list

    async def test_create_duplicate_namespace(self) -> None:
        from dse.mcp.server import create_namespace

        await create_namespace(namespace="agent:dup")
        result = json.loads(await create_namespace(namespace="agent:dup"))
        assert "error" in result

    async def test_get_namespace(self) -> None:
        from dse.mcp.server import get_namespace, store_memory

        await store_memory(namespace="agent:stats-test", content_text="Hello")
        result = json.loads(await get_namespace(namespace="agent:stats-test"))
        assert result["namespace"] == "agent:stats-test"
        assert result["total_memories"] >= 1

    async def test_get_nonexistent_namespace(self) -> None:
        from dse.mcp.server import get_namespace

        result = json.loads(await get_namespace(namespace="nope:none"))
        assert "error" in result

    async def test_delete_namespace(self) -> None:
        from dse.mcp.server import delete_namespace, list_namespaces, store_memory

        await store_memory(namespace="agent:to-delete", content_text="Goodbye")
        result = json.loads(await delete_namespace(namespace="agent:to-delete"))
        assert result["status"] == "deleted"
        assert result["search_deleted"] >= 1

        ns_list = json.loads(await list_namespaces())
        assert "agent:to-delete" not in ns_list

    async def test_delete_nonexistent_namespace(self) -> None:
        from dse.mcp.server import delete_namespace

        result = json.loads(await delete_namespace(namespace="nope:none"))
        assert "error" in result


class TestWorkingMemory:
    async def test_add_and_get_turns(self) -> None:
        from dse.mcp.server import working_memory_add, working_memory_get

        add_result = json.loads(
            await working_memory_add(
                session_id="sess-1",
                content="Hello",
                role="user",
            )
        )

        assert add_result["added"] is True
        assert add_result["session_id"] == "sess-1"

        entries = json.loads(await working_memory_get(session_id="sess-1"))

        assert isinstance(entries, list)
