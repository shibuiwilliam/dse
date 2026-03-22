# DSE — Phase 2: Graph & Quality Implementation Guide

> **Target Phase**: Phase 2: Graph & Quality
> **Prerequisite**: Phase 1 (Vertex AI Search basic search, GCS storage, FastAPI skeleton, basic MMA) must be complete
> **Design Reference**: `docs/DSE_Design_Report.md`

---

## How to Use This File

Claude Code must read this entire file before starting any task.
When unsure about implementation details, refer to the relevant section in the design reference before making decisions.
**Always follow this order: read the relevant section → implement → add tests.**

---

## Features to Implement in Phase 2

Phase 2 focuses on "memory quality, consistency, and provenance management". The following 7 features will be implemented.

| # | Feature | Priority | Dependencies |
|---|---------|----------|--------------|
| P2-1 | Neo4j Graph DB setup with 8 edge types | Highest | None |
| P2-2 | Contradiction detection with 3-stage resolution process | Highest | P2-1 |
| P2-3 | Confidence score + Bayesian updates | High | P2-1 |
| P2-4 | Working Memory Buffer (Redis Streams) | High | None |
| P2-5 | CDC pipeline (Redpanda → MMA) | Medium | P2-4 |
| P2-6 | Provenance Tracking (lineage recording) | High | P2-1 |
| P2-7 | Frontend: Graph visualization + Contradiction queue | Medium | P2-1 through P2-3 |

**Implementation order**: P2-1 → P2-4 → P2-6 → P2-3 → P2-2 → P2-5 → P2-7

---

## Critical Rules (Highest Priority)

1. **Read this file before starting implementation** — when in doubt, refer back to the design report
2. **Type annotations are mandatory** — include `from __future__ import annotations` at the top of every Python file
3. **Never merge code without tests** — add tests under `tests/` for each feature
4. **Never hardcode secrets in source code** — use `.env` exclusively
5. **All Neo4j writes must be done within a transaction** — use `async with session.begin_transaction()`
6. **Never call side-effect operations directly in Temporal Workflows** — always delegate to Activities
7. **All Gemini API calls must go through `services/llm.py`** — no direct calls allowed
8. **Maintain the ability to start all local services with `make dev`** — never leave docker-compose in a broken state

---

## Tech Stack (Phase 2 Additions)

### Cloud Services (Continued from Phase 1)

| Component | Service | Purpose |
|-----------|---------|---------|
| Search Engine | Vertex AI Search (Discovery Engine API) | Full-text, vector, and hybrid search for memories |
| LLM | Gemini 3.0 Flash (`gemini-3-flash-preview`) | MMA reasoning, contradiction detection, relation classification, importance evaluation |
| LLM (High Accuracy) | Gemini 3.1 Pro (future expansion) | Complex reasoning tasks |
| Embedding | `gemini-embedding-2-preview` | Text vectorization (3072 dimensions) |
| Object Storage | GCS / MinIO (local) | Memory content persistence |

### Local Services (Docker — Phase 2 Additions)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| Neo4j | `neo4j:5` + APOC plugin | 7474 / 7687 | Graph DB (relationship management) |
| Redis | `redis:8-alpine` | 6379 | Working Memory Buffer |
| Redpanda | `redpandadata/redpanda:latest` | 9092 / 9644 | Kafka-compatible CDC event bus |
| Redpanda Console | `redpandadata/console:latest` | 8085 | Redpanda monitoring UI |

### Additional Python Dependencies

```toml
# Append to pyproject.toml
[project.dependencies]
# Phase 2 additions
neo4j = ">=5.0"                    # Neo4j async driver
redis = {version = ">=5.0", extras = ["hiredis"]}  # Redis + high-performance parser
aiokafka = ">=0.10"                # Kafka/Redpanda async client
structlog = ">=24.0"               # Structured logging
ulid-py = ">=1.1"                  # ULID (time-sortable IDs)
```

### Additional Frontend Dependencies

```bash
pnpm add @xyflow/react        # React Flow — memory graph visualization
pnpm add @tanstack/react-table  # Table (conflict queue list)
pnpm add date-fns             # Date formatting
pnpm add zustand              # State management (existing)
```

---

## Directory Structure (Phase 2 Additions/Changes)

```
backend/src/dse/
│
├── services/                    # ← Phase 2 service additions
│   ├── graph.py                 # [NEW] Neo4j graph DB client
│   ├── cache.py                 # [NEW] Redis Working Memory client
│   ├── events.py                # [NEW] Redpanda/Kafka producer
│   ├── search.py                # [EXISTING — EXTENDED] Add contradiction candidate search methods
│   ├── embedding.py             # [EXISTING — EXTENDED] Add batch embedding methods
│   └── llm.py                   # [EXISTING — EXTENDED] Add classification/judgment prompts
│
├── core/
│   ├── models.py                # [EXISTING — EXTENDED] Add RelationRecord, ProvenanceEntry
│   ├── enums.py                 # [EXISTING — EXTENDED] Add RelationType, EvidenceType
│   └── exceptions.py            # [EXISTING — EXTENDED] Add GraphError, CDCError
│
├── agents/
│   └── mma/
│       ├── agent.py             # [EXISTING — EXTENDED] Add contradiction resolution tools
│       ├── tools/               # [NEW DIRECTORY] Split tools into separate files
│       │   ├── __init__.py
│       │   ├── store.py         # store_memory_tool
│       │   ├── contradiction.py # detect_contradiction_tool, resolve_contradiction_tool
│       │   ├── relation.py      # classify_relation_tool, create_relation_tool
│       │   ├── confidence.py    # update_confidence_tool
│       │   └── provenance.py    # record_provenance_tool
│       └── prompts.py           # [EXISTING — EXTENDED] Add Phase 2 prompts
│
├── workflows/
│   ├── worker.py                # [EXISTING — EXTENDED] Register Phase 2 workflows
│   ├── activities/
│   │   ├── indexing.py          # [EXISTING]
│   │   ├── decay.py             # [EXISTING]
│   │   ├── graph_ops.py         # [NEW] Graph operation activities
│   │   ├── contradiction.py     # [NEW] Contradiction detection/resolution activities
│   │   ├── confidence.py        # [NEW] Confidence update activities
│   │   ├── provenance.py        # [NEW] Provenance recording activities
│   │   └── cdc.py               # [NEW] CDC event processing activities
│   └── definitions/
│       ├── memory_write.py      # [EXISTING — EXTENDED] Add graph registration, provenance recording
│       ├── contradiction_check.py  # [NEW] Contradiction check workflow
│       ├── cdc_processor.py     # [NEW] CDC event processing workflow
│       └── daily_maintenance.py # [EXISTING — EXTENDED] Add confidence batch update
│
├── pipeline/
│   ├── retrieval.py             # [EXISTING — EXTENDED] Add graph neighbor expansion (Stage 3)
│   └── ranking.py               # [EXISTING — EXTENDED] Add CONTRADICTS penalty
│
└── api/
    └── routers/
        ├── memories.py          # [EXISTING — EXTENDED]
        ├── graph.py             # [NEW] Graph visualization and relations API
        ├── conflicts.py         # [NEW] Contradiction queue management API
        ├── provenance.py        # [NEW] Lineage retrieval API
        └── working_memory.py    # [NEW] Working Memory API
│
frontend/src/
├── app/
│   ├── graph/                   # [NEW] Memory graph visualization page
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── MemoryGraph.tsx  # React Flow graph component
│   │       ├── MemoryNode.tsx   # Custom node
│   │       └── RelationEdge.tsx # Custom edge
│   └── conflicts/              # [NEW] Contradiction queue management page
│       ├── page.tsx
│       └── components/
│           ├── ConflictQueue.tsx
│           └── ConflictResolver.tsx
└── lib/
    └── api/
        ├── graph.ts             # [NEW] Graph API client
        ├── conflicts.ts         # [NEW] Conflicts API client
        └── provenance.ts        # [NEW] Provenance API client
```

