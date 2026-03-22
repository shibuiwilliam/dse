from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncTransaction

from dse.config import settings
from dse.core.enums import RelationType
from dse.core.exceptions import GraphError
from dse.core.models import MemoryNode, RelationRecord

logger = structlog.get_logger(__name__)


class GraphService:
    """Neo4j graph DB client.

    All graph operations go through this class.
    Writes are always wrapped in transactions via ``_tx()``.
    """

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_pool_size=50,
            )
        return self._driver

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def _tx(self) -> AsyncIterator[AsyncTransaction]:
        """Transaction context manager — all writes must use this."""
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                await tx.commit()
            except Exception as e:
                await tx.rollback()
                raise GraphError(f"Transaction failed: {e}") from e

    # ── Node operations ──────────────────────────────────────────────

    async def upsert_memory_node(self, node: MemoryNode) -> None:
        """Create or update a Memory node."""
        cypher = """
        MERGE (m:Memory {id: $id})
        SET m.namespace           = $namespace,
            m.memory_type         = $memory_type,
            m.confidence          = $confidence,
            m.importance          = $importance,
            m.verification_status = $verification_status,
            m.is_archived         = $is_archived,
            m.created_at          = datetime($created_at),
            m.updated_at          = datetime($updated_at)
        """
        async with self._tx() as tx:
            await tx.run(cypher, **node.model_dump())

    async def get_memory_node(self, memory_id: str) -> MemoryNode | None:
        """Get a Memory node by ID."""
        cypher = "MATCH (m:Memory {id: $id}) RETURN m"
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(cypher, id=memory_id)
            record = await result.single()
            if record is None:
                return None
            return MemoryNode(**dict(record["m"]))

    async def mark_archived(self, memory_id: str) -> None:
        """Mark a Memory node as archived."""
        cypher = """
        MATCH (m:Memory {id: $id})
        SET m.is_archived = true, m.updated_at = datetime()
        """
        async with self._tx() as tx:
            await tx.run(cypher, id=memory_id)

    async def delete_node(self, memory_id: str) -> None:
        """Delete a Memory node and all its relationships."""
        cypher = "MATCH (m:Memory {id: $id}) DETACH DELETE m"
        async with self._tx() as tx:
            await tx.run(cypher, id=memory_id)
        logger.info("graph.node_deleted", memory_id=memory_id)

    async def register_node(self, record: Any) -> None:
        """Compat helper: accepts a MemoryRecord and upserts as MemoryNode."""
        node = MemoryNode(
            id=record.id,
            namespace=record.namespace,
            memory_type=record.memory_type.value
            if hasattr(record.memory_type, "value")
            else str(record.memory_type),
            confidence=record.confidence,
            importance=record.importance_score,
            verification_status=record.verification_status.value
            if hasattr(record.verification_status, "value")
            else str(record.verification_status),
            is_archived=record.is_archived,
            created_at=record.created_at.isoformat()
            if hasattr(record.created_at, "isoformat")
            else str(record.created_at),
            updated_at=record.updated_at.isoformat()
            if hasattr(record.updated_at, "isoformat")
            else str(record.updated_at),
        )
        await self.upsert_memory_node(node)

    # ── Edge operations ──────────────────────────────────────────────

    async def create_relation(self, relation: RelationRecord) -> None:
        """Create a relationship edge between two Memory nodes (MERGE)."""
        rel_type = relation.relation_type.value
        cypher = f"""
        MATCH (a:Memory {{id: $from_id}})
        MATCH (b:Memory {{id: $to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r.confidence = $confidence,
            r.strength   = $strength,
            r.created_at = datetime($created_at),
            r.created_by = $created_by,
            r.method     = $method
        """
        async with self._tx() as tx:
            await tx.run(
                cypher,
                from_id=relation.from_id,
                to_id=relation.to_id,
                confidence=relation.confidence,
                strength=relation.strength,
                created_at=relation.created_at,
                created_by=relation.created_by,
                method=relation.method,
            )
        logger.info(
            "graph.relation_created",
            from_id=relation.from_id,
            to_id=relation.to_id,
            rel_type=rel_type,
        )

    async def relation_exists(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
    ) -> bool:
        """Check if a directed edge of the given type exists."""
        rel_type = relation_type.value
        cypher = f"""
        MATCH (a:Memory {{id: $from_id}})-[r:{rel_type}]->(b:Memory {{id: $to_id}})
        RETURN count(r) > 0 AS exists
        """
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(cypher, from_id=from_id, to_id=to_id)
            record = await result.single()
            return bool(record["exists"]) if record else False

    async def any_relation_exists(self, id_a: str, id_b: str) -> bool:
        """Check if ANY edge exists between two nodes (either direction)."""
        cypher = """
        MATCH (a:Memory {id: $id_a})-[r]-(b:Memory {id: $id_b})
        RETURN count(r) > 0 AS exists
        """
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(cypher, id_a=id_a, id_b=id_b)
            record = await result.single()
            return bool(record["exists"]) if record else False

    async def create_relation_if_not_exists(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Create edge only if no edge of that type exists. Returns True if created."""
        if await self.relation_exists(from_id, to_id, relation_type):
            return False
        props = properties or {}
        rel = RelationRecord(
            from_id=from_id,
            to_id=to_id,
            relation_type=relation_type,
            confidence=float(props.get("confidence", 0.5)),
            strength=float(props.get("strength", 0.5)),
            created_by=str(props.get("created_by", "system")),
            method=str(props.get("method", "")),
        )
        await self.create_relation(rel)
        return True

    # ── Queries ──────────────────────────────────────────────────────

    async def get_neighbors(
        self,
        memory_id: str,
        *,
        hop_depth: int = 1,
        exclude_relation_types: list[RelationType] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get neighboring memories via graph traversal."""
        exclude_types = exclude_relation_types or []
        where_clauses = ["neighbor.id <> $id", "neighbor.is_archived = false"]
        if exclude_types:
            types_str = "', '".join(t.value for t in exclude_types)
            where_clauses.append(f"NOT type(r) IN ['{types_str}']")
        where_clause = " AND ".join(where_clauses)

        cypher = f"""
        MATCH (m:Memory {{id: $id}})
        MATCH (m)-[r]-(neighbor:Memory)
        WHERE {where_clause}
        RETURN DISTINCT neighbor.id AS id,
               neighbor.memory_type AS memory_type,
               neighbor.confidence AS confidence,
               type(r) AS relation_type,
               r.strength AS strength
        ORDER BY r.strength DESC
        LIMIT $limit
        """
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(cypher, id=memory_id, limit=limit)
            return [dict(record) async for record in result]

    async def get_contradicting_pairs(self, namespace: str) -> list[dict[str, Any]]:
        """Get all contradiction pairs in a namespace (for admin UI)."""
        cypher = """
        MATCH (a:Memory)-[r:CONTRADICTS]-(b:Memory)
        WHERE a.namespace = $namespace
          AND a.id < b.id
          AND a.is_archived = false
          AND b.is_archived = false
        RETURN a.id AS id_a,
               b.id AS id_b,
               a.confidence AS confidence_a,
               b.confidence AS confidence_b,
               toString(r.detected_at) AS detected_at,
               r.resolution_status AS resolution_status
        ORDER BY r.detected_at DESC
        """
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(cypher, namespace=namespace)
            return [dict(record) async for record in result]

    async def get_lineage(self, memory_id: str, max_depth: int = 5) -> list[dict[str, Any]]:
        """Trace DERIVES lineage of a memory."""
        cypher = """
        MATCH path = (root:Memory {id: $id})-[:DERIVES*0..5]->(leaf:Memory)
        RETURN [node IN nodes(path) | node.id] AS lineage_ids,
               length(path) AS depth
        ORDER BY depth
        LIMIT 20
        """
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(cypher, id=memory_id)
            return [dict(record) async for record in result]

    async def get_subgraph_for_visualization(
        self,
        namespace: str,
        *,
        limit_nodes: int = 200,
    ) -> dict[str, Any]:
        """Return nodes/edges for React Flow visualization.

        Strategy: find edges first (they're the interesting part), then collect
        the nodes on both ends. This ensures we only return connected nodes.
        """
        # Step 1: Get edges (limited to avoid overwhelming the UI)
        edge_cypher = """
        MATCH (a:Memory)-[r]->(b:Memory)
        WHERE a.namespace = $namespace AND b.namespace = $namespace
          AND a.is_archived = false AND b.is_archived = false
        RETURN startNode(r).id AS source,
               endNode(r).id AS target,
               type(r) AS relation_type,
               r.strength AS strength
        LIMIT $edge_limit
        """
        # Step 2: Get nodes that appear in those edges
        node_cypher = """
        MATCH (m:Memory)
        WHERE m.id IN $node_ids AND m.is_archived = false
        RETURN m.id AS id,
               m.memory_type AS memory_type,
               m.confidence AS confidence,
               toString(m.created_at) AS created_at
        """
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            # Fetch edges
            edge_result = await session.run(
                edge_cypher,
                namespace=namespace,
                edge_limit=limit_nodes * 5,  # Allow more edges than nodes
            )
            edges: list[dict[str, Any]] = []
            node_ids: set[str] = set()
            async for record in edge_result:
                src = record["source"]
                tgt = record["target"]
                if src and tgt:
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "relation_type": record["relation_type"],
                        "strength": record["strength"],
                    })
                    node_ids.add(src)
                    node_ids.add(tgt)

            if not node_ids:
                return {"nodes": [], "edges": []}

            # Limit node IDs to avoid huge queries
            node_id_list = list(node_ids)[:limit_nodes]

            # Fetch node details
            node_result = await session.run(node_cypher, node_ids=node_id_list)
            nodes: list[dict[str, Any]] = []
            async for record in node_result:
                nodes.append({
                    "id": record["id"],
                    "memory_type": record["memory_type"],
                    "confidence": record["confidence"],
                    "created_at": record["created_at"],
                })

            # Filter edges to only include those between returned nodes
            node_id_set = {n["id"] for n in nodes}
            filtered_edges = [
                e for e in edges
                if e["source"] in node_id_set and e["target"] in node_id_set
            ]

            return {"nodes": nodes, "edges": filtered_edges}

    async def delete_by_namespace(self, namespace: str) -> int:
        """Delete all Memory nodes in a namespace and their relationships."""
        cypher = """
        MATCH (m:Memory {namespace: $namespace})
        DETACH DELETE m
        RETURN count(m) AS deleted
        """
        async with self._tx() as tx:
            result = await tx.run(cypher, namespace=namespace)
            record = await result.single()
            deleted = record["deleted"] if record else 0
        logger.info("graph.namespace_deleted", namespace=namespace, deleted=deleted)
        return deleted

    async def init_schema(self) -> None:
        """Initialize Neo4j constraints and indexes."""
        driver = await self._get_driver()
        statements = [
            "CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT conflict_id_unique IF NOT EXISTS FOR (c:ConflictRecord) REQUIRE c.id IS UNIQUE",
            "CREATE INDEX memory_namespace IF NOT EXISTS FOR (m:Memory) ON (m.namespace)",
            "CREATE INDEX memory_type_idx IF NOT EXISTS FOR (m:Memory) ON (m.memory_type)",
            "CREATE INDEX memory_created_at IF NOT EXISTS FOR (m:Memory) ON (m.created_at)",
            "CREATE INDEX memory_confidence IF NOT EXISTS FOR (m:Memory) ON (m.confidence)",
            "CREATE INDEX memory_is_archived IF NOT EXISTS FOR (m:Memory) ON (m.is_archived)",
            "CREATE INDEX memory_verification_status IF NOT EXISTS FOR (m:Memory) ON (m.verification_status)",
        ]
        async with driver.session(database=settings.neo4j_database) as session:
            for stmt in statements:
                await session.run(stmt)
        logger.info("graph.schema_initialized")


