# DSE — Dynamic Search Engine for Agentic Memory

**Give your AI agents a memory that actually works.**

DSE is a search-engine-based memory system for AI agents. Instead of stuffing everything into an LLM's context window, DSE lets agents dynamically search, retrieve, and manage their own memories — past experiences, learned knowledge, procedural skills, and future intentions.

Think of it as Google for your agent's brain.

---

## Why DSE?

Traditional RAG retrieves *documents*. DSE retrieves *memories*.

| Problem | DSE's Answer |
|---------|-------------|
| Context windows overflow as agents accumulate knowledge | Retrieve only what's needed — memory scales independently of context cost |
| Agents forget what happened 3 conversations ago | Episodic memory persists across sessions with full provenance tracking |
| No way to tell if a memory is still accurate | Ebbinghaus-inspired decay + Bayesian confidence + contradiction detection |
| Flat vector search misses relationships | Graph-backed retrieval follows causal chains, contradictions, and derivations |
| Similar episodic memories pile up without structure | Semantic compression automatically distills episodes into generalized knowledge |

### Memory Types (inspired by cognitive science)

| Type | What it stores | Example |
|------|---------------|---------|
| **Semantic** | Facts and knowledge | "Python is an interpreted language" |
| **Episodic** | Specific experiences | "On 2026-03-10, we discussed AWS cost optimization" |
| **Procedural** | Skills and rules | "Always check test coverage during code review" |
| **Prospective** | Future intentions | "Remind me to check Project X status next login" |

---

## Architecture

```
                        AI Agent Layer
        ┌──────────┐  ┌──────────┐  ┌──────────────┐
        │Task Agent│  │Chat Agent│  │Memory Manager│
        └────┬─────┘  └────┬─────┘  └──────┬───────┘
             │              │               │
             ▼              ▼               ▼
    ┌──────────────────────────────────────────────────┐
    │            DSE Gateway (FastAPI)                  │
    │  Intent extraction → Query routing →              │
    │  Cascade retrieval → Context assembly             │
    └───────┬──────────────┬───────────────┬───────────┘
            │              │               │
    ┌───────▼───────┐ ┌────▼────┐ ┌────────▼────────┐
    │ Elasticsearch │ │ Object  │ │   Neo4j Graph   │
    │               │ │ Storage │ │                 │
    │ - BM25 text   │ │ - GCS   │ │ - 8 edge types │
    │ - kNN vector  │ │ - MinIO │ │ - Lineage       │
    │ - Hybrid      │ │         │ │ - Contradictions│
    └───────────────┘ └─────────┘ └─────────────────┘
```

**Cascade Retrieval** — three stages, tunable per query:

| Stage | Latency | What it does |
|-------|---------|-------------|
| **Fast** | < 50ms | Cache hit + approximate nearest neighbor |
| **Precision** | < 200ms | Hybrid BM25 + kNN search with RRF re-ranking |
| **Deep** | < 1s | Precision + graph traversal (excludes contradictions, follows DERIVES chains) |

**Intelligence Layer** — memories improve autonomously over time:

| Feature | How it works |
|---------|-------------|
| **Semantic Compression** | HDBSCAN clusters similar episodes, LLM generalizes them into semantic knowledge |
| **Relation Discovery** | ANN finds similar pairs, LLM classifies their relationship, graph edges auto-created |
| **Temporal Reasoning** | Allen's Interval Algebra classifies time relations, TEMPORALLY_PRECEDES edges built automatically |
| **Prospective Memory** | Time/event/condition triggers fire automatically, with daily/weekly recurrence support |
| **Importance Scoring** | Content signals (LLM) + behavior signals (access patterns) + structural signals (graph) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | Python 3.13 / FastAPI / uvicorn |
| **Search** | Elasticsearch 8.17 (BM25 + kNN dense_vector with cosine similarity) |
| **AI Agents** | Google ADK / Gemini 3.1 Flash |
| **Embeddings** | Gemini Embedding (`gemini-embedding-2-preview`, 3072 dimensions) |
| **Graph DB** | Neo4j 5 with APOC (8 relationship types, constraint/fulltext indexes) |
| **Cache** | Redis 7 (working memory sessions via Streams, search/embedding cache) |
| **Object Storage** | Google Cloud Storage (MinIO for local dev) |
| **Workflows** | Temporal (write sagas, contradiction checks, compression, discovery schedules) |
| **Event Bus** | Redpanda (Kafka-compatible CDC pipeline) |
| **MCP Server** | [Model Context Protocol](https://modelcontextprotocol.io/) (stdio + streamable-http) |
| **Frontend** | Next.js 15 / React 19 / Tailwind CSS / React Flow |

---

## Quick Start

### Prerequisites

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22+ and [pnpm](https://pnpm.io/) 9+ (for the dashboard)
- Docker and Docker Compose v2

### 1. Clone and configure

```bash
git clone https://github.com/your-org/dse.git
cd dse
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY, or set USE_MOCK_LLM=true for offline dev
```

### 2. One-command launch (recommended)

```bash
make run-all
```

This starts Docker services, installs dependencies, initializes databases, and launches the API server, Temporal worker, MCP server, and frontend — all in one go.

| Service | URL |
|---------|-----|
| **API Server** | http://localhost:8000 (`/docs` for OpenAPI) |
| **MCP Server** | http://localhost:8001/mcp (streamable-http) |
| **Dashboard** | http://localhost:3000 |
| Elasticsearch | http://localhost:9200 |
| Neo4j Browser | http://localhost:7474 |
| Temporal UI | http://localhost:8080 |
| MinIO Console | http://localhost:9001 |
| Redpanda Console | http://localhost:8085 |

### 2b. Step-by-step launch (alternative)

```bash
make dev                 # Start Docker services (Elasticsearch, Neo4j, Redis, Temporal, etc.)
make install             # Install Python packages
make wait-healthy        # Wait for all services to be ready
make db-init             # Create Neo4j constraints and indexes

# Then run each process separately:
make api                 # FastAPI server (port 8000)
make worker              # Temporal worker for background workflows
make mcp-http            # MCP server (port 8001)
make frontend            # Next.js dashboard (port 3000)
```

### 3. Load sample data

```bash
# Generate and load sample memories for a namespace
python scripts/bulk_load.py data/engineer-memory.jsonl

# Ingest a document (PDF or text) into memories
python scripts/ingest_document.py data/your-document.pdf --namespace user:my-agent
```

### 4. Register recurring workflows

```bash
make register-schedules  # Auto-discovers namespaces and registers schedules
```

---

## Usage Examples

### Store a memory

```bash
curl -X POST http://localhost:8000/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "agent:alice/project:alpha",
    "content_text": "The user prefers dark mode and uses vim keybindings.",
    "memory_type": "semantic",
    "confidence": 0.9,
    "tags": ["user-preference", "ui"],
    "source_type": "user_explicit"
  }'
```

### Retrieve context for an agent

```bash
curl -X POST http://localhost:8000/v1/memories/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the user preferences for the editor?",
    "namespace": "agent:alice/project:alpha",
    "token_budget": 2000,
    "cascade_stage": "precision"
  }'
```

The response is a token-budget-aware context package with tiered content (full text, summaries, or references) that you inject directly into your agent's prompt.

### Submit evidence to update confidence

```bash
curl -X POST http://localhost:8000/v1/memories/{id}/evidence \
  -H "Content-Type: application/json" \
  -d '{"evidence_type": "corroborating_source", "source_independent": true}'
```

Corroborating evidence increases confidence; contradicting evidence decreases it. User corrections override instantly.

### Create a prospective memory (future reminder)

```bash
curl -X POST http://localhost:8000/v1/curation/prospective \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "agent:alice/project:alpha",
    "summary": "Check deployment status of v2.0",
    "trigger_type": "time",
    "trigger_at": "2026-04-01T09:00:00Z",
    "recurrence": "daily"
  }'
```

The prospective scan workflow checks every minute and fires memories whose trigger conditions are met.

### Browse and manage memories

```bash
# List memories with filters
curl "http://localhost:8000/v1/curation/memories?namespace=agent:alice&memory_type=semantic&sort_by=importance"

# Pin an important memory (importance=1.0, never expires)
curl -X POST http://localhost:8000/v1/curation/memories/{id}/pin -d '{"pinned": true}'

# Forget a memory and all its derivatives
curl -X POST http://localhost:8000/v1/curation/memories/{id}/forget
```

---

## API Reference

### Memory CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/memories` | Create a new memory |
| `GET` | `/v1/memories/{id}` | Get a memory by ID |
| `PUT` | `/v1/memories/{id}` | Update a memory |
| `DELETE` | `/v1/memories/{id}?cascade=true` | Delete (optionally cascade to derivatives) |
| `POST` | `/v1/memories/retrieve` | Context retrieval (main search API) |
| `GET` | `/v1/memories/stats` | Namespace statistics |

### Confidence & Feedback

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/memories/{id}/feedback` | Record utility feedback (reinforces decay) |
| `POST` | `/v1/memories/{id}/evidence` | Submit evidence for Bayesian confidence update |
| `POST` | `/v1/memories/{id}/curate` | Pin, archive, or adjust importance |

### Graph & Relations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/graph/subgraph?namespace=...` | Full subgraph for visualization (React Flow) |
| `GET` | `/v1/graph/neighbors/{id}?depth=2` | Neighbor traversal (1-3 hops) |
| `GET` | `/v1/graph/lineage/{id}` | DERIVES provenance chain |

### Contradiction Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/conflicts?namespace=...` | List contradicting memory pairs |
| `POST` | `/v1/conflicts/resolve` | Resolve: keep A, B, or both |

### Provenance

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/memories/{id}/provenance` | Full lineage (created_by, transformations, access log) |
| `POST` | `/v1/memories/{id}/provenance/access` | Record an access event |

### Working Memory (Sessions)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/v1/sessions/{id}/context` | Store session context |
| `GET` | `/v1/sessions/{id}/context` | Get session context |
| `POST` | `/v1/sessions/{id}/turns` | Append conversation turn (Redis Stream) |
| `GET` | `/v1/sessions/{id}/turns` | Get recent turns |
| `POST` | `/v1/sessions/{id}/persist` | Snapshot for MMA persistence decision |
| `DELETE` | `/v1/sessions/{id}` | End session, clear working memory |

### Curation (Human-in-the-Loop)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/curation/memories` | Browse with filters, sorting, pagination |
| `POST` | `/v1/curation/memories/{id}/pin` | Pin / unpin |
| `POST` | `/v1/curation/memories/{id}/forget` | Delete memory + all derivatives |
| `POST` | `/v1/curation/compress` | Manually trigger semantic compression |
| `GET` | `/v1/curation/prospective` | List prospective memories |
| `POST` | `/v1/curation/prospective` | Create a prospective memory |
| `DELETE` | `/v1/curation/prospective/{id}` | Delete a prospective memory |
| `GET` | `/v1/curation/stats` | Memory statistics (type distribution, decay, importance) |

### Namespace Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/namespaces` | List all namespaces |
| `GET` | `/v1/namespaces/{ns}` | Get namespace stats (total, types, archived) |
| `POST` | `/v1/namespaces?namespace=...` | Create a new namespace |
| `DELETE` | `/v1/namespaces/{ns}` | Delete namespace + all its data (ES, Neo4j, storage, schedules) |

### Document Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/ingest/document` | Upload & chunk a document into memories (PDF, text) |

### MCP Introspection

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/mcp` | List all MCP capabilities (tools, resources, prompts) |
| `GET` | `/v1/mcp/tools` | List all MCP tools with input schemas |
| `GET` | `/v1/mcp/tools/{name}` | Get tool detail (full JSON schema) |
| `GET` | `/v1/mcp/resources` | List MCP resource templates |
| `GET` | `/v1/mcp/prompts` | List MCP prompts with arguments |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check (Redis + Neo4j connectivity) |

Full interactive docs at `/docs` (Swagger UI) and `/redoc` when the server is running.

---

## MCP Server (AI Agent Interface)

DSE exposes a [Model Context Protocol](https://modelcontextprotocol.io/) server so AI agents (Claude, ChatGPT, custom agents) can interact with memories through a standardized interface.

### Running the MCP server

```bash
make mcp          # stdio transport (for Claude Desktop / Claude Code)
make mcp-http     # streamable-http transport (port 8001, for remote agents)
```

### Available MCP tools

| Tool | Description |
|------|-------------|
| `retrieve_memories` | Cascade retrieval pipeline (fast/precision/deep) |
| `search_memories` | Direct BM25 text search |
| `store_memory` | Create memory with LLM-inferred summary, tags, entities, importance |
| `get_memory` | Read a memory by ID |
| `update_memory` | Partial update |
| `delete_memory` | Delete from search + graph |
| `list_namespaces` | List all namespaces |
| `get_namespace` | Get namespace stats |
| `create_namespace` | Register a new namespace |
| `delete_namespace` | Delete namespace and all its data |
| `get_related_memories` | Graph neighbor traversal |
| `create_memory_relation` | Create graph edges between memories |
| `working_memory_add` | Add to session short-term memory (Redis) |
| `working_memory_get` | Read session turns |

### Claude Desktop configuration

```json
{
  "mcpServers": {
    "dse": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/dse/backend", "python", "-m", "dse.mcp"],
      "env": {
        "USE_MOCK_LLM": "false",
        "GEMINI_API_KEY": "your-key"
      }
    }
  }
}
```

---

## Dashboard

The frontend is a Next.js admin dashboard for visualizing and managing agent memories.

```bash
make frontend            # Start dev server at http://localhost:3000
```

**Pages:**

- **Dashboard** — Stats overview (total memories, importance, active/warm/archived, type distribution)
- **Memory Search** — Full-text and semantic retrieval with result detail panel
- **Graph** — Interactive React Flow visualization of the memory knowledge graph with node detail panel
- **Conflicts** — Contradiction queue with side-by-side resolution
- **Curation** — Browse/filter/edit memories, trigger compression, manage prospective memories, analytics
- **Intelligence** — Importance heatmap, compression history, relation discovery log
- **Settings** — Service status and configuration

The namespace selector in the sidebar is global — select once, all pages filter automatically.

---

## Development

### Commands

```bash
# --- Services ---
make run-all             # One-command launch (Docker + API + worker + MCP + frontend)
make dev                 # Start all Docker services
make dev-down            # Stop Docker services
make api                 # FastAPI with hot reload (port 8000)
make worker              # Temporal worker for background jobs
make mcp                 # MCP server (stdio transport)
make mcp-http            # MCP server (streamable-http, port 8001)
make frontend            # Next.js dashboard (port 3000)

# --- Temporal ---
make register-schedules        # Register recurring schedules (auto-discovers namespaces)
make register-schedules-force  # Force re-create all schedules

# --- Trigger Workflows Manually ---
make wf-prospective-scan       NS=user:my-agent
make wf-daily-maintenance      NS=user:my-agent
make wf-semantic-compression   NS=user:my-agent
make wf-relation-discovery     NS=user:my-agent
make wf-temporal-edges         NS=user:my-agent
make wf-memory-write           RECORD='{"namespace":"default","content_text":"hello"}'

# --- Testing & Quality ---
make test                # Run unit tests with coverage
make test-int            # Run integration tests
make lint                # ruff check + mypy
make format              # Auto-fix + format

# --- Database ---
make db-init             # Initialize Neo4j schema
make db-reset            # Reset all local data (volumes deleted)
```

### Running fully offline (no cloud needed)

```bash
# In your .env:
USE_MOCK_LLM=true
USE_MOCK_SEARCH=true
```

All Gemini API calls, Elasticsearch queries, and GCS operations use deterministic in-memory mocks. Every test runs in this mode.

### Project structure

```
dse/
├── backend/
│   ├── src/dse/
│   │   ├── api/              # 12 FastAPI routers, schemas, dependency injection
│   │   ├── core/             # Domain models, enums, exceptions
│   │   ├── services/         # Elasticsearch, Gemini, Neo4j, Redis, GCS clients
│   │   ├── pipeline/         # Cascade retrieval, RRF ranking, context assembly
│   │   ├── intelligence/     # Compression, discovery, temporal reasoning, importance
│   │   ├── agents/           # Google ADK agents (MMA with 10 tools, retrieval)
│   │   ├── mcp/              # MCP server (14 tools, 2 resources, 1 prompt)
│   │   ├── workflows/        # 9 Temporal workflows, 26 activities, CLI trigger
│   │   └── infrastructure/   # PII detection, provenance tracking, CDC events
│   └── tests/                # 237+ unit tests, integration tests
├── frontend/                 # Next.js 15 admin dashboard (8 pages)
├── scripts/                  # bulk_load.py, generate_dataset.py, ingest_document.py
├── data/                     # Sample JSONL datasets and research PDFs
├── infra/                    # Neo4j init scripts, Redpanda console config
├── docs/                     # Elasticsearch mapping, ADRs
├── docker-compose.yml        # 9 Docker services
├── Makefile                  # 25+ developer workflow commands
└── .env.example              # 40+ environment variables documented
```

### Key design decisions

- **Elasticsearch for search**: Full-text BM25 + kNN dense vector (cosine, 3072-dim) + hybrid search, all in one index. Auto-created on first connection.
- **Ebbinghaus-inspired decay**: Memories naturally fade unless reinforced. Episodic memories decay fastest, semantic slowest, prospective never decay until triggered.
- **Reciprocal Rank Fusion**: BM25 and vector results are merged via RRF, then re-ranked with confidence, decay, recency, exploration bonus, and contradiction/superseded penalties.
- **Bayesian confidence**: Evidence (corroborating, contradicting, user correction) updates confidence via weighted deltas. Independent sources count more heavily.
- **Saga pattern writes**: Memory creation flows through Storage → Embedding → Elasticsearch → Graph DB → Provenance → Contradiction Check, orchestrated by Temporal.
- **Allen's Interval Algebra**: 13 temporal relations classify how memories relate in time. BEFORE/MEETS pairs get automatic TEMPORALLY_PRECEDES edges.
- **HDBSCAN compression**: Episodic memories are clustered by embedding similarity, then LLM generalizes each cluster into a single semantic memory with DERIVES edges.
- **PII guard**: Regex-based detection for email, phone, credit card, My Number. Configurable: block, anonymize, or tokenize.

---

## Roadmap

- [x] **Phase 1 — Core DSE**: Memory CRUD, Elasticsearch hybrid search, cascade retrieval, decay scoring, FastAPI, MMA agent
- [x] **Phase 2 — Graph & Quality**: Neo4j 8-edge graph, contradiction detection (3-level resolution), Bayesian confidence, working memory (Redis Streams), CDC pipeline, provenance tracking
- [x] **Phase 3 — Intelligence**: Semantic compression (HDBSCAN + LLM), prospective memory engine, relation discovery, Allen's temporal reasoning, importance estimator, curation UI API
- [x] **Phase 3.5 — Interfaces**: MCP server (14 tools, stdio + HTTP), Next.js admin dashboard (8 pages), namespace CRUD, document ingestion, bulk data loading, workflow CLI triggers
- [ ] **Phase 4 — Enterprise**: Cross-agent memory sharing (Memory Scope Tokens), GDPR compliance, multi-region, Elasticsearch cluster scaling, full OpenTelemetry observability

---

## Contributing

1. Read `CLAUDE.md` before making changes — it's the source of truth for coding standards and architecture
2. Every feature needs tests in `backend/tests/`
3. Run `make lint && make test` before opening a PR
4. Breaking changes require an ADR in `docs/adr/`

---

## Design Document

For the full architecture deep-dive — search index schema, graph edge semantics, decay algorithms, scoring formulas, and scalability design — see [PROJECT.md](./PROJECT.md).

---

## License

[MIT](./LICENSE) - Copyright (c) 2026 shibuiwilliam