---

## Environment Variables (Phase 2 Additions)

Add the following to `.env.example`.

```bash
# ─── Neo4j ───────────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j                   # Default DB name

# ─── Redis ───────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_WORKING_MEMORY_TTL_SECONDS=7200  # Session expires after 2 hours
REDIS_CACHE_TTL_SECONDS=300            # API response cache: 5 minutes

# ─── Redpanda / Kafka ────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_MEMORY_EVENTS=dse.memory.events
KAFKA_TOPIC_CDC_EVENTS=dse.cdc.events
KAFKA_CONSUMER_GROUP=dse-mma-workers

# ─── Phase 2 Algorithm Settings ─────────────────────────
# Cosine similarity threshold for contradiction detection (0.0–1.0)
CONTRADICTION_COSINE_THRESHOLD=0.92
# Confidence delta threshold for automatic contradiction resolution
CONTRADICTION_AUTO_RESOLVE_CONFIDENCE_DELTA=0.30
# Default hop depth for graph neighbor expansion
GRAPH_DEFAULT_HOP_DEPTH=1
# Maximum hop depth for graph neighbor expansion (API parameter upper limit)
GRAPH_MAX_HOP_DEPTH=3
```

---

## docker-compose.yml Additional Service Definitions

Add the following services to `docker-compose.yml`.

```yaml
# ─── Neo4j ───────────────────────────────────────────────────────
  neo4j:
    image: neo4j:5
    container_name: dse-neo4j
    ports:
      - "7474:7474"   # HTTP Browser UI
      - "7687:7687"   # Bolt protocol
    environment:
      NEO4J_AUTH: "neo4j/password"
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*"
      NEO4J_dbms_memory_heap_initial__size: "512m"
      NEO4J_dbms_memory_heap_max__size: "1G"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./infra/neo4j/init.cypher:/var/lib/neo4j/import/init.cypher:ro
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 10

# ─── Redis ───────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: dse-redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

# ─── Redpanda ────────────────────────────────────────────────────
  redpanda:
    image: redpandadata/redpanda:latest
    container_name: dse-redpanda
    ports:
      - "9092:9092"   # Kafka API
      - "9644:9644"   # Redpanda Admin API
    command:
      - redpanda
      - start
      - --smp=1
      - --memory=512M
      - --overprovisioned
      - --node-id=0
      - --kafka-addr=PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr=PLAINTEXT://localhost:9092
      - --pandaproxy-addr=PLAINTEXT://0.0.0.0:8082
      - --advertise-pandaproxy-addr=PLAINTEXT://localhost:8082
      - --schema-registry-addr=http://0.0.0.0:8081
    volumes:
      - redpanda_data:/var/lib/redpanda/data
    healthcheck:
      test: ["CMD", "rpk", "cluster", "health"]
      interval: 10s
      timeout: 5s
      retries: 10

  redpanda-console:
    image: redpandadata/console:latest
    container_name: dse-redpanda-console
    ports:
      - "8085:8080"
    environment:
      CONFIG_FILEPATH: /tmp/config.yml
    volumes:
      - ./infra/redpanda/console-config.yml:/tmp/config.yml:ro
    depends_on:
      redpanda:
        condition: service_healthy

volumes:
  neo4j_data:
  neo4j_logs:
  redis_data:
  redpanda_data:
```

---

## P2-1: Neo4j Graph DB — Implementation Spec

### Initialization Cypher Script

File: `infra/neo4j/init.cypher`

```cypher
// ─── Constraints (uniqueness guarantees) ────────────────────────────────
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
  FOR (m:Memory) REQUIRE m.id IS UNIQUE;

CREATE CONSTRAINT conflict_id_unique IF NOT EXISTS
  FOR (c:ConflictRecord) REQUIRE c.id IS UNIQUE;

// ─── Indexes ────────────────────────────────────────────────────────────
CREATE INDEX memory_namespace IF NOT EXISTS
  FOR (m:Memory) ON (m.namespace);

CREATE INDEX memory_type_idx IF NOT EXISTS
  FOR (m:Memory) ON (m.memory_type);

CREATE INDEX memory_created_at IF NOT EXISTS
  FOR (m:Memory) ON (m.created_at);

CREATE INDEX memory_confidence IF NOT EXISTS
  FOR (m:Memory) ON (m.confidence);

CREATE INDEX memory_is_archived IF NOT EXISTS
  FOR (m:Memory) ON (m.is_archived);

CREATE INDEX memory_verification_status IF NOT EXISTS
  FOR (m:Memory) ON (m.verification_status);

// ─── Full-text search index (using APOC) ────────────────────────────────
CALL db.index.fulltext.createNodeIndex(
  "memoryFulltext",
  ["Memory"],
  ["summary"],
  {analyzer: "standard"}
) IF NOT EXISTS;
```

### Graph Service Implementation

File: `backend/src/dse/services/graph.py`

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncTransaction
from neo4j.exceptions import ConstraintError, ServiceUnavailable

from dse.config import settings
from dse.core.enums import RelationType
from dse.core.exceptions import GraphError
from dse.core.models import MemoryNode, RelationRecord

logger = structlog.get_logger(__name__)