class MockGraphService(GraphService):
    """In-memory mock for unit tests."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[RelationRecord] = []

    async def close(self) -> None:
        pass

    async def upsert_memory_node(self, node: MemoryNode) -> None:
        self._nodes[node.id] = node.model_dump()

    async def get_memory_node(self, memory_id: str) -> MemoryNode | None:
        data = self._nodes.get(memory_id)
        return MemoryNode(**data) if data else None

    async def mark_archived(self, memory_id: str) -> None:
        if memory_id in self._nodes:
            self._nodes[memory_id]["is_archived"] = True

    async def delete_node(self, memory_id: str) -> None:
        self._nodes.pop(memory_id, None)
        self._edges = [e for e in self._edges if e.from_id != memory_id and e.to_id != memory_id]

    async def create_relation(self, relation: RelationRecord) -> None:
        self._edges.append(relation)

    async def relation_exists(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
    ) -> bool:
        return any(
            e.from_id == from_id and e.to_id == to_id and e.relation_type == relation_type
            for e in self._edges
        )

    async def any_relation_exists(self, id_a: str, id_b: str) -> bool:
        return any(
            (e.from_id == id_a and e.to_id == id_b) or (e.from_id == id_b and e.to_id == id_a)
            for e in self._edges
        )

    async def create_relation_if_not_exists(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        if await self.relation_exists(from_id, to_id, relation_type):
            return False
        props = properties or {}
        rel = RelationRecord(
            from_id=from_id,
            to_id=to_id,
            relation_type=relation_type,
            confidence=float(props.get("confidence", 0.5)),
            created_by=str(props.get("created_by", "system")),
            method=str(props.get("method", "")),
        )
        self._edges.append(rel)
        return True

    async def get_neighbors(
        self,
        memory_id: str,
        *,
        hop_depth: int = 1,
        exclude_relation_types: list[RelationType] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        exclude = set(exclude_relation_types or [])
        neighbors: list[dict[str, Any]] = []
        for edge in self._edges:
            if edge.relation_type in exclude:
                continue
            other_id = None
            if edge.from_id == memory_id:
                other_id = edge.to_id
            elif edge.to_id == memory_id:
                other_id = edge.from_id
            if other_id and other_id in self._nodes:
                node = self._nodes[other_id]
                if not node.get("is_archived", False):
                    neighbors.append(
                        {
                            "id": other_id,
                            "memory_type": node.get("memory_type", "episodic"),
                            "confidence": node.get("confidence", 0.5),
                            "relation_type": edge.relation_type.value,
                            "strength": edge.strength,
                        }
                    )
        return neighbors[:limit]

    async def get_contradicting_pairs(self, namespace: str) -> list[dict[str, Any]]:
        pairs: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for edge in self._edges:
            if edge.relation_type == RelationType.CONTRADICTS:
                pair_key = tuple(sorted([edge.from_id, edge.to_id]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                a = self._nodes.get(edge.from_id, {})
                b = self._nodes.get(edge.to_id, {})
                if a.get("namespace") == namespace:
                    pairs.append(
                        {
                            "id_a": edge.from_id,
                            "id_b": edge.to_id,
                            "confidence_a": a.get("confidence", 0.5),
                            "confidence_b": b.get("confidence", 0.5),
                            "detected_at": edge.created_at,
                            "resolution_status": "pending",
                        }
                    )
        return pairs

    async def get_lineage(self, memory_id: str, max_depth: int = 5) -> list[dict[str, Any]]:
        return []

    async def get_subgraph_for_visualization(
        self,
        namespace: str,
        *,
        limit_nodes: int = 100,
    ) -> dict[str, Any]:
        nodes = [
            {"id": nid, "memory_type": n.get("memory_type"), "confidence": n.get("confidence")}
            for nid, n in self._nodes.items()
            if n.get("namespace") == namespace and not n.get("is_archived")
        ][:limit_nodes]
        edges = [
            {
                "source": e.from_id,
                "target": e.to_id,
                "relation_type": e.relation_type.value,
                "strength": e.strength,
            }
            for e in self._edges
        ]
        return {"nodes": nodes, "edges": edges}

    async def delete_by_namespace(self, namespace: str) -> int:
        to_delete = [nid for nid, n in self._nodes.items() if n.get("namespace") == namespace]
        for nid in to_delete:
            self._nodes.pop(nid, None)
        self._edges = [
            e for e in self._edges if e.from_id not in to_delete and e.to_id not in to_delete
        ]
        return len(to_delete)

    async def init_schema(self) -> None:
        pass
