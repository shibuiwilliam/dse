from __future__ import annotations

import pytest

from dse.core.enums import RelationType
from dse.core.models import MemoryNode, RelationRecord
from dse.services.graph import MockGraphService


@pytest.fixture
def graph() -> MockGraphService:
    return MockGraphService()


class TestUpsertMemoryNode:
    @pytest.mark.asyncio
    async def test_create_node(self, graph: MockGraphService) -> None:
        node = MemoryNode(id="m1", namespace="test", memory_type="episodic")
        await graph.upsert_memory_node(node)
        result = await graph.get_memory_node("m1")
        assert result is not None
        assert result.id == "m1"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, graph: MockGraphService) -> None:
        node = MemoryNode(id="m1", namespace="test", confidence=0.5)
        await graph.upsert_memory_node(node)
        node.confidence = 0.9
        await graph.upsert_memory_node(node)
        result = await graph.get_memory_node("m1")
        assert result is not None
        assert result.confidence == 0.9


class TestCreateRelationAllTypes:
    @pytest.mark.asyncio
    async def test_all_8_edge_types(self, graph: MockGraphService) -> None:
        for i, rel_type in enumerate(RelationType):
            node_a = MemoryNode(id=f"a{i}", namespace="test")
            node_b = MemoryNode(id=f"b{i}", namespace="test")
            await graph.upsert_memory_node(node_a)
            await graph.upsert_memory_node(node_b)
            rel = RelationRecord(
                from_id=f"a{i}",
                to_id=f"b{i}",
                relation_type=rel_type,
                confidence=0.8,
            )
            await graph.create_relation(rel)
            assert await graph.relation_exists(f"a{i}", f"b{i}", rel_type)


class TestRelationExists:
    @pytest.mark.asyncio
    async def test_exists(self, graph: MockGraphService) -> None:
        for nid in ["x", "y"]:
            await graph.upsert_memory_node(MemoryNode(id=nid, namespace="test"))
        rel = RelationRecord(from_id="x", to_id="y", relation_type=RelationType.COMPLEMENTS)
        await graph.create_relation(rel)
        assert await graph.relation_exists("x", "y", RelationType.COMPLEMENTS)

    @pytest.mark.asyncio
    async def test_not_exists(self, graph: MockGraphService) -> None:
        assert not await graph.relation_exists("x", "y", RelationType.CONTRADICTS)


class TestGetNeighbors:
    @pytest.mark.asyncio
    async def test_returns_neighbors(self, graph: MockGraphService) -> None:
        for nid in ["a", "b", "c"]:
            await graph.upsert_memory_node(MemoryNode(id=nid, namespace="test"))
        await graph.create_relation(
            RelationRecord(from_id="a", to_id="b", relation_type=RelationType.COMPLEMENTS)
        )
        await graph.create_relation(
            RelationRecord(from_id="a", to_id="c", relation_type=RelationType.REFERENCES)
        )
        neighbors = await graph.get_neighbors("a")
        assert len(neighbors) == 2

    @pytest.mark.asyncio
    async def test_excludes_relation_types(self, graph: MockGraphService) -> None:
        for nid in ["a", "b"]:
            await graph.upsert_memory_node(MemoryNode(id=nid, namespace="test"))
        await graph.create_relation(
            RelationRecord(from_id="a", to_id="b", relation_type=RelationType.CONTRADICTS)
        )
        neighbors = await graph.get_neighbors(
            "a", exclude_relation_types=[RelationType.CONTRADICTS]
        )
        assert len(neighbors) == 0

    @pytest.mark.asyncio
    async def test_excludes_archived(self, graph: MockGraphService) -> None:
        await graph.upsert_memory_node(MemoryNode(id="a", namespace="test"))
        await graph.upsert_memory_node(MemoryNode(id="b", namespace="test", is_archived=True))
        await graph.create_relation(
            RelationRecord(from_id="a", to_id="b", relation_type=RelationType.COMPLEMENTS)
        )
        neighbors = await graph.get_neighbors("a")
        assert len(neighbors) == 0


class TestMarkArchived:
    @pytest.mark.asyncio
    async def test_marks_archived(self, graph: MockGraphService) -> None:
        await graph.upsert_memory_node(MemoryNode(id="a", namespace="test"))
        await graph.mark_archived("a")
        node = await graph.get_memory_node("a")
        assert node is not None
        assert node.is_archived is True


class TestGetContradictingPairs:
    @pytest.mark.asyncio
    async def test_returns_pairs(self, graph: MockGraphService) -> None:
        await graph.upsert_memory_node(MemoryNode(id="a", namespace="ns1"))
        await graph.upsert_memory_node(MemoryNode(id="b", namespace="ns1"))
        await graph.create_relation(
            RelationRecord(from_id="a", to_id="b", relation_type=RelationType.CONTRADICTS)
        )
        pairs = await graph.get_contradicting_pairs("ns1")
        assert len(pairs) == 1
        assert pairs[0]["id_a"] in ("a", "b")


class TestSubgraphVisualization:
    @pytest.mark.asyncio
    async def test_returns_nodes_and_edges(self, graph: MockGraphService) -> None:
        await graph.upsert_memory_node(MemoryNode(id="a", namespace="ns1"))
        await graph.upsert_memory_node(MemoryNode(id="b", namespace="ns1"))
        await graph.create_relation(
            RelationRecord(from_id="a", to_id="b", relation_type=RelationType.COMPLEMENTS)
        )
        result = await graph.get_subgraph_for_visualization("ns1")
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) >= 1