class GraphService:
    """Neo4j graph DB client.

    All graph operations must go through this class.
    Do not write code that calls the neo4j driver directly elsewhere.
    """

    def __init__(self) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=50,
        )

    async def close(self) -> None:
        await self._driver.close()

    @asynccontextmanager
    async def _tx(self) -> AsyncIterator[AsyncTransaction]:
        """Transaction context manager.

        All Neo4j writes must use this.
        Automatically rolls back on exception.
        """
        async with self._driver.session(database=settings.neo4j_database) as session:
            async with session.begin_transaction() as tx:
                try:
                    yield tx
                    await tx.commit()
                except Exception as e:
                    await tx.rollback()
                    raise GraphError(f"Transaction failed: {e}") from e

    # ─── Node Operations ────────────────────────────────────────────────

    async def upsert_memory_node(self, node: MemoryNode) -> None:
        """Create or update a memory node."""
        cypher = """
        MERGE (m:Memory {id: $id})
        SET m.namespace          = $namespace,
            m.memory_type        = $memory_type,
            m.confidence         = $confidence,
            m.importance         = $importance,
            m.verification_status = $verification_status,
            m.is_archived        = $is_archived,
            m.created_at         = datetime($created_at),
            m.updated_at         = datetime($updated_at)
        """
        async with self._tx() as tx:
            await tx.run(cypher, **node.model_dump())

    async def get_memory_node(self, memory_id: str) -> MemoryNode | None:
        """Get a memory node by ID."""
        cypher = "MATCH (m:Memory {id: $id}) RETURN m"
        async with self._driver.session() as session:
            result = await session.run(cypher, id=memory_id)
            record = await result.single()
            if record is None:
                return None
            return MemoryNode(**dict(record["m"]))

    async def mark_archived(self, memory_id: str) -> None:
        """Mark a memory node as archived."""
        cypher = """
        MATCH (m:Memory {id: $id})
        SET m.is_archived = true, m.updated_at = datetime()
        """
        async with self._tx() as tx:
            await tx.run(cypher, id=memory_id)

    # ─── Edge Operations ────────────────────────────────────────────────

    async def create_relation(self, relation: RelationRecord) -> None:
        """Create an edge between two memory nodes.

        If an edge with the same direction and type already exists, MERGE will skip it.
        """
        # Use RelationType value as the Cypher relationship name
        rel_type = relation.relation_type.value  # e.g., "SUPERSEDED_BY"

        cypher = f"""
        MATCH (a:Memory {{id: $from_id}})
        MATCH (b:Memory {{id: $to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r.confidence   = $confidence,
            r.strength     = $strength,
            r.created_at   = datetime($created_at),
            r.created_by   = $created_by,
            r.method       = $method
        """
        async with self._tx() as tx:
            await tx.run(cypher, **relation.model_dump(exclude={"relation_type"}),
                        from_id=relation.from_id, to_id=relation.to_id)

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
        """Check if an edge with the specified direction and type exists."""
        rel_type = relation_type.value
        cypher = f"""
        MATCH (a:Memory {{id: $from_id}})-[r:{rel_type}]->(b:Memory {{id: $to_id}})
        RETURN count(r) > 0 AS exists
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, from_id=from_id, to_id=to_id)
            record = await result.single()
            return bool(record["exists"]) if record else False

    # ─── Queries ────────────────────────────────────────────────────────

    async def get_neighbors(
        self,
        memory_id: str,
        *,
        hop_depth: int = 1,
        exclude_relation_types: list[RelationType] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get neighbor nodes and edges within the specified hop depth.

        Used for search result context enrichment (Stage 3 Retrieval).
        """
        exclude_types = exclude_relation_types or []
        exclude_clause = ""
        if exclude_types:
            types_str = "|".join(t.value for t in exclude_types)
            exclude_clause = f"WHERE NOT type(r) IN ['{types_str}']"

        cypher = f"""
        MATCH (m:Memory {{id: $id}})
        CALL apoc.path.subgraphNodes(m, {{
            maxLevel: $hop_depth,
            labelFilter: '+Memory'
        }}) YIELD node AS neighbor
        WHERE neighbor.id <> $id AND neighbor.is_archived = false
        MATCH (m)-[r]-(neighbor)
        {exclude_clause}
        RETURN neighbor.id AS id,
               neighbor.memory_type AS memory_type,
               neighbor.confidence AS confidence,
               type(r) AS relation_type,
               r.strength AS strength
        ORDER BY r.strength DESC
        LIMIT $limit
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, id=memory_id, hop_depth=hop_depth, limit=limit)
            return [dict(record) async for record in result]

    async def get_contradicting_pairs(self, namespace: str) -> list[dict]:
        """Get all contradiction pairs within a namespace (for admin UI)."""
        cypher = """
        MATCH (a:Memory)-[r:CONTRADICTS]-(b:Memory)
        WHERE a.namespace = $namespace
          AND a.id < b.id           -- Deduplication (return only one side of bidirectional edges)
          AND a.is_archived = false
          AND b.is_archived = false
        RETURN a.id AS id_a,
               b.id AS id_b,
               a.confidence AS confidence_a,
               b.confidence AS confidence_b,
               r.detected_at AS detected_at,
               r.resolution_status AS resolution_status
        ORDER BY r.detected_at DESC
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, namespace=namespace)
            return [dict(record) async for record in result]

    async def get_lineage(self, memory_id: str, max_depth: int = 5) -> list[dict]:
        """Get the lineage chain (DERIVES edges) of a memory."""
        cypher = """
        MATCH path = (root:Memory {id: $id})-[:DERIVES*0..5]->(leaf:Memory)
        RETURN [node IN nodes(path) | node.id] AS lineage_ids,
               length(path) AS depth
        ORDER BY depth
        LIMIT 20
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, id=memory_id)
            return [dict(record) async for record in result]

    async def get_subgraph_for_visualization(
        self,
        namespace: str,
        *,
        limit_nodes: int = 100,
    ) -> dict:
        """Return nodes/edges for the React Flow frontend."""
        cypher = """
        MATCH (m:Memory)
        WHERE m.namespace = $namespace AND m.is_archived = false
        WITH m ORDER BY m.created_at DESC LIMIT $limit
        OPTIONAL MATCH (m)-[r]-(other:Memory)
        WHERE other.namespace = $namespace AND other.is_archived = false
        RETURN
            collect(DISTINCT {
                id: m.id,
                memory_type: m.memory_type,
                confidence: m.confidence,
                created_at: toString(m.created_at)
            }) AS nodes,
            collect(DISTINCT {
                source: startNode(r).id,
                target: endNode(r).id,
                relation_type: type(r),
                strength: r.strength
            }) AS edges
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, namespace=namespace, limit=limit_nodes)
            record = await result.single()
            if record is None:
                return {"nodes": [], "edges": []}
            return {"nodes": record["nodes"], "edges": record["edges"]}
```

### Edge Type Enum Definition

File: `backend/src/dse/core/enums.py` (append)

```python
from enum import StrEnum

class RelationType(StrEnum):
    """Memory relationship types.

    Values must exactly match Neo4j relationship names (UPPER_SNAKE_CASE).
    Design reference: DSE_Design_Report.md § 3.3 Graph DB Design
    """
    SUPERSEDED_BY      = "SUPERSEDED_BY"      # A is outdated and replaced by B
    COMPLEMENTS        = "COMPLEMENTS"          # A + B together form complete information
    CONTRADICTS        = "CONTRADICTS"          # A and B state conflicting facts (bidirectional)
    DERIVES            = "DERIVES"              # B was inferred/summarized from A
    CAUSES             = "CAUSES"               # A caused B
    REFERENCES         = "REFERENCES"           # A cites/references B
    HAS_CHILD          = "HAS_CHILD"            # A contains B (hierarchical)
    TEMPORALLY_PRECEDES = "TEMPORALLY_PRECEDES" # A occurred before B


class VerificationStatus(StrEnum):
    UNVERIFIED   = "unverified"
    VERIFIED     = "verified"
    CONTRADICTED = "contradicted"   # Contradiction flag
    PENDING      = "pending"        # Awaiting human review
    SUPERSEDED   = "superseded"     # Has been replaced


