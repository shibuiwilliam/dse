# Dynamic Search Engine for Agentic Memory (DSE) — Design Report

> **Version**: 1.0
> **Date**: 2026-03-19
> **Status**: Design Draft

---

## Table of Contents

1. [Overview and Vision](#1-overview-and-vision)
2. [System Architecture](#2-system-architecture)
3. [Core Component Design](#3-core-component-design)
   - 3.1 Search Index Design
   - 3.2 Object Storage Design
   - 3.3 Graph Database Design
   - 3.4 Memory Management Agent Design
4. [Challenges and Solutions](#4-challenges-and-solutions)
5. [Complementary Technologies](#5-complementary-technologies)
6. [Missing Technologies and Their Design](#6-missing-technologies-and-their-design)
7. [Memory Lifecycle Design](#7-memory-lifecycle-design)
8. [Search Pipeline Design](#8-search-pipeline-design)
9. [Graph Structure and Relationship Design](#9-graph-structure-and-relationship-design)
10. [Security and Access Control](#10-security-and-access-control)
11. [Scalability and Operations Design](#11-scalability-and-operations-design)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Appendix: Schema and Query Reference](#13-appendix-schema-and-query-reference)

---

## 1. Overview and Vision

### 1.1 What is DSE?

Dynamic Search Engine for Agentic Memory (DSE) is an architecture that implements an AI agent's memory system as a search engine. Unlike traditional RAG (Retrieval-Augmented Generation), which retrieves documents in response to user queries, DSE provides a foundation for dynamically searching and managing an agent's own "memories" — past experiences, learned knowledge, and execution procedures.

The essential value of implementing DSE as a search engine lies in three areas:

**Scalability**: Instead of stuffing all memories into an LLM's context window, only the needed memories are dynamically retrieved. Context costs remain constant regardless of how much total memory accumulates.

**Diverse Search Modes**: By combining full-text search (keyword matching), vector search (semantic similarity), hybrid search, and graph traversal (relationship exploration), DSE enables flexible memory recall that closely mirrors human memory retrieval.

**Dynamic Memory Updates**: Memories can be updated and reorganized in real-time in response to agent actions, user feedback, and changes in external data. This functions as "living memory" — fundamentally different from a static vector database.

### 1.2 Memory Classification

DSE adopts memory classifications from cognitive science:

| Type | Definition | Example |
|------|-----------|---------|
| **Semantic memory** | Concepts, facts, knowledge | "Python is an interpreted language" |
| **Episodic memory** | Specific events, experiences | "On 2026-03-10, discussed AWS cost optimization with the user" |
| **Procedural memory** | Procedures, skills, rules | "Always check test coverage during code review" |
| **Prospective memory** | Future plans, intentions | "Check Project X progress on next login" (see extension below) |

### 1.3 Design Principles

- **Retrieval-First**: Memory usage always goes through search. Do not rely on the LLM's parametric memory.
- **Provenance Tracking**: Every memory can be traced back to its origin.
- **Graceful Degradation**: Even if search fails or times out, the agent continues operating with an empty context.
- **Privacy by Design**: Memories are strictly isolated by agent, user, and project namespace.
- **Evolvability**: Memories have a lifecycle of creation, updating, compression, deletion, and archiving.

---

## 2. System Architecture

### 2.1 System Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI Agent Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Task Agent  │  │  Chat Agent  │  │  Memory Mgmt Agent     │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────┘ │
└─────────┼────────────────┼──────────────────────┼──────────────┘
          │                │   Memory API          │
          ▼                ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DSE Gateway (Memory API)                      │
│  - Intent extraction   - Query routing   - Context assembly     │
│  - Access control      - Cache layer     - Feedback recording   │
└───────┬──────────────────┬───────────────────────┬─────────────┘
        │                  │                       │
        ▼                  ▼                       ▼
┌──────────────┐  ┌────────────────────┐  ┌────────────────────┐
│ Search Index │  │  Object Storage    │  │   Graph Database   │
│              │  │                    │  │                    │
│ - Full-text  │  │ - Text records     │  │ - Memory nodes     │
│ - Vector     │  │ - Images/docs      │  │ - Relation edges   │
│ - Hybrid     │  │ - Audio/video      │  │ - Temporal links   │
│ - Tags/facet │  │ - Embeddings cache │  │ - Causal DAG       │
└──────┬───────┘  └─────────┬──────────┘  └─────────┬──────────┘
       │                    │                        │
       └────────────────────┴────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │   Update Pipeline (CDC)     │
              │  Kafka / Pub-Sub stream     │
              │  - Change detection         │
              │  - Re-indexing trigger       │
              │  - Relation discovery        │
              └─────────────────────────────┘
```

### 2.2 Data Flow

**Memory Retrieval (Read Path)**:

```
1. Agent → DSE Gateway: "retrieve memory for context X"
2. DSE Gateway: intent extraction → query formulation
3. Search Index: hybrid search (BM25 + vector) → Top-N candidates
4. Graph DB: expand 1-hop relations for each candidate
5. Ranking Engine: re-rank by relevance × confidence × recency
6. Object Storage: fetch content for Top-K results
7. Context Assembly: select full / summary / reference per token budget
8. → Agent: structured context with provenance metadata
```

**Memory Storage (Write Path)**:

```
1. Agent → DSE Gateway: "store memory M"
2. Preprocessing: content normalization, PII detection
3. Embedding Service: generate embedding vector
4. Conflict Detection: cosine similarity check against existing records
5. Search Index: upsert record
6. Graph DB: register node + detect new relations
7. Object Storage: persist content
8. CDC Event: publish update event to pipeline
```

---

## 3. Core Component Design

### 3.1 Search Index Design

#### Index Schema (Complete)

```json
{
  "id": "uuid-v7",
  "namespace": "agent:alice/project:alpha",

  // Content reference
  "content_path": "gs://dse-bucket/memories/uuid.txt",
  "summary": "Summary within 150 characters. For fast search.",
  "summary_embedding": [0.12, -0.34, ...],

  // Full-text search
  "content_text": "Text for indexing (OCR/captions for images)",

  // Vector search
  "embedding": [0.12, -0.34, ...],
  "embedding_model": "text-embedding-3-large",
  "embedding_version": "2026-01",

  // Memory classification
  "memory_type": "episodic | semantic | procedural | prospective",
  "memory_subtype": "observation | inference | user_explicit | agent_generated",
  "content_type": "text | image | audio | document | code | structured_data",

  // Reliability and quality metadata
  "confidence": 0.92,
  "source_type": "observation | inference | user_explicit | external_api",
  "source_id": "conversation:uuid / task:uuid / external:url",
  "verification_status": "unverified | verified | contradicted | superseded",
  "last_verified_at": "2026-03-19T09:00:00Z",

  // Timestamps
  "created_at": "2026-03-19T09:00:00Z",
  "updated_at": "2026-03-19T09:00:00Z",
  "accessed_at": "2026-03-19T12:00:00Z",
  "expires_at": "2027-03-19T09:00:00Z",

  // Access statistics (for Decay calculation)
  "access_count": 14,
  "access_count_7d": 3,
  "access_count_30d": 8,
  "last_access_utility": 0.85,

  // Decay score (updated via daily batch)
  "decay_score": 0.76,
  "importance_score": 0.90,

  // Relationships
  "superseded_by": "uuid | null",
  "supersedes": ["uuid1", "uuid2"],
  "parent_id": "uuid | null",

  // Tags and facets
  "tags": ["user:alice", "project:alpha", "domain:engineering"],
  "entities": ["AWS", "Lambda", "Python"],
  "language": "ja",

  // Prospective memory fields
  "trigger_type": "time | event | condition | null",
  "trigger_at": "2026-03-20T09:00:00Z",
  "trigger_condition": "project:alpha AND status:blocked",
  "is_triggered": false,

  // Archive
  "is_archived": false,
  "archived_at": "null",
  "archive_reason": "null"
}
```

#### Search Index Technology Comparison

| Criteria | Elasticsearch | Azure AI Search | Vertex AI Search | Recommended |
|----------|--------------|-----------------|-----------------|-------------|
| Hybrid search | Good (RRF) | Excellent (built-in) | Excellent | Azure/Vertex |
| Vector search | Good (kNN) | Excellent | Excellent | Equivalent |
| Custom ranking | Excellent | Good | Limited | Elasticsearch |
| Schema flexibility | Excellent | Good | Limited | Elasticsearch |
| Managed service | Limited | Excellent | Excellent | Azure/Vertex |
| Scale (100M+ docs) | Excellent | Good | Excellent | Elasticsearch/Vertex |

**Recommended configuration**: Elasticsearch for early development (flexibility priority); Azure AI Search or Vertex AI Search for enterprise deployment (managed service + security priority).

### 3.2 Object Storage Design

#### Directory Structure

```
gs://dse-bucket/
├── memories/
│   ├── {namespace}/
│   │   ├── {uuid}.txt          # Text memory
│   │   ├── {uuid}.json         # Structured data
│   │   ├── {uuid}.md           # Markdown record
│   │   └── {uuid}/             # Compound content
│   │       ├── content.txt
│   │       ├── image_01.png
│   │       └── metadata.json
├── embeddings/
│   └── {uuid}.npy              # Cached embedding
├── archives/
│   └── {namespace}/
│       └── {uuid}.gz           # Compressed archive
└── temp/
    └── {session_id}/           # Volatile working area
```

#### Metadata File (metadata.json)

Human-readable metadata accompanying each memory record's source data:

```json
{
  "id": "uuid",
  "title": "AWS Lambda Cost Optimization Discussion",
  "created_at": "2026-03-19T09:00:00Z",
  "source": {
    "type": "conversation",
    "session_id": "conv:uuid",
    "agent_id": "agent:alice-assistant",
    "user_id": "user:alice"
  },
  "provenance": [
    {
      "step": "observation",
      "timestamp": "2026-03-19T09:01:00Z",
      "description": "User asked about Lambda cost reduction"
    },
    {
      "step": "extraction",
      "timestamp": "2026-03-19T09:05:00Z",
      "description": "Agent extracted and recorded key points"
    }
  ],
  "related_files": ["image_01.png"],
  "checksum": "sha256:abc123..."
}
```

### 3.3 Graph Database Design

#### Node and Edge Schema

The Graph DB manages only relationships between memories. Content is held by Object Storage.

**Node (Memory Node)**:

```cypher
CREATE (m:Memory {
  id: "uuid",
  memory_type: "episodic",
  namespace: "agent:alice",
  created_at: datetime("2026-03-19T09:00:00Z"),
  confidence: 0.92,
  importance: 0.85
})
```

**Edges (Relation Edges)**:

```cypher
// Update relationship: A became outdated, replaced by B
(:Memory {id:"A"})-[:SUPERSEDED_BY {updated_at: datetime()}]->(:Memory {id:"B"})

// Complementary relationship: A and B together form complete understanding
(:Memory {id:"A"})-[:COMPLEMENTS {strength: 0.8}]->(:Memory {id:"B"})

// Contradiction relationship: A and B hold conflicting information
(:Memory {id:"A"})-[:CONTRADICTS {detected_at: datetime()}]->(:Memory {id:"B"})

// Derivation relationship: B was inferred/extracted from A
(:Memory {id:"A"})-[:DERIVES {method: "summarization"}]->(:Memory {id:"B"})

// Temporal relationship: A occurred before B
(:Memory {id:"A"})-[:TEMPORALLY_PRECEDES {interval_ms: 86400000}]->(:Memory {id:"B"})

// Causal relationship: A caused B
(:Memory {id:"A"})-[:CAUSES {confidence: 0.7}]->(:Memory {id:"B"})

// Parent-child relationship: B is part of A (hierarchical)
(:Memory {id:"A"})-[:HAS_CHILD {order: 1}]->(:Memory {id:"B"})

// Reference relationship: A references/cites B
(:Memory {id:"A"})-[:REFERENCES {context: "cited as evidence"}]->(:Memory {id:"B"})
```

#### Graph Traversal Query Patterns

**1-hop neighbor expansion (context enrichment of search results)**:

```cypher
MATCH (m:Memory {id: $retrieved_id})
OPTIONAL MATCH (m)-[r]-(related:Memory)
WHERE NOT r:CONTRADICTS AND NOT related.is_archived = true
RETURN m, related, type(r) as relation_type, r.strength as strength
ORDER BY r.strength DESC
LIMIT 5
```

**Contradiction detection**:

```cypher
MATCH (a:Memory)-[:CONTRADICTS]-(b:Memory)
WHERE a.namespace = $namespace
  AND a.confidence > 0.5 AND b.confidence > 0.5
RETURN a.id, b.id, a.summary, b.summary
```

**Memory lineage tracing**:

```cypher
MATCH path = (root:Memory {id: $id})-[:DERIVES*..5]->(leaf:Memory)
RETURN nodes(path) as lineage, length(path) as depth
ORDER BY depth
```

### 3.4 Memory Management Agent Design

The Memory Management Agent (MMA) is a dedicated agent that maintains the quality, freshness, and consistency of DSE's memories. It is completely separated from task agents.

#### MMA Responsibility Matrix

| Task | Trigger | Priority | Implementation |
|------|---------|----------|---------------|
| New memory registration | After agent action | High | Synchronous API |
| Contradiction detection and flagging | On write / daily batch | High | Async Worker |
| Decay score update | Daily batch | Medium | Cron Job |
| Semantic promotion | Weekly batch | Medium | Scheduled Job |
| Archive processing | Decay score < threshold | Low | Weekly batch |
| Relationship discovery | On write / periodic batch | Medium | Background Worker |
| External CDC event processing | Event-driven | High | Kafka Consumer |
| Prospective memory firing | Periodic scan / event | High | Event Scheduler |
| Summary variant generation | On write | Medium | Async Worker |
| Provenance recording | On all writes | High | Synchronous processing |

#### MMA Decision Flow (On Write)

```
[New Content]
        │
        ▼
PII / Sensitive Information Detection
        │
    Detected ────────────────────────► Remove or Reject
        │
        ▼
Embedding Generation
        │
        ▼
Cosine Similarity Search (threshold > 0.92)
        │
    Similar found              No similar found
        │                           │
        ▼                           ▼
LLM Contradiction/Duplicate      Register new record
Judgment
        │
   ┌────┴──────────────┬────────────────┐
   │                   │                │
Same content      Contradiction     Complementary
(Duplicate)            │            information
   │           Set contradiction         │
   ▼           flag on both          Add COMPLEMENTS
Update                records            edge
existing
or set
SUPERSEDES
relationship
```

---

## 4. Challenges and Solutions

### 4.1 Trade-off Between Search Latency and Context Quality

**Challenge**: In real-time agent operations, deeper search increases latency. However, reducing latency sacrifices search quality, creating a risk that agents make decisions with inappropriate context.

**Solution: Cascade Retrieval (Staged Search)**

```
Stage 1: Fast Path (< 50ms)
  - L1 Cache (Redis): recently accessed memories within session
  - Approximate Nearest Neighbor (HNSW): approximate vector search
  - Returns: Top-10 candidates

Stage 2: Precision Path (< 200ms)
  - Exact KNN + BM25 Hybrid
  - Re-ranking by Decay, Confidence, Recency
  - Returns: Top-5 refined results

Stage 3: Deep Path (< 1000ms)
  - Graph traversal (1-2 hops)
  - Cross-memory relation expansion
  - LLM-based context relevance scoring
  - Returns: Final results with deep context
```

Agents specify which stage to use via the `memory_budget_ms` parameter. Urgent tasks use only Stage 1; reasoning tasks utilize Stages 2-3.

### 4.2 Memory Freshness and Staleness

**Challenge**: Past memories diverge from current facts, causing agents to continue referencing outdated information.

**Solution: Time-Decay Scoring**

Based on the Ebbinghaus forgetting curve, with corrections for access frequency, importance, and memory type:

```python
def compute_decay_score(record: MemoryRecord, now: datetime) -> float:
    age_days = (now - record.created_at).days

    # Base decay (episodic decays fast, semantic decays slow)
    decay_rate = {
        "episodic": 0.05,
        "semantic": 0.01,
        "procedural": 0.008,
        "prospective": 0.0  # Does not decay until triggered
    }[record.memory_type]

    base_decay = math.exp(-decay_rate * age_days)

    # Access frequency correction (reinforced each time referenced)
    access_boost = 1.0 + 0.1 * math.log(1 + record.access_count_30d)

    # Importance correction
    importance_factor = 0.5 + 0.5 * record.importance_score

    return min(1.0, base_decay * access_boost * importance_factor)
```

Records with decay score below `0.2` are automatically flagged as archive candidates, and the MMA processes them in periodic batches.

**Archive Layer Design**:

- **Active layer**: decay > 0.4. Included in normal search.
- **Warm layer**: 0.2 < decay <= 0.4. Included in search only when explicitly specified.
- **Archive layer**: decay <= 0.2. Retrievable only by explicit ID. Moved to long-term low-cost storage.

### 4.3 Contradictions and Conflicts Between Memories

**Challenge**: When multiple mutually contradictory memories coexist about the same fact, agents risk using incorrect information.

**Solution: 3-Level Contradiction Resolution Process**

```
Level 1: Automatic Detection
  cosine_similarity(embedding_A, embedding_B) > 0.92
  AND LLM judgment: "Do A and B contradict?" → Yes
  → Add CONTRADICTS edge, set verification_status: "contradicted" on both records

Level 2: Automatic Resolution (Rule-based)
  - Newer record (created_at) overrides older → resolve via SUPERSEDED_BY
  - One-sided high confidence (confidence gap > 0.3) → adopt higher confidence
  - Source is user_explicit → prioritize

Level 3: Escalation
  Cannot auto-resolve → MMA adds to user/operator confirmation queue
  Both records flagged "needs review" until resolved, search scores decayed to 0.3×
```

### 4.4 Graph Traversal Cost

**Challenge**: Search and graph exploration are orthogonal operations; combining both increases latency.

**Solution: Pre-computed Neighborhood Cache**

```
On write (async):
  New memory registration → MMA computes 1-hop neighbors →
  Embeds as neighbor_ids[] field in the Search Index record →
  Graph expansion becomes unnecessary at search time (at the cost of real-time accuracy)

On read:
  If neighbor_ids are stale (newer related records exist) →
  Background re-query Graph DB → update neighbor_ids
```

For cases requiring deep exploration, agents explicitly specify `graph_depth=2` according to their token budget.

### 4.5 Context Window Management

**Challenge**: Retrieving large amounts of memory overflows the LLM's context window.

**Solution: Tiered Context Assembly**

Each memory record has three levels of content variants:

```
Tier 1: Reference-only (~20 tokens)
  Record ID + title + memory_type only.
  Used as an index for the agent to fetch details later.

Tier 2: Summary (~150 tokens)
  AI-generated summary + key entities + confidence.
  Sufficient for most context references.

Tier 3: Full (variable)
  Full text content. Used only when deep reasoning/verification is needed.
```

Agents pass a `token_budget` to the DSE Gateway, which automatically selects and combines the appropriate tiers to assemble the context.

### 4.6 Consistency Between Index and Source Data

**Challenge**: Object Storage data and Search Index are updated asynchronously, causing consistency drift.

**Solution: Saga Pattern Update Transactions**

```
Phase 1: Write to Object Storage (source of truth)
Phase 2: Generate and cache Embedding
Phase 3: Upsert Search Index
Phase 4: Update Graph DB nodes/edges
Phase 5: Publish CDC event

If any phase fails:
  - Execute compensating transactions to roll back prior phases in reverse order
  - Save failure event to Dead Letter Queue
  - MMA periodically processes DLQ for retries
```

### 4.7 Search Result Bias and Fairness

**Challenge**: Frequently accessed memories always receive high scores, burying useful but rarely referenced memories.

**Solution: Exploration-Exploitation Balance**

```
Scoring formula:
  final_score = alpha * relevance_score
              + beta * (decay_score * confidence)
              + gamma * recency_bonus
              + epsilon * exploration_bonus

exploration_bonus = 1 / (1 + access_count_30d)
  # Lower access count yields higher exploration bonus

epsilon varies by task type:
  - Normal task: epsilon = 0.05 (stability priority)
  - Creative task: epsilon = 0.20 (diversity priority)
  - Debug task: epsilon = 0.02 (track record priority)
```

### 4.8 Embedding Model Obsolescence

**Challenge**: When the embedding model is upgraded, existing vectors and new version vectors cannot be compared in the same space (Vector Space Mismatch).

**Solution: Versioned Gradual Migration**

```
1. Add embedding_model / embedding_version fields to index records
2. Add new version to a separate embedding_v2[] field
3. Background batch re-embeds existing records to populate embedding_v2
4. After full migration, overwrite embedding field with v2 / remove old field
5. During migration, search engine performs union search across both embedding versions
```

---

## 5. Complementary Technologies

### 5.1 Working Memory Buffer (Volatile Short-term Memory)

DSE handles persistent memory, but a dedicated short-term memory buffer is needed for transient state management within conversations and tasks. This corresponds to "working memory" in cognitive architecture.

**Design**:

```
Technology: Redis Streams / Apache Kafka
Scope: Within session only (TTL: 30 min to 4 hours)
Stored content:
  - Current task scope
  - Recent conversation context (N turns)
  - Agent's temporary reasoning results
  - Tool call result cache

Rules for DSE write-back at session end:
  - Only promote to long-term memory if importance score > 0.6
  - Importance is assessed automatically by MMA using LLM
  - Items explicitly marked by user are unconditionally promoted
```

**Connection between Working Memory and DSE**:

```
Session start:
  DSE → fetch last N relevant memories → place in Working Memory

During conversation:
  Use only Working Memory (no real-time DSE access needed)

Session pause:
  Save Working Memory snapshot to temp/
  → Restorable on resume

Session end:
  MMA evaluates Working Memory → selectively persists to DSE
```

### 5.2 Event-Driven Update Pipeline (CDC: Change Data Capture)

Infrastructure for reflecting external data source changes into DSE in real-time.

**Architecture**:

```
External Systems (DB / API / File Storage)
        │
   Debezium / Fivetran (CDC)
        │
   Apache Kafka (Message Broker)
        │
   Stream Processing (Apache Flink / Spark Streaming)
   ├── Filtering: only DSE-relevant changes
   ├── Transform: normalize to DSE schema
   └── Deduplication: prevent double processing
        │
   MMA (Memory Management Agent)
   ├── Semantic interpretation of changes (using LLM)
   ├── Diff computation against existing memories
   └── Update / register to DSE
```

**CDC Event Schema**:

```json
{
  "event_id": "uuid",
  "event_type": "create | update | delete",
  "source": {
    "system": "salesforce | jira | github | custom_db",
    "entity_type": "task | document | issue | row",
    "entity_id": "external_id"
  },
  "payload": { "before": {...}, "after": {...} },
  "timestamp": "ISO8601",
  "namespace": "agent:alice/project:alpha"
}
```

### 5.3 Semantic Compression (Memory Distillation)

A compression process that periodically promotes accumulated episodic memories to semantic memories. This corresponds to the process by which humans develop generalized knowledge through experience.

**Distillation Process**:

```
Weekly batch (or threshold trigger):

1. Clustering
   Target: episodic memories from the past 30 days (same namespace)
   Method: HDBSCAN on embeddings
   → Cluster semantically similar memory groups

2. Distillation candidate selection
   Conditions:
     - Cluster size >= 5
     - Average confidence within cluster >= 0.7
     - No existing similar semantic memory

3. LLM generalization
   Prompt:
     "From the following group of episodic memories,
      express the common patterns, knowledge, and rules
      as a single semantic memory"

4. Register new semantic memory
   - memory_type: "semantic"
   - source_type: "inference"
   - confidence: cluster average × 0.9
   - Connect to source episodes with DERIVES edges
   - Decay source episodes' importance_score to 0.5×
     (do not delete — retain as distillation source)
```

**Example**:

```
Episodic group (5 items):
  - "2026-02-10: User Alice asked a Python question"
  - "2026-02-15: Alice asked about Python debugging methods"
  - "2026-02-20: Alice requested a Python library comparison"
  - "2026-02-25: Alice asked about Python asyncio"
  - "2026-03-05: Alice asked about Python type hints"
↓ Semantic Compression
Semantic memory:
  "User Alice primarily uses Python and tends to ask
   intermediate to advanced technical questions"
```

### 5.4 Human-in-the-Loop Memory Curation

An interface that allows users and operators to directly manage memory quality and content.

**Functional Requirements**:

```
User-facing features:
  - Visualize own memory graph (D3.js graph)
  - Manual editing/deletion/importance adjustment of specific memories
  - "Forget this" → bulk delete target and derived memories
  - "Remember this" → importance_score = 1.0, remove expires_at
  - Direct input/editing of Procedural memories
  - Manual memory type changes

Operator-facing features:
  - Dashboard showing memory usage across all users
  - Review and resolve contradiction/confirmation queue
  - Configure cross-namespace memory sharing
  - Bulk archive/delete

API:
  PUT /memories/{id}/importance
  DELETE /memories/{id}?cascade=true
  POST /memories/{id}/curate
  GET /memories/graph?namespace={ns}&depth={d}
```

### 5.5 Integration with Memory-Augmented ReAct Loop

Middleware design for incorporating DSE into agent frameworks (LangChain / AutoGen / CrewAI, etc.).

```python
class DSEMemoryMiddleware:
    """
    Middleware that automatically retrieves and stores memories
    before and after the agent's Thought step.
    """

    async def before_think(self, agent_state: AgentState) -> AgentState:
        """Before Thought step: retrieve memories and inject into context"""
        intent = await self.extract_intent(agent_state.last_observation)
        memories = await self.dse.retrieve(
            query=intent.query,
            namespace=agent_state.namespace,
            memory_types=intent.relevant_types,
            token_budget=agent_state.available_tokens // 4,  # Allocate 1/4 of context to memory
            cascade_stage=intent.urgency_level
        )
        agent_state.context = self.assemble_context(memories)
        return agent_state

    async def after_act(self, agent_state: AgentState, action_result: ActionResult):
        """After Action step: save important information to memory"""
        importance = await self.assess_importance(action_result)
        if importance.score > 0.5:
            await self.dse.store(
                content=importance.extract_storable_content(action_result),
                memory_type=importance.suggested_type,
                namespace=agent_state.namespace,
                source_id=action_result.action_id,
                confidence=importance.confidence
            )
```

---

## 6. Missing Technologies and Their Design

### 6.1 Prospective Memory (Future Intentions)

**What's missing**: The current design targets only past and present memories. There is no mechanism for holding "things to do in the future" as memories and automatically firing them at the appropriate time.

**Technology: Event Scheduler with Condition Engine**

```python
class ProspectiveMemoryEngine:
    """
    Evaluation and firing engine for prospective memories.
    Supports both time triggers and condition triggers.
    """

    async def schedule_scan(self):
        """Firing scan executed every minute"""
        records = await self.search_index.query({
            "filter": {
                "memory_type": "prospective",
                "is_triggered": False,
                "is_archived": False
            }
        })

        for record in records:
            if await self.should_fire(record):
                await self.fire(record)

    async def should_fire(self, record: MemoryRecord) -> bool:
        if record.trigger_type == "time":
            return datetime.now(UTC) >= record.trigger_at

        elif record.trigger_type == "event":
            # Notification-based via event bus (Kafka)
            return record.id in self.pending_events

        elif record.trigger_type == "condition":
            # Evaluate condition expression via LLM
            return await self.evaluate_condition(
                condition=record.trigger_condition,
                current_context=await self.get_current_context()
            )

    async def fire(self, record: MemoryRecord):
        """Fire: notify agent and update record"""
        await self.agent_bus.notify(
            agent_id=record.namespace,
            type="prospective_memory_triggered",
            memory_id=record.id,
            summary=record.summary
        )
        await self.search_index.update(record.id, {
            "is_triggered": True,
            "triggered_at": datetime.now(UTC).isoformat()
        })
```

**Additional index fields**:

```json
{
  "trigger_type": "time | event | condition",
  "trigger_at": "ISO8601 (for time triggers)",
  "trigger_event": "project:X:status:changed (for event triggers)",
  "trigger_condition": "user_idle_minutes > 30 AND task_count > 5",
  "recurrence": "daily | weekly | null (repeating)",
  "is_triggered": false,
  "triggered_at": "null"
}
```

### 6.2 Confidence and Epistemic State Management

**What's missing**: The "confidence level" and "type of knowledge (observation or inference?)" of memories are not systematically managed. There is insufficient basis for agents to judge "is this reliable information?"

**Technology: Bayesian Belief Updater**

```python
class EpistemicStateManager:
    """
    Dynamically updates memory confidence through Bayesian updating.
    """

    async def update_confidence(
        self,
        record_id: str,
        new_evidence: Evidence
    ) -> float:
        record = await self.get_record(record_id)

        # Bayesian update: P(H|E) ∝ P(E|H) × P(H)
        prior = record.confidence
        likelihood = self.compute_likelihood(new_evidence, record)
        posterior = self.bayesian_update(prior, likelihood)

        # Update strength varies by evidence type
        update_strength = {
            "user_explicit_correction": 1.0,  # Force override
            "corroborating_source":     0.15, # Reinforcement
            "contradicting_source":    -0.20, # Refutation
            "passage_of_time":         -0.01, # Time passage
            "repeated_access":          0.05, # Repeated reference
        }[new_evidence.type]

        new_confidence = max(0.0, min(1.0, prior + update_strength))
        await self.update_record(record_id, {"confidence": new_confidence})
        return new_confidence

    def compute_likelihood(self, evidence: Evidence, record: MemoryRecord) -> float:
        if evidence.type == "corroborating_source":
            # Same content confirmed from independent source
            return 0.9 if evidence.source_independent else 0.6
        elif evidence.type == "contradicting_source":
            return 0.1 if evidence.source_credibility > 0.8 else 0.3
        return 0.5
```

**Epistemic State Fields**:

```json
{
  "epistemic_state": {
    "confidence": 0.87,
    "basis": "observation",
    "corroborating_sources": 3,
    "contradicting_sources": 0,
    "last_updated_by": "evidence:uuid",
    "uncertainty_type": "aleatory | epistemic"
  }
}
```

### 6.3 Causal and Temporal Reasoning Engine

**What's missing**: Reasoning about "Did A cause B?" or "Did X happen before or after Y?" is not directly supported by DSE's index search. A dedicated engine for causal and temporal reasoning is needed.

**Technology 1: Allen's Interval Algebra (Temporal Reasoning)**

Expresses temporal relationships between memories using 13 types of time relations (before / meets / overlaps / starts / during / finishes / equals, and their inverses).

```python
class TemporalReasoningEngine:
    """
    Temporal reasoning engine based on Allen's Interval Algebra.
    """

    def classify_relation(
        self,
        interval_a: TimeInterval,
        interval_b: TimeInterval
    ) -> AllenRelation:
        if interval_a.end < interval_b.start:
            return AllenRelation.BEFORE
        elif interval_a.end == interval_b.start:
            return AllenRelation.MEETS
        elif interval_a.start < interval_b.start and interval_a.end < interval_b.end:
            return AllenRelation.OVERLAPS
        # ... covers all 13 relations

    async def find_temporal_context(
        self,
        memory_id: str,
        window: timedelta = timedelta(days=7)
    ) -> List[TemporalNeighbor]:
        """
        Retrieve related memories that occurred within X days
        before and after the target memory.
        """
        record = await self.get_record(memory_id)
        window_start = record.created_at - window
        window_end = record.created_at + window

        neighbors = await self.search_index.query({
            "filter": {
                "created_at": {"gte": window_start, "lte": window_end},
                "namespace": record.namespace
            },
            "vector": record.embedding,
            "k": 20
        })

        return [
            TemporalNeighbor(
                record=n,
                temporal_relation=self.classify_relation(
                    TimeInterval(record.created_at, record.updated_at),
                    TimeInterval(n.created_at, n.updated_at)
                )
            )
            for n in neighbors
        ]
```

**Technology 2: Causal DAG (Causal Graph)**

Combines causal inference libraries (DoWhy / CausalNex) with Graph DB to manage causal structures between memories.

```cypher
// Causal chain query
MATCH path = (cause:Memory)-[:CAUSES*1..3]->(effect:Memory {id: $target_id})
WHERE ALL(r IN relationships(path) WHERE r.confidence > 0.6)
RETURN cause, path
ORDER BY length(path) ASC, reduce(conf=1.0, r IN relationships(path) | conf * r.confidence) DESC
```

### 6.4 Cross-Agent Memory Sharing Protocol

**What's missing**: When multiple agents share the same DSE, access control for who can access which memories and namespace design are undefined.

**Technology: Memory Scope Token (Memory Scope Authorization)**

Applies OAuth's scope concept to memory access.

```
Namespace hierarchy:
  global/                        # Shared across all agents (read-only)
  org:{org_id}/                  # Shared within organization
  project:{project_id}/          # Shared within project
  user:{user_id}/                # User personal
  agent:{agent_id}/              # Agent-exclusive
  session:{session_id}/          # Session volatile (Working Memory)

Memory Scope Token example:
{
  "sub": "agent:task-agent-001",
  "scopes": [
    "global:read",
    "org:acme:read",
    "project:alpha:read:write",
    "user:alice:read",
    "agent:task-agent-001:read:write:delete"
  ],
  "constraints": {
    "memory_types": ["semantic", "episodic"],
    "max_results_per_query": 20,
    "rate_limit": "100/minute"
  },
  "exp": 1742345678
}
```

**Shared memory write rules**:

```
When an agent writes to project:alpha/ memory:
  1. Verify write scope
  2. PII inspection of content (stricter for shared memory)
  3. Record writing agent ID in source_id (Provenance)
  4. Notify other agents of change (optional)
```

### 6.5 Memory Provenance Tracking (Lineage Tracking)

**What's missing**: The complete lineage of when, who, why, for what task, and how a memory was generated or updated cannot be tracked.

**Technology: Lineage Graph + OpenLineage-Compatible Schema**

```json
{
  "memory_id": "uuid",
  "lineage": {
    "created_by": {
      "agent_id": "agent:task-agent-001",
      "task_id": "task:uuid",
      "session_id": "session:uuid",
      "action": "observation"
    },
    "transformations": [
      {
        "type": "summarization",
        "timestamp": "ISO8601",
        "performed_by": "agent:mma",
        "input_ids": ["uuid-1", "uuid-2"],
        "output_id": "uuid-3",
        "model": "claude-sonnet-4-6"
      },
      {
        "type": "semantic_compression",
        "timestamp": "ISO8601",
        "performed_by": "agent:mma",
        "input_ids": ["uuid-10", ..., "uuid-30"],
        "output_id": "uuid-31",
        "cluster_id": "cluster:42"
      }
    ],
    "access_log": [
      {
        "accessed_by": "agent:task-agent-001",
        "accessed_at": "ISO8601",
        "task_id": "task:uuid",
        "utility_score": 0.85
      }
    ]
  }
}
```

**Applications of Provenance**:

- Debugging: Trace back "why was this memory used?"
- Quality control: Distinguish "AI auto-generated memory" vs "user-verified memory"
- GDPR compliance: Calculate impact scope when deleting a specific user's data
- Audit log: Compliance trail for enterprise environments

### 6.6 Memory Importance Scoring (Automatic Importance Evaluation)

**What's missing**: Memory "importance" is registered with a fixed value at write time in the current design, with no mechanism for dynamic updates based on subsequent context.

**Technology: Contextual Importance Estimator**

```python
class ImportanceEstimator:
    """
    Model that dynamically evaluates memory importance based on context.
    Combines multiple signals.
    """

    SIGNALS = {
        # Content-derived signals
        "contains_decision":          0.30,  # Record of a decision
        "contains_error_correction":  0.25,  # Error correction
        "contains_user_preference":   0.20,  # User preference
        "contains_factual_claim":     0.15,  # Factual claim
        "contains_deadline":          0.25,  # Deadline

        # Behavior-derived signals
        "user_explicitly_marked":     0.50,  # User marked as important
        "agent_re_referenced":        0.10,  # Agent re-referenced
        "led_to_successful_action":   0.20,  # Contributed to successful action
        "led_to_failed_action":      -0.10,  # Used in failed action

        # Structure-derived signals
        "many_dependents_in_graph":   0.15,  # Referenced by many memories
        "unique_in_namespace":        0.10,  # Rare information with no similar records
    }

    async def estimate(self, record: MemoryRecord, context: dict) -> float:
        score = 0.5  # baseline

        for signal, weight in self.SIGNALS.items():
            if await self.detect_signal(signal, record, context):
                score += weight

        return max(0.0, min(1.0, score))
```

---

## 7. Memory Lifecycle Design

### 7.1 Overall Lifecycle

```
[Creation] → [Active] → [Warm] → [Archive] → [Deletion]
                ↑                   ↑
                └── Semantic ───────┘
                    Compression
                    (Promotion)
```

State definitions and transition conditions:

| State | decay_score | Search target | Storage | Transition condition |
|-------|------------|--------------|---------|---------------------|
| Active | > 0.4 | Included in normal search | Hot storage | After creation / decay recovery |
| Warm | 0.2–0.4 | Only when explicitly specified | Warm storage | decay < 0.4 |
| Archive | < 0.2 | Direct ID access only | Cold storage / GCS Nearline | decay < 0.2 |
| Superseded | Any | Excluded (score ×0.1) | Hot storage (for reference) | When SUPERSEDED_BY edge added |
| Deleted | - | Excluded | Deleted | User request / GDPR |

### 7.2 Memory Reinforcement

When a memory is referenced by an agent or user and judged useful, its Decay recovers.

```python
async def reinforce_memory(
    memory_id: str,
    utility_score: float,  # 0.0 to 1.0
    accessor_type: str     # "agent" | "user"
):
    record = await get_record(memory_id)

    # Decay recovery amount: varies by utility score and accessor type
    recovery = utility_score * (0.15 if accessor_type == "user" else 0.05)

    new_decay = min(1.0, record.decay_score + recovery)
    new_access_count = record.access_count + 1

    await update_record(memory_id, {
        "decay_score": new_decay,
        "access_count": new_access_count,
        "access_count_7d": record.access_count_7d + 1,
        "accessed_at": datetime.now(UTC).isoformat(),
        "last_access_utility": utility_score
    })
```

---

## 8. Search Pipeline Design

### 8.1 Query Preprocessing

Pipeline that converts natural language queries from agents into searchable form:

```python
class QueryPreprocessor:
    async def process(self, query: str, context: RetrievalContext) -> SearchQuery:
        # 1. Intent extraction
        intent = await self.llm.extract(f"""
            Extract search intent from the following query:
            Query: {query}
            Task context: {context.task_description}

            Items to extract:
            - primary_intent: main search intent
            - memory_types: list of relevant memory types
            - entities: list of important entities
            - time_range: relevant time range (if any)
            - urgency: high | medium | low
        """)

        # 2. Query expansion
        expanded_queries = await self.expand_query(query, intent)

        # 3. Embedding generation
        embedding = await self.embedding_model.encode(
            f"{intent.primary_intent} {' '.join(intent.entities)}"
        )

        # 4. Filter construction
        filters = self.build_filters(intent, context)

        return SearchQuery(
            text_queries=expanded_queries,
            embedding=embedding,
            filters=filters,
            memory_types=intent.memory_types,
            cascade_stage=self.select_stage(intent.urgency)
        )
```

### 8.2 Hybrid Search and RRF (Reciprocal Rank Fusion)

```python
class HybridSearchEngine:

    async def search(self, query: SearchQuery) -> List[SearchResult]:
        # Parallel execution
        bm25_results, vector_results = await asyncio.gather(
            self.bm25_search(query),
            self.vector_search(query)
        )

        # Merge scores using RRF (Reciprocal Rank Fusion)
        rrf_scores = defaultdict(float)
        k = 60  # RRF constant

        for rank, result in enumerate(bm25_results):
            rrf_scores[result.id] += 1 / (k + rank + 1)

        for rank, result in enumerate(vector_results):
            rrf_scores[result.id] += 1 / (k + rank + 1)

        # Re-rank with custom scoring
        combined = []
        all_results = {r.id: r for r in bm25_results + vector_results}

        for doc_id, rrf_score in sorted(rrf_scores.items(), key=lambda x: -x[1]):
            record = all_results[doc_id]
            final_score = self.compute_final_score(record, rrf_score, query)
            combined.append(SearchResult(record=record, score=final_score))

        return sorted(combined, key=lambda x: -x.score)[:query.top_k]

    def compute_final_score(
        self,
        record: MemoryRecord,
        rrf_score: float,
        query: SearchQuery
    ) -> float:
        # Factor weights (adjusted by task type)
        w = query.weights  # Default: relevance=0.5, quality=0.3, temporal=0.2

        relevance = rrf_score
        quality = record.confidence * record.decay_score
        temporal = self.temporal_recency_score(record.created_at)

        # Superseded penalty
        superseded_penalty = 0.1 if record.superseded_by else 1.0

        # Exploration bonus (discovery of low-access memories)
        exploration = query.exploration_factor / (1 + record.access_count_30d)

        return (
            w.relevance * relevance +
            w.quality * quality +
            w.temporal * temporal +
            query.exploration_factor * exploration
        ) * superseded_penalty
```

### 8.3 Context Assembly

```python
class ContextAssembler:

    async def assemble(
        self,
        results: List[SearchResult],
        token_budget: int
    ) -> AssembledContext:

        context_items = []
        used_tokens = 0

        for result in results:
            record = result.record

            # Select tier based on token budget
            remaining = token_budget - used_tokens

            if remaining >= 500 and result.score > 0.8:
                # Tier 3: Full (high relevance and sufficient budget)
                content = await self.fetch_full_content(record.content_path)
                tier = "full"
            elif remaining >= 100:
                # Tier 2: Summary
                content = record.summary
                tier = "summary"
            elif remaining >= 20:
                # Tier 1: Reference only
                content = f"[{record.memory_type}] {record.id}: {record.summary[:50]}..."
                tier = "reference"
            else:
                break

            tokens = self.count_tokens(content)
            context_items.append(ContextItem(
                memory_id=record.id,
                memory_type=record.memory_type,
                content=content,
                tier=tier,
                score=result.score,
                confidence=record.confidence,
                created_at=record.created_at,
                tokens=tokens
            ))
            used_tokens += tokens

        return AssembledContext(items=context_items, total_tokens=used_tokens)
```

---

## 9. Graph Structure and Relationship Design

### 9.1 Automatic Relationship Discovery

Relationship discovery algorithm executed periodically by the MMA:

```python
class RelationDiscoveryEngine:

    async def discover_relations(self, namespace: str):
        """
        Discover latent relationships between existing memory records
        and register them in the Graph DB.
        """

        # 1. Extract candidate similar memory pairs (ANN search)
        candidates = await self.find_similar_pairs(namespace, threshold=0.75)

        for pair in candidates:
            # Skip if relationship already exists
            if await self.relation_exists(pair.a.id, pair.b.id):
                continue

            # 2. Classify relationship type via LLM
            relation = await self.classify_relation(pair.a, pair.b)

            if relation.type and relation.confidence > 0.7:
                await self.graph_db.create_edge(
                    from_id=pair.a.id,
                    to_id=pair.b.id,
                    relation_type=relation.type,
                    properties={
                        "confidence": relation.confidence,
                        "discovered_by": "auto",
                        "discovered_at": datetime.now(UTC).isoformat(),
                        "method": "embedding_similarity + llm_classification"
                    }
                )

    async def classify_relation(
        self,
        memory_a: MemoryRecord,
        memory_b: MemoryRecord
    ) -> RelationClassification:

        prompt = f"""
        Classify the relationship between the following two memories.

        Memory A: {memory_a.summary}
        Memory B: {memory_b.summary}

        Relationship types (select the applicable one):
        - SUPERSEDES: A updates/replaces B's content
        - COMPLEMENTS: A and B together form complete information
        - CONTRADICTS: A and B contradict each other
        - DERIVES: B was inferred/extracted from A
        - CAUSES: A caused B
        - REFERENCES: A references B
        - NONE: No meaningful relationship

        Reply in JSON format:
        {{"type": "...", "confidence": 0.0-1.0, "reason": "..."}}
        """

        return await self.llm.classify(prompt)
```

### 9.2 Graph Visualization Query

```cypher
// Subgraph retrieval for memory network (for UI)
MATCH (center:Memory {id: $center_id})
CALL apoc.path.subgraphNodes(center, {
  maxLevel: 2,
  relationshipFilter: "SUPERSEDES|COMPLEMENTS|DERIVES|CAUSES",
  labelFilter: "+Memory"
}) YIELD node
MATCH (center)-[r]-(node)
RETURN center, collect(node) as neighbors, collect(r) as relations
```

---

## 10. Security and Access Control

### 10.1 PII Detection and Anonymization

```python
class PIIGuard:
    """
    Guard that detects and processes PII during memory writes.
    """

    PII_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\b(\+?81|0)\d{9,10}\b",
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "my_number": r"\b\d{12}\b"
    }

    async def process(self, content: str, policy: PIIPolicy) -> PIIResult:
        detected = self.detect(content)

        if not detected:
            return PIIResult(content=content, pii_detected=False)

        match policy:
            case PIIPolicy.BLOCK:
                raise PIIDetectedError(f"PII detected: {detected}")
            case PIIPolicy.ANONYMIZE:
                anonymized = self.anonymize(content, detected)
                return PIIResult(content=anonymized, pii_detected=True, pii_types=detected)
            case PIIPolicy.TOKENIZE:
                tokenized, vault = self.tokenize(content, detected)
                # vault (original PII values) stored in separate encrypted storage
                await self.pii_vault.store(vault)
                return PIIResult(content=tokenized, pii_detected=True, pii_types=detected)
```

### 10.2 Namespace Isolation and Access Control

```
Access control principles:
  1. Default-deny: Deny access to any namespace not explicitly authorized
  2. Namespace isolation: Memories in different namespaces are physically isolated (index shards)
  3. Set scopes at Read/Write/Delete granularity
  4. Audit logs: Send all access to OpenTelemetry + SIEM

Encryption:
  At rest: AES-256 (Object Storage) / transparent encryption (Search Index)
  In transit: TLS 1.3
  Embedding vectors: Use encrypted index for particularly sensitive content
```

---

## 11. Scalability and Operations Design

### 11.1 Scaling Strategy

| Component | Scaling Method | Metrics |
|-----------|---------------|---------|
| Search Index | Horizontal sharding (by Namespace) | QPS, P99 latency |
| Object Storage | Automatic via managed service | Storage usage |
| Graph DB | Read replicas + write buffer | Query time, edge count |
| Embedding Service | GPU auto-scaling | Queue depth, throughput |
| MMA Worker | Kubernetes HPA | Queue depth, processing delay |

### 11.2 Observability

**Metrics (OpenTelemetry)**:

```yaml
# DSE metrics definitions
dse_retrieval_latency_ms:
  type: histogram
  labels: [cascade_stage, memory_type, namespace]

dse_cache_hit_ratio:
  type: gauge
  labels: [cache_layer, namespace]

dse_memory_decay_distribution:
  type: histogram
  labels: [memory_type, namespace]
  buckets: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

dse_contradiction_count:
  type: counter
  labels: [namespace, resolution_status]

dse_index_freshness_lag_seconds:
  type: histogram
  labels: [update_source]
```

**Traces**: All Retrieval and Write operations are assigned Trace IDs, visualized with Jaeger/Zipkin. This enables tracking the causal relationship between agent decisions and memory access.

### 11.3 Disaster Recovery

```
RTO: 4 hours (Object Storage + Graph DB restoration)
RPO: 1 hour (reconstruction from CDC logs)

Backup strategy:
  Object Storage: Cross-region replication (continuous)
  Search Index: Snapshot daily + WAL continuous backup
  Graph DB: Neo4j Causal Cluster (3 nodes) + daily export

Response by failure scenario:
  Search Index failure: Degraded operation with Graph DB + Object Storage only
  Graph DB failure: Flat search (no relationships) for degraded operation
  Object Storage failure: Degraded operation with Summary field only (full content unavailable)
```

---

## 12. Implementation Roadmap

### Phase 1: Core DSE (3 months)

**Goal**: Minimum configuration where basic memory storage and search works.

- Search Index schema design and construction (Elasticsearch)
- Object Storage infrastructure (GCS / Azure Blob)
- Basic Hybrid Search implementation (BM25 + Vector)
- Memory type tagging (semantic / episodic / procedural)
- Decay Score daily batch
- Basic MMA implementation (write / read)
- Integration with Memory-Augmented ReAct loop

### Phase 2: Graph & Quality (3 months)

**Goal**: Relationship management and quality assurance between memories.

- Graph DB construction (Neo4j)
- SUPERSEDES / COMPLEMENTS / CONTRADICTS edges
- Contradiction detection and flagging
- Confidence scores and Bayesian updates
- Working Memory Buffer (Redis)
- CDC Pipeline (Kafka + Debezium)
- Provenance tracking

### Phase 3: Intelligence (3 months)

**Goal**: Intelligent management features where memories autonomously improve.

- Semantic Compression (episodic → semantic promotion)
- Prospective Memory engine
- Automatic relationship discovery
- Temporal Reasoning (Allen's Interval)
- Contextual Importance Estimator
- Human-in-the-Loop Curation UI

### Phase 4: Enterprise (3 months)

**Goal**: Production operations and multi-agent support.

- Cross-Agent Memory Sharing Protocol
- Memory Scope Token (authorization infrastructure)
- PII Guard + anonymization
- GDPR compliance (deletion / export)
- Multi-region support
- Embedding Model version management and migration
- Complete Observability stack
- Disaster recovery

---

## 13. Appendix: Schema and Query Reference

### A. Complete Index Schema (Elasticsearch Mapping)

```json
{
  "mappings": {
    "properties": {
      "id":              { "type": "keyword" },
      "namespace":       { "type": "keyword" },
      "content_path":    { "type": "keyword", "index": false },
      "summary":         { "type": "text", "analyzer": "kuromoji" },
      "content_text":    { "type": "text", "analyzer": "kuromoji" },
      "embedding":       { "type": "dense_vector", "dims": 3072, "index": true, "similarity": "cosine" },
      "summary_embedding": { "type": "dense_vector", "dims": 3072, "index": true, "similarity": "cosine" },
      "memory_type":     { "type": "keyword" },
      "memory_subtype":  { "type": "keyword" },
      "content_type":    { "type": "keyword" },
      "confidence":      { "type": "float" },
      "source_type":     { "type": "keyword" },
      "source_id":       { "type": "keyword" },
      "verification_status": { "type": "keyword" },
      "created_at":      { "type": "date" },
      "updated_at":      { "type": "date" },
      "accessed_at":     { "type": "date" },
      "expires_at":      { "type": "date" },
      "access_count":    { "type": "integer" },
      "access_count_7d": { "type": "integer" },
      "access_count_30d": { "type": "integer" },
      "decay_score":     { "type": "float" },
      "importance_score": { "type": "float" },
      "superseded_by":   { "type": "keyword" },
      "tags":            { "type": "keyword" },
      "entities":        { "type": "keyword" },
      "language":        { "type": "keyword" },
      "trigger_type":    { "type": "keyword" },
      "trigger_at":      { "type": "date" },
      "trigger_condition": { "type": "keyword" },
      "is_triggered":    { "type": "boolean" },
      "is_archived":     { "type": "boolean" },
      "neighbor_ids":    { "type": "keyword" },
      "embedding_model": { "type": "keyword" },
      "embedding_version": { "type": "keyword" }
    }
  }
}
```

### B. Memory API Endpoint Specifications

```
POST   /v1/memories               # Create new memory
GET    /v1/memories/{id}          # Get by ID
PUT    /v1/memories/{id}          # Update
DELETE /v1/memories/{id}          # Delete (soft / hard)
POST   /v1/memories/retrieve      # Context retrieval (main search API)
GET    /v1/memories/graph         # Get graph visualization data
POST   /v1/memories/{id}/feedback # Record feedback (utility score)
POST   /v1/memories/{id}/curate   # Manual curation
GET    /v1/memories/conflicts     # List contradicting memories
POST   /v1/memories/compress      # Trigger Semantic Compression
GET    /v1/memories/stats         # Namespace statistics
GET    /v1/memories/{id}/lineage  # Get provenance lineage
```

### C. Recommended Technology Stack (Full Spec)

| Layer | Component | Technology Options |
|-------|-----------|-------------------|
| Search engine | Search Index | Elasticsearch 8.x / Azure AI Search / Vertex AI Search |
| Vector DB | Vector Search | ES dense_vector / Qdrant / Weaviate |
| Graph DB | Relation Store | Neo4j Aura / Amazon Neptune / TigerGraph |
| Object storage | Content Store | GCS / Azure Blob / S3 |
| Cache | Working Memory | Redis 7.x (Redis Streams) |
| Messaging | Event Bus | Apache Kafka / GCP Pub-Sub / Azure Event Hubs |
| Embedding | Vector Model | text-embedding-3-large / Vertex AI Embeddings |
| LLM | Reasoning | Claude Sonnet 4.6 (for MMA judgments) |
| Orchestration | Workflow | Temporal / Prefect / Apache Airflow |
| Monitoring | Observability | OpenTelemetry + Jaeger + Prometheus + Grafana |
| Authorization | Access Control | OPA (Open Policy Agent) + JWT |
| CDC | Change Capture | Debezium + Kafka Connect |
| PII | Detection | Presidio / AWS Comprehend |

---

*This report comprehensively documents DSE's design philosophy, technology choices, and implementation guidelines. For actual implementation, it is recommended to select and simplify components based on the target system's scale, cost, and team skill set.*
