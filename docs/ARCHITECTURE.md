# DSE Architecture

> Dynamic Search Engine for Agentic Memory — Technical Architecture Document

This document describes the architecture, data flows, algorithms, and design decisions behind DSE. It is intended for developers working on the system and for architects evaluating its design.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Memory Model](#2-memory-model)
3. [Service Architecture](#3-service-architecture)
4. [Write Path](#4-write-path)
5. [Read Path — Cascade Retrieval](#5-read-path--cascade-retrieval)
6. [Ranking and Scoring](#6-ranking-and-scoring)
7. [Context Assembly](#7-context-assembly)
8. [Knowledge Graph](#8-knowledge-graph)
9. [Intelligence Layer](#9-intelligence-layer)
10. [Working Memory](#10-working-memory)
11. [MCP Interface](#11-mcp-interface)
12. [Agent Framework](#12-agent-framework)
13. [Temporal Workflows](#13-temporal-workflows)
14. [Infrastructure](#14-infrastructure)
15. [Frontend Dashboard](#15-frontend-dashboard)
16. [Configuration and Feature Flags](#16-configuration-and-feature-flags)
17. [Testing Strategy](#17-testing-strategy)
18. [Deployment Topology](#18-deployment-topology)

---

## 1. System Overview

DSE is a search-engine-backed memory system for AI agents. Rather than stuffing all context into an LLM's prompt, agents query DSE to retrieve only the memories relevant to their current task.

```
                           AI Agent Layer
           ┌──────────┐  ┌──────────┐  ┌──────────────┐
           │Task Agent│  │Chat Agent│  │Memory Manager│
           └────┬─────┘  └────┬─────┘  └──────┬───────┘
                │              │               │
        ┌───────┴──────────────┴───────────────┴────────┐
        │              MCP Interface (stdio / HTTP)      │
        └───────┬──────────────┬───────────────┬────────┘
                │              │               │
        ┌───────▼──────────────▼───────────────▼────────┐
        │              DSE Gateway (FastAPI)              │
        │  Query preprocessing → Cascade retrieval →      │
        │  RRF ranking → Context assembly                 │
        └───┬────────┬─────────┬──────────┬─────────┬───┘
            │        │         │          │         │
     ┌──────▼─┐ ┌────▼────┐ ┌─▼──────┐ ┌─▼─────┐ ┌▼──────┐
     │Elastic- │ │ Object  │ │ Neo4j  │ │ Redis │ │Temporal│
     │search   │ │ Storage │ │ Graph  │ │ Cache │ │       │
     │         │ │(GCS/    │ │        │ │       │ │       │
     │BM25+kNN │ │ MinIO)  │ │8 edges │ │Working│ │Sagas  │
     │hybrid   │ │         │ │        │ │Memory │ │       │
     └─────────┘ └─────────┘ └────────┘ └───────┘ └───────┘
```

### Design Principles

- **Retrieval-first**: Memories are found through search, not loaded in bulk
- **Cognitive-science-inspired**: Four memory types mirror human cognition
- **Graceful degradation**: Each service can be mocked; the system works offline
- **Privacy by design**: PII detection runs before storage, configurable policy
- **Evolvability**: Temporal workflows decouple write concerns into independently deployable activities

---

## 2. Memory Model

### 2.1 Memory Types

Inspired by cognitive science, DSE classifies memories into four types with distinct lifecycle behaviors:

| Type | Purpose | Decay Rate | Example |
|------|---------|------------|---------|
| **Episodic** | Specific experiences and events | 0.05/day (fast) | "Deployed v2.0 on March 10, latency increased 20%" |
| **Semantic** | Facts, knowledge, generalizations | 0.01/day (slow) | "Python is an interpreted language" |
| **Procedural** | Skills, rules, how-to instructions | 0.008/day (slowest) | "Always run integration tests before merging" |
| **Prospective** | Future intentions, reminders, triggers | 0.0 (no decay) | "Check model accuracy next Monday" |

### 2.2 MemoryRecord Schema

The core `MemoryRecord` model has ~40 fields organized into groups:

```
MemoryRecord
├── Identity
│   ├── id: UUID
│   └── namespace: str              # "agent:{id}" or "project:{id}"
│
├── Content
│   ├── content_text: str           # Full text
│   ├── summary: str (≤500 chars)   # LLM-generated or explicit
│   └── content_path: str           # Object storage path
│
├── Embeddings
│   ├── embedding: float[3072]      # Gemini embedding-2-preview
│   ├── embedding_model: str
│   └── embedding_version: str
│
├── Classification
│   ├── memory_type: MemoryType
│   ├── memory_subtype: MemorySubtype    # observation/inference/user_explicit/agent_generated
│   └── content_type: ContentType        # text/image/audio/document/code/structured_data
│
├── Confidence & Verification
│   ├── confidence: float [0.0–1.0]     # Bayesian-updated
│   ├── confidence_basis: str
│   ├── corroborating_sources: int
│   ├── contradicting_sources: int
│   ├── source_type: SourceType
│   ├── source_id: str
│   └── verification_status: VerificationStatus
│
├── Lifecycle
│   ├── created_at, updated_at, accessed_at: datetime
│   ├── expires_at: datetime | None
│   ├── decay_score: float [0.0–1.0]
│   └── importance_score: float [0.0–1.0]
│
├── Access Metrics
│   ├── access_count: int
│   ├── access_count_7d, access_count_30d: int
│   └── last_access_utility: float
│
├── Relations
│   ├── superseded_by: str | None
│   ├── supersedes: list[str]
│   ├── parent_id: str | None
│   └── neighbor_ids: list[str]
│
├── Metadata
│   ├── tags: list[str]
│   ├── entities: list[str]         # Named entities (LLM-extracted)
│   └── language: str
│
├── Prospective (only when memory_type=PROSPECTIVE)
│   ├── trigger_type: time | event | condition
│   ├── trigger_at: datetime | None
│   ├── trigger_condition: str | None
│   └── is_triggered: bool
│
└── Archive
    ├── is_archived: bool
    ├── archived_at: datetime | None
    └── archive_reason: str | None
```

### 2.3 Decay Model

Memories decay using an Ebbinghaus-inspired formula with access frequency and importance correction:

```
base_decay = exp(-decay_rate × age_days)
access_boost = 1.0 + 0.1 × ln(1 + access_count_30d)
importance_factor = 0.5 + 0.5 × importance_score

decay_score = min(1.0, base_decay × access_boost × importance_factor)
```

Decay tiers determine retrieval priority:
- **Active** (> 0.4): Readily retrieved, full content available
- **Warm** (0.2–0.4): Retrievable but deprioritized
- **Archive** (< 0.2): Excluded from normal search, available on explicit request

### 2.4 Confidence Model

Confidence is updated via Bayesian evidence:

| Evidence Type | Effect |
|---------------|--------|
| `corroborating_source` | +0.10 (independent) or +0.05 |
| `contradicting_source` | -0.10 (independent) or -0.05 |
| `user_explicit_correction` | Forces to specified value |
| `repeated_access` | +0.02 |
| `passage_of_time` | -0.01 |
| `relation_derived` | +0.03 |

Independent sources have double weight. Confidence is clamped to [0.0, 1.0].

---

## 3. Service Architecture

### 3.1 Service Layer

Each external system is abstracted behind an async service class with a corresponding mock for testing:

| Service | Backend | Mock | Purpose |
|---------|---------|------|---------|
| `SearchService` | Elasticsearch 8.17 | `MockSearchService` (in-memory dict) | BM25 + kNN + hybrid search, CRUD |
| `EmbeddingService` | Gemini `gemini-embedding-2-preview` | `MockEmbeddingService` (SHA256 hash) | 3072-dim text vectorization |
| `LLMService` | Gemini `gemini-3.1-flash-lite-preview` | `MockLLMService` (deterministic) | Reasoning, classification, enrichment |
| `GraphService` | Neo4j 5 | `MockGraphService` (in-memory) | Relationship graph, traversal |
| `StorageService` | GCS / MinIO (S3-compat) | `MockStorageService` (in-memory) | Content blob persistence |
| `WorkingMemoryService` | Redis 7 | `MockWorkingMemoryService` (in-memory) | Session context, turn streams, caches |

### 3.2 Dependency Injection

Services are instantiated via `api/deps.py` using `@lru_cache` singletons. Feature flags control mock/real selection:

```python
USE_MOCK_LLM=true   → MockLLMService, MockEmbeddingService
USE_MOCK_SEARCH=true → MockSearchService, MockStorageService, MockGraphService, MockWorkingMemoryService
```

This allows fully offline development with `make dev` + both flags set to `true`.

### 3.3 Elasticsearch Index

A single index (`dse-memories`) stores all memory records with this mapping:

| Field | ES Type | Purpose |
|-------|---------|---------|
| `summary` | `text` (BM25, boost 3x) | Full-text search, high relevance weight |
| `content_text` | `text` (BM25) | Full-text search |
| `embedding` | `dense_vector` (3072, cosine, kNN) | Semantic vector search |
| `namespace` | `keyword` | Namespace filtering |
| `memory_type` | `keyword` | Type filtering |
| `is_archived` | `boolean` | Archive filtering |
| `confidence`, `decay_score`, `importance_score` | `float` | Range queries, aggregations |
| `tags`, `entities` | `keyword` | Faceted filtering |
| `created_at`, `updated_at` | `date` | Temporal queries |

The index is auto-created on first connection with 1 shard, 0 replicas (local dev). Production would scale shards by namespace.

---

## 4. Write Path

### 4.1 Synchronous Write (API / MCP)

The `POST /v1/memories` endpoint and MCP `store_memory` tool follow this flow:

```
Content Text
    │
    ▼
┌─────────────────────┐
│  LLM Enrichment     │  enrich_memory() → summary, tags, entities, importance
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Embedding          │  encode("{summary} {entities}") → float[3072]
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Search Index       │  Elasticsearch upsert (text + vector)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Knowledge Graph    │  Neo4j node registration
└─────────────────────┘
```

### 4.2 Saga Write (Temporal Workflow)

The `MemoryWriteWorkflow` provides the full production write path with compensations:

```
Phase 1: store_to_object_storage      → GCS/MinIO (source of truth)
Phase 2: generate_embedding           → Gemini Embedding API
Phase 3: upsert_search_index          → Elasticsearch
Phase 4: register_graph_node          → Neo4j
Phase 5: initialize_provenance        → Object Storage (lineage record)
Phase 6: ContradictionCheckWorkflow   → Child workflow (async)
         ├── search_contradiction_candidates
         ├── llm_judge_contradiction (per candidate)
         └── auto_resolve OR enqueue_manual_resolution
```

Each phase has an independent retry policy (3 attempts, exponential backoff). Failure at any phase doesn't roll back prior phases — the saga pattern ensures eventual consistency through idempotent retries.

---

## 5. Read Path — Cascade Retrieval

The retrieval pipeline is the core of DSE. It uses a 3-stage cascade where each stage adds precision at the cost of latency:

```
┌─────────────────────────────────────────────────────────┐
│                   Query Preprocessing                    │
│  Raw query → LLM intent extraction → query expansion    │
│  → embedding generation → stage selection               │
└────────────────────────┬────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌──────────┐  ┌────────────┐  ┌──────────┐
    │  FAST    │  │ PRECISION  │  │   DEEP   │
    │  <50ms   │  │  <200ms    │  │  <1000ms │
    │          │  │            │  │          │
    │ ANN vec  │  │ BM25 text  │  │Precision │
    │ search   │  │ + kNN vec  │  │+ Graph   │
    │          │  │ + RRF      │  │expansion │
    └────┬─────┘  └─────┬──────┘  └────┬─────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
              ┌──────────────────┐
              │  Context Assembly │
              │  Token budgeting  │
              │  Tier selection   │
              └──────────────────┘
```

### 5.1 Query Preprocessing

1. **Intent extraction** (LLM): Extracts `primary_intent`, `memory_types`, `entities`, `time_range`, `urgency`
2. **Query expansion**: Generates 2–3 query variants (original + intent + entity-focused) for better recall
3. **Embedding**: Encodes the enriched intent string via `encode_query()` with `RETRIEVAL_QUERY` task type
4. **Stage selection**: Maps urgency to cascade stage:
   - `high` urgency → FAST (agent needs immediate answer)
   - `medium` → PRECISION (default)
   - `low` → DEEP (complex reasoning task)
5. **Exploration factor**: Adjusted by task context (0.20 for creative tasks, 0.02 for debugging, 0.05 default)

### 5.2 Stage Details

**Stage 1 — Fast** (< 50ms):
- Single vector-based search via Elasticsearch
- No re-ranking, no graph expansion
- Best for: High-urgency queries, cache-friendly patterns

**Stage 2 — Precision** (< 200ms):
- BM25 full-text search on primary query
- Vector search on expanded query variants
- Results merged via Reciprocal Rank Fusion (RRF)
- Multi-factor re-ranking applied
- Best for: Most queries (default)

**Stage 3 — Deep** (< 1000ms):
- Starts with Precision results
- Graph expansion: Takes top-5 results, traverses Neo4j neighbors (1 hop, max 3 per node)
- Excludes `CONTRADICTS` edges from expansion
- Graph-sourced results get 0.6x score discount
- Deduplication by memory ID
- Best for: Complex reasoning, when relationships matter

---

## 6. Ranking and Scoring

### 6.1 Reciprocal Rank Fusion (RRF)

BM25 and vector results are merged using RRF to avoid bias toward either ranking method:

```
rrf_score(doc) = Σ  1 / (K + rank_i(doc) + 1)
                 i

where K = 60 (smoothing constant)
```

A document ranked #1 in BM25 and #3 in vector search gets:
`1/(60+0+1) + 1/(60+2+1) = 0.01639 + 0.01587 = 0.03226`

### 6.2 Multi-Factor Final Score

After RRF, each result is scored using five factors:

```
final_score = (
    relevance_weight × rrf_score        # 0.5 — search relevance
  + quality_weight × (confidence × decay) # 0.3 — trust × freshness
  + temporal_weight × recency            # 0.2 — time proximity
  + exploration_factor × exploration     # 0.02–0.20 — diversity bonus
) × superseded_penalty                   # 0.1 if superseded, else 1.0
  × contradiction_penalty                # 0.3 if contradicted/pending, else 1.0
```

**Recency** uses a sigmoid function with a 168-hour (1-week) half-life:
```
recency = 1 / (1 + ln(age_hours / 168))
```

**Exploration bonus** encourages diversity by boosting less-accessed memories:
```
exploration = factor / (1 + access_count_30d)
```

---

## 7. Context Assembly

After ranking, results are assembled into a token-budgeted context package.

### 7.1 Tier Selection

Each result is assigned a content tier based on its score and the remaining token budget:

| Tier | Condition | Content | Token Cost |
|------|-----------|---------|------------|
| **Tier 3** (Full) | score > 0.8, budget >= 500, has content_path | Full content from object storage | Variable |
| **Tier 2** (Summary) | budget >= 100 | `record.summary` (≤500 chars) | ~250 tokens |
| **Tier 1** (Reference) | budget >= 20 | `"[TYPE] ID: summary_excerpt"` | ~20 tokens |
| **Truncated** | insufficient budget | Content truncated to fit | Remaining budget |

Token estimation: 2 characters per token (Japanese text assumption).

### 7.2 Output Format

```json
{
  "items": [
    {
      "memory_id": "uuid",
      "memory_type": "semantic",
      "content": "Full text or summary...",
      "tier": "full",
      "score": 0.847,
      "confidence": 0.92,
      "created_at": "2026-03-10T...",
      "tokens": 312
    }
  ],
  "total_tokens": 2847,
  "query": "original query",
  "namespace": "agent:alice"
}
```

---

## 8. Knowledge Graph

### 8.1 Node Model

Each memory is represented as a `Memory` node in Neo4j with properties: `id`, `namespace`, `memory_type`, `confidence`, `importance`, `verification_status`, `is_archived`, `created_at`, `updated_at`.

### 8.2 Relationship Types

DSE uses 8 directed edge types:

| Edge | Meaning | Created By |
|------|---------|------------|
| `SUPERSEDED_BY` | A is outdated, replaced by B | Contradiction resolution |
| `COMPLEMENTS` | A and B provide complementary info | Contradiction check / Discovery |
| `CONTRADICTS` | A and B are contradictory | Contradiction check |
| `DERIVES` | A was derived from B (compression, inference) | Semantic compression |
| `CAUSES` | A causally led to B | Relation discovery (LLM) |
| `REFERENCES` | A references B without causal link | Relation discovery (LLM) |
| `HAS_CHILD` | A is the parent of B (hierarchical) | Explicit creation |
| `TEMPORALLY_PRECEDES` | A occurred before B within a time window | Allen's Interval Algebra |

Each edge carries `confidence`, `strength`, `created_at`, `created_by`, and `method` properties.

### 8.3 Graph Queries

- **Neighbor traversal**: Variable hop depth (1–3), excludable edge types, sorted by strength
- **Contradiction pairs**: Bidirectional `CONTRADICTS` edges within a namespace
- **Lineage tracing**: Follows `DERIVES` chains up to 5 hops
- **Subgraph visualization**: Edge-first query strategy (find edges, then collect endpoint nodes)

### 8.4 Schema

```cypher
CREATE CONSTRAINT memory_id_unique FOR (m:Memory) REQUIRE m.id IS UNIQUE;
CREATE INDEX memory_namespace FOR (m:Memory) ON (m.namespace);
CREATE INDEX memory_type_idx FOR (m:Memory) ON (m.memory_type);
CREATE INDEX memory_created_at FOR (m:Memory) ON (m.created_at);
CREATE INDEX memory_confidence FOR (m:Memory) ON (m.confidence);
CREATE INDEX memory_is_archived FOR (m:Memory) ON (m.is_archived);
```

---

## 9. Intelligence Layer

The intelligence layer runs as scheduled Temporal workflows to autonomously improve memory quality.

### 9.1 Semantic Compression

**Schedule**: Weekly | **Queue**: `dse-maintenance`

Distills clusters of episodic memories into generalized semantic knowledge.

```
Episodic memories (30-day window)
    │
    ▼
HDBSCAN clustering (embedding similarity)
    │
    ▼
Per cluster (min_size=5, avg_confidence ≥ 0.70):
    │
    ├── LLM generalization → semantic summary
    ├── Embedding generation → new vector
    ├── Create MemoryRecord (type=SEMANTIC, subtype=compressed)
    ├── Create DERIVES edges from semantic → each episode
    └── Decay source episode importance (× 0.5)
```

Idempotent: checks for existing similar semantic memories before creating duplicates.

### 9.2 Relation Discovery

**Schedule**: Daily | **Queue**: `dse-discovery`

Finds latent relationships between memories using embedding similarity + LLM classification.

```
All non-archived memories
    │
    ▼
ANN candidate pairs (cosine similarity > 0.75, max 200 pairs)
    │
    ▼
Filter: skip pairs that already have edges
    │
    ▼
Per pair: LLM classification → SUPERSEDES | COMPLEMENTS | CONTRADICTS |
                                DERIVES | CAUSES | REFERENCES | NONE
    │
    ▼
Create edges (confidence ≥ 0.70)
```

### 9.3 Temporal Reasoning

**Schedule**: Daily | **Queue**: `dse-discovery`

Uses Allen's Interval Algebra to classify time relationships between memories and create `TEMPORALLY_PRECEDES` edges.

The 13 Allen relations (BEFORE, MEETS, OVERLAPS, STARTS, DURING, FINISHES, EQUAL, and their inverses) are classified for memory pairs within a configurable time window (default 7 days). Only `BEFORE` and `MEETS` relations create edges.

### 9.4 Prospective Memory

**Schedule**: Every 1 minute | **Queue**: `dse-main`

Scans for prospective memories whose trigger conditions are met:

| Trigger Type | Condition |
|-------------|-----------|
| `time` | `trigger_at <= now` |
| `event` | External event match (via CDC) |
| `condition` | LLM evaluation of natural language condition |

When fired: `is_triggered = true`, events published to Kafka. Auto-archives after `prospective_archive_after_days` (default 7).

### 9.5 Importance Estimation

Multi-signal importance scoring combines three categories:

**Content signals** (LLM-assessed):
- Contains decision, error correction, user preference, factual claim, deadline

**Behavior signals** (access-pattern-based):
- User explicitly stored, re-referenced, used in successful/failed task

**Structural signals** (graph-based):
- Number of dependent memories (DERIVES edges)
- Uniqueness within namespace

Scores are weighted and combined with a baseline of 0.5, clamped to [importance_score_min, importance_score_max].

### 9.6 Daily Maintenance

**Schedule**: Daily | **Queue**: `dse-maintenance`

1. **Decay update**: Recomputes `decay_score` for all active memories using the Ebbinghaus formula
2. **Archiving**: Memories with `decay_score < 0.2` are moved to archived state

---

## 10. Working Memory

Working memory provides short-term, session-scoped storage backed by Redis.

### 10.1 Session Context

Key-value storage with TTL (default 7200s):
```
working_memory:{session_id}:context → JSON blob (agent state, preferences)
```

### 10.2 Conversation Turns

Redis Streams for ordered turn history:
```
working_memory:{session_id}:turns → Stream (max 200 entries)
  Each entry: { role: "user"|"assistant"|"system", content: "..." }
```

### 10.3 Caching

| Cache | Key Pattern | TTL |
|-------|-------------|-----|
| Search results | `cache:search:{query_hash}` | 300s |
| Embeddings | `cache:embedding:{text_hash}` | 300s |
| Memory records | `cache:memory:{memory_id}` | 300s |

### 10.4 Persistence Decision

The MMA agent can snapshot a session for persistence:
```python
snapshot = await cache.snapshot_for_persistence(session_id)
# Returns: { session_id, context, turns[] }
# Agent decides which turns to promote to long-term memory
```

---

## 11. MCP Interface

DSE exposes a [Model Context Protocol](https://modelcontextprotocol.io/) server so AI agents can interact with memories through a standardized interface.

### 11.1 Transport

| Mode | Command | Use Case |
|------|---------|----------|
| stdio | `make mcp` | Claude Desktop, Claude Code, local agents |
| streamable-http | `make mcp-http` (port 8001) | Remote agents, multi-client |

### 11.2 Tools (14)

| Category | Tools |
|----------|-------|
| Retrieval | `retrieve_memories`, `search_memories` |
| CRUD | `store_memory`, `get_memory`, `update_memory`, `delete_memory` |
| Namespace | `list_namespaces`, `get_namespace`, `create_namespace`, `delete_namespace` |
| Graph | `get_related_memories`, `create_memory_relation` |
| Working Memory | `working_memory_add`, `working_memory_get` |

### 11.3 Resources

| URI | Description |
|-----|-------------|
| `dse://memories/{memory_id}` | Read a memory record |
| `dse://graph/{memory_id}/neighbors` | Read graph neighbors |

### 11.4 Prompts

| Name | Description |
|------|-------------|
| `memory_context` | Retrieves memories and formats as an injectable context block |

### 11.5 LLM Enrichment on Store

When `store_memory` is called with just `namespace` and `content_text`, the MCP server automatically:
1. Calls `llm.enrich_memory()` to infer summary, tags, entities, importance, and memory_type
2. Generates embedding from `"{summary} {entities}"`
3. Indexes in Elasticsearch and registers in Neo4j

Explicitly provided fields take precedence over LLM-inferred values.

---

## 12. Agent Framework

### 12.1 Memory Management Agent (MMA)

Built on Google ADK, the MMA is responsible for memory lifecycle operations:

**Tools**:
- `store_memory_tool`: Store with duplicate/contradiction checking
- `detect_contradiction_tool` / `resolve_contradiction_tool`: Conflict management
- `classify_relation_tool` / `create_relation_tool`: Relationship management
- `update_confidence_tool`: Evidence-based confidence updates
- `record_provenance_tool`: Lineage tracking

### 12.2 Retrieval Agent

A read-only agent that determines the best retrieval strategy:
- Selects cascade stage based on query complexity
- Configures token budget based on task requirements
- Returns assembled context for injection into the calling agent's prompt

### 12.3 Memory-Augmented ReAct Middleware

The `DSEMemoryMiddleware` wraps any agent in a memory-augmented ReAct loop:

```
Think → Retrieve relevant memories → Act → Store results as new memories
```

This middleware:
- Injects memory context before the agent's thinking step
- Captures action results and decides whether to persist them
- Manages the working memory session lifecycle

---

## 13. Temporal Workflows

### 13.1 Workflow Registry

| Workflow | Trigger | Queue | Timeout |
|----------|---------|-------|---------|
| `MemoryWriteWorkflow` | On memory create | `dse-main` | 30–60s per phase |
| `ContradictionCheckWorkflow` | Child of MemoryWrite | `dse-main` | 60s per activity |
| `ProspectiveScanWorkflow` | Every 1 min | `dse-main` | 30s |
| `DailyMaintenanceWorkflow` | Every 1 day | `dse-maintenance` | 10 min |
| `P3SemanticCompressionWorkflow` | Every 1 week | `dse-maintenance` | 30 min |
| `P3RelationDiscoveryWorkflow` | Every 1 day | `dse-discovery` | 15 min |
| `TemporalEdgeBuildWorkflow` | Every 1 day | `dse-discovery` | 15 min |

### 13.2 Task Queues

Three queues separate concerns and allow independent scaling:

| Queue | Purpose | Typical Load |
|-------|---------|-------------|
| `dse-main` | Real-time operations (writes, scans) | High throughput |
| `dse-maintenance` | Batch maintenance (decay, compression) | Nightly/weekly |
| `dse-discovery` | Analytical jobs (relation discovery, temporal edges) | Daily |

### 13.3 Worker

A single worker process polls all three queues concurrently using `asyncio.TaskGroup`. All workflows and all activities are registered on every worker instance.

### 13.4 Schedule Registration

`make register-schedules` auto-discovers namespaces from Elasticsearch and registers per-namespace schedules for all recurring workflows. `--force` flag recreates existing schedules.

---

## 14. Infrastructure

### 14.1 PII Guard

Content is screened before storage using regex-based detection:

| PII Type | Pattern |
|----------|---------|
| Email | RFC-like email pattern |
| Phone (JP) | `(+81|0)\d{9,10}` |
| Credit Card | 16-digit with separators |
| My Number (JP) | 12-digit |
| IP Address | Quad-dotted decimal |

Three handling policies:
- **BLOCK**: Reject the request with `PIIDetectedError` (422)
- **ANONYMIZE**: Replace with `[EMAIL_REDACTED]`, `[PHONE_REDACTED]`, etc.
- **TOKENIZE**: Replace with reversible tokens `[PII_TOKEN_EMAIL_1]`

### 14.2 Provenance Tracking

Stored separately from the search index in object storage (`provenance/{namespace}/{memory_id}.json`):

```json
{
  "memory_id": "uuid",
  "created_by": { "step": "ingestion", "performed_by": "agent:alice", ... },
  "transformations": [
    { "step": "semantic_compression", "model_used": "gemini-3.1-flash", ... }
  ],
  "access_log": [
    { "accessed_by": "agent:bob", "utility_score": 0.85, ... }
  ]
}
```

Access log is capped at 500 entries (rolling buffer).

### 14.3 Event Bus

Memory lifecycle events are published to Kafka/Redpanda for downstream consumers:

| Event | Topic | Key |
|-------|-------|-----|
| `memory.created` | `dse.memory.events` | `memory_id` |
| `memory.updated` | `dse.memory.events` | `memory_id` |
| `memory.deleted` | `dse.memory.events` | `memory_id` |
| `memory.accessed` | `dse.memory.events` | `memory_id` |

CDC events from external systems flow through `dse.cdc.events` and can trigger memory creation.

### 14.4 Logging

All backend code uses `structlog` with structured fields:

- **Local**: Human-readable `ConsoleRenderer`
- **Production**: JSON `JSONRenderer`

Standard fields: `event`, `memory_id`, `namespace`, `memory_type`, `error`.

---

## 15. Frontend Dashboard

A Next.js 15 admin dashboard with 8 pages:

| Page | Purpose | Key Components |
|------|---------|----------------|
| Dashboard | Stats overview | Stat cards, type distribution badges |
| Memories | Search and retrieve | Cascade search, result list, detail panel |
| Graph | Knowledge graph visualization | React Flow, custom nodes/edges, edge legend, detail panels |
| Conflicts | Contradiction resolution | Side-by-side comparison, keep A/B/both |
| Curation | Memory management | Browser (filter/sort/edit/pin/forget), compression, prospective, analytics |
| Intelligence | Autonomous improvement monitoring | Importance heatmap, compression history, discovery log |
| Workflows | Temporal workflow status | Static workflow descriptions |
| Settings | Namespace and service management | Create/delete namespaces, service status links |

### 15.1 State Management

| Layer | Technology | Scope |
|-------|-----------|-------|
| Server data | TanStack Query v5 | API data fetching, caching, refetching |
| Global UI state | Zustand | Namespace selection, font size preference |
| Local UI state | React `useState` | Filter selections, form inputs, panel toggles |

### 15.2 Global Namespace Selector

The sidebar contains a namespace dropdown (Zustand store) that auto-fetches available namespaces every 30s. All pages read from this global store — no per-page namespace inputs.

---

## 16. Configuration and Feature Flags

### 16.1 Environment Variables

All configuration is via environment variables loaded through `pydantic-settings` (with `.env` file support). See `.env.example` for the full list (40+ variables).

### 16.2 Key Feature Flags

| Flag | Default | Effect |
|------|---------|--------|
| `USE_MOCK_LLM` | `false` | Replace Gemini with deterministic mock (no API key needed) |
| `USE_MOCK_SEARCH` | `false` | Replace ES, Neo4j, Redis, GCS with in-memory mocks |
| `APP_ENV` | `local` | Controls logging format, production validations |

### 16.3 Algorithm Tuning

| Parameter | Default | Controls |
|-----------|---------|----------|
| `contradiction_cosine_threshold` | 0.92 | Similarity threshold for contradiction candidates |
| `contradiction_auto_resolve_confidence_delta` | 0.30 | Min confidence gap for auto-resolution |
| `compression_min_cluster_size` | 5 | Minimum episodes to form a compression cluster |
| `compression_similarity_threshold` | 0.75 | Embedding similarity for clustering |
| `discovery_similarity_threshold` | 0.75 | Embedding similarity for relation candidates |
| `discovery_min_llm_confidence` | 0.70 | Min LLM confidence to create a discovered edge |
| `temporal_window_days` | 7 | Time window for Allen's Interval Algebra |
| `importance_user_access_recovery` | 0.15 | Decay recovery on user access |
| `importance_agent_access_recovery` | 0.05 | Decay recovery on agent access |

---

## 17. Testing Strategy

### 17.1 Unit Tests (237+)

All external services mocked. Covers:
- API routers (memories, retrieve, graph, conflicts, curation, working memory, namespaces, MCP info)
- Domain models and enums
- Pipeline stages (preprocessing, ranking, assembly)
- Intelligence modules (importance, prospective, Allen intervals)
- Service mocks (search, graph, cache, embedding, LLM, PII, provenance, events, confidence)
- MCP server tools

### 17.2 Integration Tests

Run against real Docker services (`make test-int`):
- Elasticsearch index creation and search
- Neo4j constraint creation and graph queries
- Redis session management

### 17.3 Mock Architecture

Every service has a mock that implements the same interface:
- `MockSearchService`: In-memory dict with substring matching
- `MockEmbeddingService`: Deterministic SHA256-based vectors (3072-dim)
- `MockLLMService`: Returns predictable structured responses
- `MockGraphService`: In-memory node/edge lists
- `MockStorageService`: In-memory blob store
- `MockWorkingMemoryService`: In-memory session state

Tests force mock mode via `conftest.py`:
```python
os.environ["USE_MOCK_LLM"] = "true"
os.environ["USE_MOCK_SEARCH"] = "true"
```

---

## 18. Deployment Topology

### 18.1 Local Development

```
make run-all
```

Runs everything on a single machine:
- 9 Docker containers (ES, Neo4j, Redis, Postgres, Temporal, Temporal UI, MinIO, Redpanda, Redpanda Console)
- FastAPI server (port 8000, hot reload)
- Temporal worker (polls all 3 queues)
- MCP server (port 8001, streamable-http)
- Next.js dev server (port 3000)

### 18.2 Production (Target)

```
                        ┌──────────────┐
                        │   Load       │
                        │   Balancer   │
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌──────────┐    ┌──────────┐    ┌──────────┐
       │ API Pod  │    │ API Pod  │    │ API Pod  │
       │ (FastAPI)│    │ (FastAPI)│    │ (FastAPI)│
       └──────────┘    └──────────┘    └──────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ Elasticsearch│   │   Neo4j      │   │   Redis      │
  │ Cluster      │   │   (HA)       │   │   Cluster    │
  └──────────────┘   └──────────────┘   └──────────────┘

  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ Temporal     │   │ GCS          │   │ Kafka /      │
  │ Server       │   │              │   │ Redpanda     │
  └──────────────┘   └──────────────┘   └──────────────┘

  Workers (auto-scaled per queue):
  ┌──────────┐  ┌──────────────┐  ┌──────────────┐
  │dse-main  │  │dse-maintenance│  │dse-discovery │
  │ worker×N │  │  worker×1     │  │  worker×1    │
  └──────────┘  └──────────────┘  └──────────────┘
```

Key scaling considerations:
- **API pods**: Stateless, horizontally scalable behind a load balancer
- **Workers**: `dse-main` scales with write throughput; `dse-maintenance` and `dse-discovery` run as singletons
- **Elasticsearch**: Shard by namespace for multi-tenant isolation
- **Neo4j**: Read replicas for graph traversal queries
- **Redis**: Cluster mode for working memory across API pods