class EvidenceType(StrEnum):
    """Evidence types that serve as basis for confidence updates.

    Design reference: DSE_Design_Report.md § 6.2 Confidence and Epistemic State
    """
    USER_EXPLICIT_CORRECTION = "user_explicit_correction"
    CORROBORATING_SOURCE     = "corroborating_source"
    CONTRADICTING_SOURCE     = "contradicting_source"
    PASSAGE_OF_TIME          = "passage_of_time"
    REPEATED_ACCESS          = "repeated_access"
    RELATION_DERIVED         = "relation_derived"
```

---

## P2-2: Contradiction Detection & 3-Stage Resolution — Implementation Spec

Contradiction detection operates through two pathways: **write-time triggers** and **daily batch processing**.

### Contradiction Detection Flow (Detailed)

```
New memory write
     │
     ▼
[Activity: generate_embedding]
Generate vector with Gemini
     │
     ▼
[Activity: search_similar_candidates]
Retrieve memories with cosine similarity > CONTRADICTION_COSINE_THRESHOLD via Vertex AI Search
     │
  Candidates found?
  YES──────────────────────────────────────────────────────────────┐
     │ NO                                                           │
     ▼                                                             ▼
 Normal registration                      [Activity: llm_judge_contradiction]
 complete                                 Gemini judges: "contradiction, complement, or duplicate?"
                                               │
                             ┌───────────────┼──────────────────────┐
                             ▼               ▼                      ▼
                        Contradiction   Complementary          Identical/Duplicate
                             │               │                      │
                             ▼               ▼                      ▼
                    [auto_resolve?]   COMPLEMENTS edge      SUPERSEDES_BY edge
                             │        Register in Neo4j     Update existing
                    ┌────────┴────────┐
                    ▼                 ▼
                Auto-resolvable   Not auto-resolvable
                    │                 │
                    ▼                 ▼
               SUPERSEDED_BY     CONTRADICTS edge
               Add edge          Set both nodes'
               Set SUPERSEDED    verification_status
               flag on old       = "pending"
               node              Add to admin UI queue
```

### Contradiction Judgment Prompt

File: `backend/src/dse/agents/mma/prompts.py` (append)

```python
CONTRADICTION_JUDGE_PROMPT = """
You are a memory quality management AI for an AI agent system.
Accurately classify the relationship between the following two memories.

Memory A:
ID: {id_a}
Type: {type_a}
Created: {created_at_a}
Confidence: {confidence_a}
Content: {summary_a}

Memory B:
ID: {id_b}
Type: {type_b}
Created: {created_at_b}
Confidence: {confidence_b}
Content: {summary_b}

Choose one relationship from the following and respond in JSON:
- CONTRADICTS: The two state conflicting facts about the same subject
- SUPERSEDES: B updates/replaces A's content (newer information)
- COMPLEMENTS: The two together form more complete information
- DUPLICATE: Essentially the same content
- UNRELATED: No meaningful relationship

Return ONLY the following JSON with no preamble or explanation:
{{
  "relation": "CONTRADICTS|SUPERSEDES|COMPLEMENTS|DUPLICATE|UNRELATED",
  "confidence": 0.0 to 1.0,
  "reason": "Reasoning in 50 characters or less",
  "auto_resolvable": true|false,
  "recommended_keep": "A|B|both|null"
}}
"""

RELATION_CLASSIFY_PROMPT = """
You are a memory quality management AI for an AI agent system.
Classify the relationship type between the following two memories.

Memory A: {summary_a}
Memory B: {summary_b}

Available relationship types:
- SUPERSEDED_BY: A has been replaced by B (A→B direction)
- COMPLEMENTS: A and B are complementary (A→B direction)
- CONTRADICTS: A and B contradict each other (bidirectional)
- DERIVES: B was inferred/summarized from A (A→B direction)
- CAUSES: A caused B (A→B direction)
- REFERENCES: A references B (A→B direction)
- NONE: No relationship

Return ONLY the following JSON:
{{
  "relation_type": "type name or NONE",
  "confidence": 0.0 to 1.0,
  "reason": "Reason in 30 characters or less"
}}
"""
```

### Temporal Workflow: Contradiction Check

File: `backend/src/dse/workflows/definitions/contradiction_check.py`

```python
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))
TIMEOUT = timedelta(seconds=60)


@workflow.defn
class ContradictionCheckWorkflow:
    """Workflow that performs contradiction checks when a new memory is registered.

    Called as a child workflow from MemoryWriteWorkflow.
    Design reference: DSE_Design_Report.md § 4.3 Memory Contradictions and Conflicts
    """

    @workflow.run
    async def run(self, memory_id: str, namespace: str) -> dict:
        # Step 1: Search for similar memory candidates
        candidates = await workflow.execute_activity(
            "search_contradiction_candidates",
            args=[memory_id, namespace],
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

        if not candidates:
            return {"status": "no_candidates", "memory_id": memory_id}

        results = []
        for candidate_id in candidates:
            # Step 2: Judge relationship with LLM
            judgment = await workflow.execute_activity(
                "llm_judge_contradiction",
                args=[memory_id, candidate_id],
                start_to_close_timeout=TIMEOUT,
                retry_policy=RETRY,
            )

            relation = judgment["relation"]

            if relation == "CONTRADICTS":
                if judgment["auto_resolvable"]:
                    # Step 3a: Auto-resolve (keep the newer one)
                    await workflow.execute_activity(
                        "auto_resolve_contradiction",
                        args=[memory_id, candidate_id, judgment],
                        start_to_close_timeout=TIMEOUT,
                        retry_policy=RETRY,
                    )
                    results.append({"type": "auto_resolved", "candidate_id": candidate_id})
                else:
                    # Step 3b: Add to manual resolution queue
                    await workflow.execute_activity(
                        "enqueue_manual_resolution",
                        args=[memory_id, candidate_id, judgment],
                        start_to_close_timeout=TIMEOUT,
                        retry_policy=RETRY,
                    )
                    results.append({"type": "manual_required", "candidate_id": candidate_id})

            elif relation == "COMPLEMENTS":
                await workflow.execute_activity(
                    "create_graph_relation",
                    args=[memory_id, candidate_id, "COMPLEMENTS", judgment["confidence"]],
                    start_to_close_timeout=TIMEOUT,
                    retry_policy=RETRY,
                )
                results.append({"type": "complemented", "candidate_id": candidate_id})

            elif relation in ("SUPERSEDES", "DUPLICATE"):
                await workflow.execute_activity(
                    "create_supersedes_relation",
                    args=[memory_id, candidate_id],
                    start_to_close_timeout=TIMEOUT,
                    retry_policy=RETRY,
                )
                results.append({"type": "superseded", "candidate_id": candidate_id})

        return {"status": "completed", "memory_id": memory_id, "results": results}
```

---

## P2-3: Confidence Score + Bayesian Updates — Implementation Spec

### Confidence Fields (Addition to Vertex AI Search Index)

Add the following fields to the Phase 1 index (update `docs/vertex_schema.json`).

```json
{
  "confidence":              { "type": "number", "filterable": true, "retrievable": true },
  "confidence_basis":        { "type": "string", "retrievable": true },
  "corroborating_sources":   { "type": "integer", "retrievable": true },
  "contradicting_sources":   { "type": "integer", "retrievable": true },
  "confidence_updated_at":   { "type": "string", "filterable": true, "retrievable": true },
  "verification_status":     { "type": "string", "filterable": true, "retrievable": true }
}
```

### Bayesian Update Logic

File: `backend/src/dse/workflows/activities/confidence.py`

```python
from __future__ import annotations

import math

from temporalio import activity

from dse.core.enums import EvidenceType
from dse.core.models import Evidence
from dse.services.search import SearchService


# Update strength constants per evidence type
# Design reference: DSE_Design_Report.md § 6.2 Confidence and Epistemic State
EVIDENCE_DELTA: dict[EvidenceType, float] = {
    EvidenceType.USER_EXPLICIT_CORRECTION: 1.0,   # Explicit user correction → forced value
    EvidenceType.CORROBORATING_SOURCE:     0.15,  # Corroborating evidence
    EvidenceType.CONTRADICTING_SOURCE:    -0.20,  # Contradicting evidence
    EvidenceType.PASSAGE_OF_TIME:         -0.01,  # Time decay (applied daily)
    EvidenceType.REPEATED_ACCESS:          0.05,  # Repeated retrieval
    EvidenceType.RELATION_DERIVED:        -0.05,  # Derived via inference (lower trust than source)
}


@activity.defn
async def update_confidence_activity(memory_id: str, evidence_dict: dict) -> float:
    """Activity that performs Bayesian update of a memory's confidence score.

    Args:
        memory_id: ID of the memory to update
        evidence_dict: Dict representation of Evidence

    Returns:
        Updated confidence value (0.0–1.0)
    """
    evidence = Evidence(**evidence_dict)
    search_svc = SearchService()

    current = await search_svc.get_by_id(memory_id)
    if current is None:
        raise ValueError(f"Memory not found: {memory_id}")

    prior = current["confidence"]

    if evidence.type == EvidenceType.USER_EXPLICIT_CORRECTION:
        # Explicit user correction overrides immediately (not Bayesian update, but forced)
        new_confidence = evidence.forced_value if evidence.forced_value is not None else 1.0
    else:
        delta = EVIDENCE_DELTA.get(evidence.type, 0.0)

        # Stronger boost from independent sources, weaker from same source
        if evidence.type == EvidenceType.CORROBORATING_SOURCE:
            delta *= 1.5 if evidence.source_independent else 0.7

        new_confidence = _clamp(prior + delta)

    # Update
    patch: dict = {
        "confidence": new_confidence,
        "confidence_updated_at": _now_iso(),
    }
    if evidence.type == EvidenceType.CORROBORATING_SOURCE:
        patch["corroborating_sources"] = (current.get("corroborating_sources") or 0) + 1
    elif evidence.type == EvidenceType.CONTRADICTING_SOURCE:
        patch["contradicting_sources"] = (current.get("contradicting_sources") or 0) + 1

    await search_svc.patch(memory_id, patch)

    activity.logger.info(
        "confidence.updated",
        memory_id=memory_id,
        prior=prior,
        posterior=new_confidence,
        evidence_type=evidence.type,
    )
    return new_confidence


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
```

---

## P2-4: Working Memory Buffer (Redis Streams) — Implementation Spec

### Redis Client Implementation

File: `backend/src/dse/services/cache.py`

```python
from __future__ import annotations

import json
from typing import Any

import structlog
from redis.asyncio import Redis

from dse.config import settings

logger = structlog.get_logger(__name__)

# Redis key prefix conventions
# working_memory:{session_id}:context   → Session context
# working_memory:{session_id}:turns     → Conversation turns (Redis Stream)
# cache:search:{query_hash}             → Search result cache
# cache:embedding:{text_hash}           → Embedding cache


class WorkingMemoryService:
    """Working Memory using Redis (volatile short-term memory).

    Holds transient state within a session.
    At session end, the MMA persists only the important items to DSE (Vertex AI Search).
    Design reference: DSE_Design_Report.md § 5.1 Working Memory Buffer
    """

    def __init__(self) -> None:
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._ttl = settings.redis_working_memory_ttl_seconds

    async def close(self) -> None:
        await self._redis.aclose()

    # ─── Session Context ────────────────────────────────────────────────

    async def set_context(self, session_id: str, context: dict) -> None:
        """Save the current context of a session."""
        key = f"working_memory:{session_id}:context"
        await self._redis.setex(key, self._ttl, json.dumps(context, ensure_ascii=False))

    async def get_context(self, session_id: str) -> dict | None:
        """Get the context of a session."""
        key = f"working_memory:{session_id}:context"
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    async def delete_context(self, session_id: str) -> None:
        """Delete context at session end."""
        await self._redis.delete(f"working_memory:{session_id}:context")

    # ─── Conversation Turns (Redis Stream) ──────────────────────────────

    async def append_turn(self, session_id: str, turn: dict) -> str:
        """Append a conversation turn to the Redis Stream.

        Returns:
            str: Redis Stream entry ID
        """
        key = f"working_memory:{session_id}:turns"
        entry_id = await self._redis.xadd(
            key,
            {"data": json.dumps(turn, ensure_ascii=False)},
            maxlen=200,     # Max 200 turns (older ones auto-deleted)
        )
        await self._redis.expire(key, self._ttl)
        return entry_id

    async def get_recent_turns(self, session_id: str, *, count: int = 20) -> list[dict]:
        """Get the most recent conversation turns."""
        key = f"working_memory:{session_id}:turns"
        entries = await self._redis.xrevrange(key, count=count)
        return [json.loads(e[1]["data"]) for e in entries]

    async def snapshot_for_persistence(self, session_id: str) -> dict:
        """Create a snapshot for MMA handoff at session end."""
        context = await self.get_context(session_id)
        turns = await self.get_recent_turns(session_id, count=50)
        return {"session_id": session_id, "context": context, "turns": turns}

    # ─── Search Result Cache ────────────────────────────────────────────

    async def cache_search_result(self, query_hash: str, result: Any) -> None:
        key = f"cache:search:{query_hash}"
        await self._redis.setex(
            key,
            settings.redis_cache_ttl_seconds,
            json.dumps(result, ensure_ascii=False),
        )

    async def get_cached_search_result(self, query_hash: str) -> Any | None:
        key = f"cache:search:{query_hash}"
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None

    # ─── Embedding Cache ────────────────────────────────────────────────

    async def cache_embedding(self, text_hash: str, embedding: list[float]) -> None:
        """Cache a generated embedding to save Gemini API calls."""
        key = f"cache:embedding:{text_hash}"
        await self._redis.setex(
            key,
            3600 * 24,  # 24 hours
            json.dumps(embedding),
        )

    async def get_cached_embedding(self, text_hash: str) -> list[float] | None:
        key = f"cache:embedding:{text_hash}"
        raw = await self._redis.get(key)
        return json.loads(raw) if raw else None
```

---

## P2-5: CDC Pipeline — Implementation Spec

### Kafka Topic Design

| Topic Name | Producer | Consumer | Purpose |
|------------|----------|----------|---------|
| `dse.memory.events` | FastAPI (write path) | MMA Worker | Async processing trigger after memory writes |
| `dse.cdc.events` | External systems / Debezium | MMA Worker | Reflect external DB changes in DSE |
| `dse.contradiction.alerts` | MMA Worker | Admin UI Webhook | Contradiction detection notifications |

### Event Schema

File: `backend/src/dse/core/events.py`

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from ulid import ULID


class MemoryEventType(StrEnum):
    CREATED  = "memory.created"
    UPDATED  = "memory.updated"
    DELETED  = "memory.deleted"
    ACCESSED = "memory.accessed"


class CDCEventType(StrEnum):
    INSERT = "cdc.insert"
    UPDATE = "cdc.update"
    DELETE = "cdc.delete"


class MemoryEvent(BaseModel):
    """Event published to Kafka after a memory write."""
    event_id: str = Field(default_factory=lambda: str(ULID()))
    event_type: MemoryEventType
    memory_id: str
    namespace: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CDCEvent(BaseModel):
    """CDC event received from external systems."""
    event_id: str = Field(default_factory=lambda: str(ULID()))
    event_type: CDCEventType
    source_system: str         # "salesforce" | "jira" | "github" | "custom"
    source_entity_type: str
    source_entity_id: str
    namespace: str
    payload_before: dict[str, Any] | None = None
    payload_after: dict[str, Any] | None = None
    timestamp: str
```

### CDC Consumer Implementation

File: `backend/src/dse/workflows/activities/cdc.py`

```python
from __future__ import annotations

import asyncio
import json

import structlog
from aiokafka import AIOKafkaConsumer
from temporalio.client import Client as TemporalClient

from dse.config import settings
from dse.core.events import CDCEvent

logger = structlog.get_logger(__name__)


async def run_cdc_consumer() -> None:
    """Main loop for the CDC event consumer.

    Receives CDC events from Redpanda and converts them
    into Temporal Workflows to pass to the MMA.
    Runs as a separate process from the Temporal Worker.
    """
    temporal_client = await TemporalClient.connect(settings.temporal_host)

    consumer = AIOKafkaConsumer(
        settings.kafka_topic_cdc_events,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"{settings.kafka_consumer_group}-cdc",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode()),
    )

    await consumer.start()
    logger.info("cdc_consumer.started", topic=settings.kafka_topic_cdc_events)

    try:
        async for msg in consumer:
            try:
                event = CDCEvent(**msg.value)
                await _process_cdc_event(temporal_client, event)
            except Exception as e:
                logger.error("cdc_consumer.process_error", error=str(e), msg_value=msg.value)
    finally:
        await consumer.stop()
        await temporal_client.close()


async def _process_cdc_event(client: TemporalClient, event: CDCEvent) -> None:
    """Start a Temporal workflow for a CDC event."""
    await client.start_workflow(
        "CDCProcessorWorkflow",
        event.model_dump(),
        id=f"cdc-{event.event_id}",
        task_queue=settings.temporal_task_queue,
    )
    logger.info(
        "cdc_consumer.workflow_started",
        event_id=event.event_id,
        source=event.source_system,
    )
```

---

## P2-6: Provenance Tracking — Implementation Spec

### Provenance Schema

File: `backend/src/dse/core/models.py` (append)

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from ulid import ULID


class ProvenanceEntry(BaseModel):
    """A provenance entry for a memory.

    Each element in the provenance array within Object Storage's metadata.json.
    Design reference: DSE_Design_Report.md § 6.5 Memory Provenance Tracking
    """
    entry_id: str = Field(default_factory=lambda: str(ULID()))
    step: str                          # "observation" | "extraction" | "summarization" | "inference"
    timestamp: str
    performed_by: str                  # "agent:{id}" | "user:{id}" | "system"
    task_id: str | None = None
    session_id: str | None = None
    description: str
    model_used: str | None = None      # e.g., "gemini-2.5-flash"
    input_memory_ids: list[str] = Field(default_factory=list)  # Source memory IDs for derivation


class AccessLogEntry(BaseModel):
    """An access record for a memory (each element in the provenance access_log array)."""
    accessed_by: str
    accessed_at: str
    task_id: str | None = None
    utility_score: float | None = None   # Usefulness score fed back by the agent


class MemoryProvenance(BaseModel):
    """Complete provenance information for a memory. Persisted to Object Storage."""
    memory_id: str
    created_by: ProvenanceEntry
    transformations: list[ProvenanceEntry] = Field(default_factory=list)
    access_log: list[AccessLogEntry] = Field(default_factory=list)
```

### Provenance Service Implementation

File: `backend/src/dse/infrastructure/provenance.py`

```python
from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog

from dse.core.models import AccessLogEntry, MemoryProvenance, ProvenanceEntry
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)

PROVENANCE_PATH_TEMPLATE = "provenance/{namespace}/{memory_id}.json"


class ProvenanceService:
    """Service that records and retrieves memory provenance from Object Storage.

    Provenance is stored as a separate file in Object Storage.
    Not stored in the Search Index (to reduce storage and update costs).
    """

    def __init__(self) -> None:
        self._storage = StorageService()

    def _path(self, namespace: str, memory_id: str) -> str:
        return PROVENANCE_PATH_TEMPLATE.format(namespace=namespace, memory_id=memory_id)

    async def initialize(
        self,
        memory_id: str,
        namespace: str,
        created_by: ProvenanceEntry,
    ) -> None:
        """Initialize the provenance file when a memory is created."""
        provenance = MemoryProvenance(
            memory_id=memory_id,
            created_by=created_by,
        )
        await self._write(namespace, memory_id, provenance)
        logger.info("provenance.initialized", memory_id=memory_id)

    async def record_transformation(
        self,
        memory_id: str,
        namespace: str,
        entry: ProvenanceEntry,
    ) -> None:
        """Record a transformation such as summarization or inference."""
        provenance = await self._read(namespace, memory_id)
        if provenance is None:
            logger.warning("provenance.not_found_on_transform", memory_id=memory_id)
            return
        provenance.transformations.append(entry)
        await self._write(namespace, memory_id, provenance)

    async def record_access(
        self,
        memory_id: str,
        namespace: str,
        accessed_by: str,
        task_id: str | None = None,
        utility_score: float | None = None,
    ) -> None:
        """Record an access to a memory (for the feedback loop)."""
        provenance = await self._read(namespace, memory_id)
        if provenance is None:
            return
        entry = AccessLogEntry(
            accessed_by=accessed_by,
            accessed_at=datetime.now(UTC).isoformat(),
            task_id=task_id,
            utility_score=utility_score,
        )
        # Limit access_log to a maximum of 500 entries
        provenance.access_log.append(entry)
        if len(provenance.access_log) > 500:
            provenance.access_log = provenance.access_log[-500:]
        await self._write(namespace, memory_id, provenance)

    async def get(self, memory_id: str, namespace: str) -> MemoryProvenance | None:
        return await self._read(namespace, memory_id)

    async def _read(self, namespace: str, memory_id: str) -> MemoryProvenance | None:
        path = self._path(namespace, memory_id)
        raw = await self._storage.read_text(path)
        if raw is None:
            return None
        return MemoryProvenance(**json.loads(raw))

    async def _write(self, namespace: str, memory_id: str, provenance: MemoryProvenance) -> None:
        path = self._path(namespace, memory_id)
        await self._storage.write_text(path, provenance.model_dump_json(indent=2))
```

---

## P2-7: Frontend — Graph Visualization & Contradiction Queue

### Graph Visualization Component

File: `frontend/src/app/graph/components/MemoryGraph.tsx`

```typescript
"use client";

import { useCallback } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { fetchSubgraph } from "@/lib/api/graph";
import { MemoryNode } from "./MemoryNode";
import { RelationEdge } from "./RelationEdge";

const nodeTypes = { memory: MemoryNode };
const edgeTypes = { relation: RelationEdge };

// Color definitions per edge type
const EDGE_COLOR: Record<string, string> = {
  SUPERSEDED_BY:       "#f59e0b",  // amber
  COMPLEMENTS:         "#10b981",  // emerald
  CONTRADICTS:         "#ef4444",  // red
  DERIVES:             "#6366f1",  // indigo
  CAUSES:              "#8b5cf6",  // violet
  REFERENCES:          "#64748b",  // slate
  HAS_CHILD:           "#06b6d4",  // cyan
  TEMPORALLY_PRECEDES: "#d1d5db",  // gray
};

interface Props {
  namespace: string;
}

export function MemoryGraph({ namespace }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["graph", namespace],
    queryFn: () => fetchSubgraph(namespace),
    refetchInterval: 30_000,
  });

  const rfNodes: Node[] = (data?.nodes ?? []).map((n: any) => ({
    id: n.id,
    type: "memory",
    position: { x: Math.random() * 800, y: Math.random() * 600 }, // Layout will be computed with dagre later
    data: {
      memoryType: n.memory_type,
      confidence: n.confidence,
      createdAt: n.created_at,
    },
  }));

  const rfEdges: Edge[] = (data?.edges ?? []).map((e: any, i: number) => ({
    id: `${e.source}-${e.target}-${e.relation_type}-${i}`,
    source: e.source,
    target: e.target,
    type: "relation",
    animated: e.relation_type === "CONTRADICTS",
    style: { stroke: EDGE_COLOR[e.relation_type] ?? "#94a3b8" },
    data: { relationType: e.relation_type, strength: e.strength },
  }));

  const [nodes, , onNodesChange] = useNodesState(rfNodes);
  const [edges, , onEdgesChange] = useEdgesState(rfEdges);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-slate-500 text-sm">Loading graph...</p>
      </div>
    );
  }

  return (
    <div className="h-[70vh] w-full rounded-lg border border-slate-200 dark:border-slate-700">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
```

### Contradiction Queue Component

File: `frontend/src/app/conflicts/components/ConflictQueue.tsx`

```typescript
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchConflicts, resolveConflict } from "@/lib/api/conflicts";
import { formatDistanceToNow } from "date-fns";

interface Conflict {
  id_a: string;
  id_b: string;
  confidence_a: number;
  confidence_b: number;
  detected_at: string;
  resolution_status: "pending" | "resolved" | "dismissed";
  summary_a?: string;
  summary_b?: string;
}

interface Props {
  namespace: string;
}

export function ConflictQueue({ namespace }: Props) {
  const qc = useQueryClient();

  const { data: conflicts = [] } = useQuery<Conflict[]>({
    queryKey: ["conflicts", namespace],
    queryFn: () => fetchConflicts(namespace),
    refetchInterval: 10_000,
  });

  const resolveMutation = useMutation({
    mutationFn: ({ idA, idB, keep }: { idA: string; idB: string; keep: "A" | "B" | "both" }) =>
      resolveConflict(namespace, idA, idB, keep),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conflicts"] }),
  });

  const pending = conflicts.filter((c) => c.resolution_status === "pending");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-slate-900 dark:text-slate-100">
          Contradiction Queue
        </h2>
        {pending.length > 0 && (
          <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900 dark:text-red-300">
            {pending.length} items
          </span>
        )}
      </div>

      {pending.length === 0 ? (
        <p className="text-sm text-slate-500">No unresolved contradictions</p>
      ) : (
        <ul className="divide-y divide-slate-200 dark:divide-slate-700">
          {pending.map((c) => (
            <li key={`${c.id_a}-${c.id_b}`} className="py-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <ConflictCard
                  memoryId={c.id_a}
                  confidence={c.confidence_a}
                  summary={c.summary_a}
                  label="Memory A"
                />
                <ConflictCard
                  memoryId={c.id_b}
                  confidence={c.confidence_b}
                  summary={c.summary_b}
                  label="Memory B"
                />
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Detected: {formatDistanceToNow(new Date(c.detected_at), { addSuffix: true })}
              </p>
              <div className="mt-3 flex gap-2">
                {(["A", "B", "both"] as const).map((keep) => (
                  <button
                    key={keep}
                    onClick={() =>
                      resolveMutation.mutate({ idA: c.id_a, idB: c.id_b, keep })
                    }
                    className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    {keep === "both" ? "Keep both" : `Keep ${keep}`}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ConflictCard({
  memoryId,
  confidence,
  summary,
  label,
}: {
  memoryId: string;
  confidence: number;
  summary?: string;
  label: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-slate-800 dark:text-slate-200 line-clamp-3">
        {summary ?? memoryId}
      </p>
      <div className="mt-2 flex items-center gap-1">
        <div className="h-1.5 flex-1 rounded-full bg-slate-200">
          <div
            className="h-1.5 rounded-full bg-emerald-500"
            style={{ width: `${confidence * 100}%` }}
          />
        </div>
        <span className="text-xs text-slate-500">{(confidence * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
```

---

## API Endpoints (Phase 2 Additions)

```
# Graph
GET    /v1/graph/subgraph?namespace={ns}&limit={n}   # Subgraph for visualization
GET    /v1/graph/neighbors/{id}?depth={d}&limit={n}  # Get neighbor nodes
GET    /v1/graph/lineage/{id}                        # Lineage chain

# Contradiction Management
GET    /v1/conflicts?namespace={ns}&status={s}       # List contradiction pairs
POST   /v1/conflicts/resolve                         # Manually resolve contradiction
        Body: {id_a, id_b, keep: "A"|"B"|"both", reason}

# Confidence
POST   /v1/memories/{id}/feedback                   # Post-access feedback
        Body: {utility_score: 0.0-1.0, task_id, accessed_by}
POST   /v1/memories/{id}/evidence                   # Add confidence update evidence
        Body: {evidence_type, source_independent, forced_value}

# Provenance
GET    /v1/memories/{id}/provenance                  # Get provenance
POST   /v1/memories/{id}/provenance/access           # Record access log

# Working Memory
GET    /v1/sessions/{session_id}/context             # Get session context
PUT    /v1/sessions/{session_id}/context             # Update session context
GET    /v1/sessions/{session_id}/turns               # Get conversation turns
POST   /v1/sessions/{session_id}/persist             # Trigger MMA persistence
DELETE /v1/sessions/{session_id}                     # End session
```

---

## Temporal Task Queues and Workflow List

| Task Queue | Workflow | Execution Condition |
|-----------|---------|---------------------|
| `dse-main` | `MemoryWriteWorkflow` | On memory write (synchronous start) |
| `dse-main` | `ContradictionCheckWorkflow` | Child workflow from MemoryWriteWorkflow |
| `dse-main` | `CDCProcessorWorkflow` | Triggered from Redpanda consumer |
| `dse-main` | `SessionPersistWorkflow` | On session end |
| `dse-maintenance` | `DailyMaintenanceWorkflow` | Daily at 02:00 UTC |
| `dse-maintenance` | `DecayUpdateWorkflow` | Called from DailyMaintenance |
| `dse-maintenance` | `ConfidenceBatchUpdateWorkflow` | Called from DailyMaintenance |
| `dse-discovery` | `RelationDiscoveryWorkflow` | Daily at 04:00 UTC |

---

## Test Requirements (Phase 2)

### Unit Tests (Required)

Write the following tests for each feature:

```
tests/unit/
├── test_graph_service.py
│   ├── test_upsert_memory_node         # Node creation and duplicate MERGE
│   ├── test_create_relation_all_types  # All 8 edge types creation
│   ├── test_relation_exists            # Existence check
│   └── test_get_neighbors             # Neighbor retrieval (depth 1, 2)
│
├── test_contradiction_detection.py
│   ├── test_auto_resolve_newer_wins    # Newer one replaces the older
│   ├── test_auto_resolve_high_confidence_wins  # Higher confidence replaces lower
│   ├── test_manual_queue_when_ambiguous # Ambiguous contradictions go to queue
│   └── test_complement_creates_edge    # Complementary info creates COMPLEMENTS edge
│
├── test_confidence_bayesian.py
│   ├── test_user_correction_forces_value
│   ├── test_corroborating_source_increases
│   ├── test_contradicting_source_decreases
│   ├── test_clamping_min_max           # Never goes outside 0.0–1.0 range
│   └── test_independent_source_stronger_than_dependent
│
├── test_working_memory.py
│   ├── test_set_get_context
│   ├── test_append_get_turns
│   ├── test_ttl_expiry                 # Verify keys expire with TTL
│   └── test_snapshot_for_persistence
│
└── test_provenance.py
    ├── test_initialize_creates_file
    ├── test_record_transformation
    ├── test_record_access_log
    └── test_access_log_max_500        # Verify trimming at 500 entries
```

### Integration Tests (Required)

```
tests/integration/
├── test_neo4j_graph.py                 # Connect to real Neo4j (Docker)
│   ├── test_full_write_read_cycle
│   ├── test_contradiction_subgraph_query
│   └── test_lineage_multi_hop
│
├── test_redis_working_memory.py        # Connect to real Redis (Docker)
│   └── test_session_lifecycle          # Create → read → expire
│
└── test_contradiction_workflow.py      # Temporal Test Kit
    └── test_workflow_auto_resolve
```

Ensure Docker is running before executing tests:

```python
# Add the following to tests/conftest.py
import pytest
import docker

@pytest.fixture(scope="session", autouse=True)
def check_docker_services():
    client = docker.from_env()
    required = ["dse-neo4j", "dse-redis", "dse-redpanda"]
    running = {c.name for c in client.containers.list()}
    missing = [s for s in required if s not in running]
    if missing:
        pytest.skip(f"Docker services not running: {missing}. Run `make dev` first")
```

---

## Phase 2 Completion Checklist

Phase 2 is complete when all of the following are satisfied:

- [ ] `make dev` starts Neo4j / Redis / Redpanda successfully
- [ ] `make db-init` creates Neo4j constraints and indexes
- [ ] `make test-unit` passes 100%
- [ ] `make test-int` passes 100% (with Docker running)
- [ ] ContradictionCheckWorkflow is registered in Temporal on memory write
- [ ] Workflow execution history is visible in Temporal UI (http://localhost:8080)
- [ ] Frontend `/graph` displays the memory graph
- [ ] Frontend `/conflicts` displays and allows resolving the contradiction queue
- [ ] `/v1/memories/{id}/provenance` returns Provenance JSON
- [ ] `GET /v1/graph/neighbors/{id}` returns graph neighbors
- [ ] Confidence feedback API updates the score
- [ ] Redis Working Memory stores and retrieves session context
- [ ] Events are visible in Redpanda Console (http://localhost:8085)
- [ ] `make lint` passes with no errors (mypy strict + ruff + tsc)

---

## Common Implementation Mistakes (Phase 2 Specific)

**Neo4j Related**

1. **Calling `run()` directly without `async with session.begin_transaction()`**
   → Always write within a transaction. Use the `GraphService._tx()` context manager

2. **Creating CONTRADICTS edges in only one direction**
   → CONTRADICTS is conceptually bidirectional, but create it as a unidirectional edge in Neo4j
   and use undirected match `(a)-[:CONTRADICTS]-(b)` in queries

3. **Registering duplicate edges**
   → Use `MERGE`. `CREATE` will create duplicate edges

4. **Running subgraph queries on Neo4j without APOC installed**
   → `NEO4J_PLUGINS: '["apoc"]'` in docker-compose is required. Verify after health check

**Contradiction Detection Related**

5. **Comparing LLM JSON responses as strings without parsing**
   → Always parse with `json.loads()` and validate with Pydantic models

6. **Hardcoding the contradiction detection similarity threshold**
   → Always reference `settings.contradiction_cosine_threshold`

**Temporal Related**

7. **Calling `datetime.now()` directly in Workflows**
   → Use `workflow.now()`. Otherwise, the timestamp changes on replay, breaking determinism

8. **Awaiting another Activity from within an Activity**
   → Activities are atomic units. If an Activity needs to call another Activity, promote it to the Workflow layer

**Redpanda / Kafka Related**

9. **Consumer fails if topics don't exist at startup**
   → Pre-create topics with `make dev-init-topics` (add to Makefile)

10. **Not handling null `payload_before` and `payload_after` in CDC events**
    → `payload_after` is null for DELETE events. Always include None checks

---

## Reference Documentation

- [DSE Design Report](./docs/DSE_Design_Report.md) ← **Always refer to this during Phase 2 implementation**
- [Vertex AI Search](https://docs.cloud.google.com/generative-ai-app-builder/docs)
- [Gemini API Models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [Google ADK](https://google.github.io/adk-docs/)
- [Temporal Workflow](https://docs.temporal.io/workflows)
- [Neo4j Python Driver (Async)](https://neo4j.com/docs/python-manual/current/async/)
- [React Flow](https://reactflow.dev/)
