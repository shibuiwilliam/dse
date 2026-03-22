# DSE — Dynamic Search Engine for Agentic Memory

## Project Overview

An architecture that implements AI agent memory systems using a search engine.
Agents dynamically search, retrieve, and update past memories (Semantic / Episodic / Procedural / Prospective) through Elasticsearch.

---

## Critical Rules (Highest Priority)

1. **Always consult the relevant section of `CLAUDE.md` before making code changes**
2. **Type annotations are mandatory**. In Python, include `from __future__ import annotations` at the top of every file
3. **Never merge code without tests**. Every new feature must have corresponding tests under `tests/`
4. **All environment variables must be listed in `.env.example`**. Never hardcode secrets in source code
5. **Cloud-dependent components (Elasticsearch / Gemini API / GCS) must have local mocks available**
6. **Create an ADR (Architecture Decision Record) in `docs/adr/` for any breaking changes**
7. **Maintain the ability to start all local services with a single `make dev` command via Docker Compose**

---

## Tech Stack

### Cloud Services (Google Cloud)

| Component | Service | Purpose |
|-----------|---------|---------|
| Search Engine | Elasticsearch 8.x (Docker) | Full-text, vector (kNN), and hybrid search for memories |
| LLM | Gemini 3.0 Flash (`gemini-3-flash-preview`) | MMA reasoning, contradiction detection, relation classification, importance evaluation |
| LLM (High Accuracy) | Gemini 3.1 Pro (future expansion) | Complex reasoning tasks |
| Embedding | `gemini-embedding-2-preview` | Text vectorization (3072 dimensions) |
| Object Storage | Google Cloud Storage | Persistent storage for memory content |

> **Local development note**: Elasticsearch runs locally via Docker Compose. GCS is emulated with MinIO.
> The Gemini API can be swapped with mocks using the `USE_MOCK_LLM=true` environment variable.

### Local Services (Docker)

| Component | Service | Port | Purpose |
|-----------|---------|------|---------|
| Search Engine | Elasticsearch 8.x | 9200 | Full-text, vector, and hybrid search |
| Graph DB | Neo4j 5.x | 7474 / 7687 | Memory relationship graph |
| Cache / Working Memory | Redis 7.x | 6379 | Session short-term memory and API cache |
| Workflow Engine | Temporal Server | 7233 / 8233 | MMA workflow execution |
| Temporal UI | Temporal Web UI | 8080 | Workflow monitoring |
| DB (for Temporal) | PostgreSQL 17 | 5432 | Temporal persistence storage |
| Local Storage | MinIO | 9000 / 9001 | Local GCS emulation |
| Messaging | Redpanda (Kafka-compatible) | 9092 / 9644 | CDC event bus |

### Backend

- **Language**: Python 3.13
- **AI Agent Framework**: Google ADK (`google-adk>=1.0.0`)
- **Web Framework**: FastAPI + uvicorn
- **Package Manager**: `uv`
- **Type Checking**: `mypy --strict`
- **Linter**: `ruff`
- **Testing**: `pytest` + `pytest-asyncio`
- **Dependency Management**: `pyproject.toml` + `uv.lock`

### Frontend (Admin Dashboard)

- **Language**: TypeScript (strict mode)
- **Framework**: Next.js 15 (App Router)
- **UI Library**: React 19
- **Styling**: Tailwind CSS v4
- **State Management**: Zustand
- **Data Fetching**: TanStack Query v5
- **Graph Visualization**: React Flow (Memory Graph UI)
- **Package Manager**: `pnpm`
- **Type Checking**: `tsc --noEmit`
- **Linter**: ESLint + Prettier

---

## Directory Structure

```
dse/
├── CLAUDE.md                    # ← This file
├── Makefile                     # make dev / make test / make lint etc.
├── docker-compose.yml           # All local services
├── docker-compose.override.yml  # Development overrides (gitignored)
├── .env.example                 # List of required env vars (no values)
├── .env                         # Actual values (gitignored)
│
├── backend/                     # Python backend
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/
│   │   └── dse/
│   │       ├── __init__.py
│   │       ├── main.py              # FastAPI entry point
│   │       ├── config.py            # Settings / env vars (pydantic-settings)
│   │       │
│   │       ├── api/                 # REST API layer
│   │       │   ├── routers/
│   │       │   │   ├── memories.py  # /v1/memories CRUD
│   │       │   │   ├── retrieve.py  # /v1/memories/retrieve
│   │       │   │   ├── graph.py     # /v1/memories/graph
│   │       │   │   └── health.py    # /health
│   │       │   ├── deps.py          # FastAPI dependency injection
│   │       │   └── schemas.py       # Pydantic request/response schemas
│   │       │
│   │       ├── core/                # Domain models and business logic
│   │       │   ├── models.py        # MemoryRecord, Relation, etc.
│   │       │   ├── enums.py         # MemoryType, RelationType, etc.
│   │       │   └── exceptions.py    # Domain exceptions
│   │       │
│   │       ├── services/            # Service layer
│   │       │   ├── search.py        # Elasticsearch client
│   │       │   ├── embedding.py     # Gemini Embedding client
│   │       │   ├── storage.py       # GCS / MinIO client
│   │       │   ├── graph.py         # Neo4j client
│   │       │   ├── cache.py         # Redis client (Working Memory)
│   │       │   └── llm.py           # Gemini LLM client
│   │       │
│   │       ├── agents/              # Google ADK agents
│   │       │   ├── mma/             # Memory Management Agent
│   │       │   │   ├── agent.py     # ADK Agent definition
│   │       │   │   ├── tools.py     # ADK Tool definitions
│   │       │   │   └── prompts.py   # System prompt
│   │       │   ├── retrieval/       # Retrieval Agent
│   │       │   │   ├── agent.py
│   │       │   │   └── tools.py
│   │       │   └── middleware.py    # Memory-Augmented ReAct middleware
│   │       │
│   │       ├── workflows/           # Temporal workflows
│   │       │   ├── worker.py        # Temporal Worker entry point
│   │       │   ├── activities/      # Temporal Activity definitions
│   │       │   │   ├── indexing.py  # Index update activity
│   │       │   │   ├── decay.py     # Decay score update
│   │       │   │   ├── compress.py  # Semantic Compression
│   │       │   │   └── discover.py  # Relation discovery
│   │       │   └── definitions/     # Temporal Workflow definitions
│   │       │       ├── memory_write.py
│   │       │       ├── daily_maintenance.py
│   │       │       └── cdc_processor.py
│   │       │
│   │       ├── pipeline/            # Search pipeline
│   │       │   ├── retrieval.py     # Cascade Retrieval
│   │       │   ├── ranking.py       # Re-ranking and scoring
│   │       │   ├── assembly.py      # Context Assembly
│   │       │   └── preprocessing.py # Query preprocessing / Intent extraction
│   │       │
│   │       ├── mcp/                 # MCP server (AI Agent interface)
│   │       │   ├── __init__.py
│   │       │   ├── __main__.py      # python -m dse.mcp entry point
│   │       │   └── server.py        # FastMCP server definition
│   │       │
│   │       └── infrastructure/      # Infrastructure layer
│   │           ├── pii.py           # PII detection and anonymization
│   │           ├── provenance.py    # Lineage tracking
│   │           └── events.py        # CDC event publisher
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
│
├── frontend/                    # Next.js admin dashboard
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── app/                 # App Router
│       │   ├── layout.tsx
│       │   ├── page.tsx         # Dashboard home
│       │   ├── memories/        # Memory list and search
│       │   ├── graph/           # Memory graph visualization
│       │   ├── workflows/       # Temporal workflow monitoring
│       │   └── settings/        # Settings
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       │   ├── api.ts           # Backend API client
│       │   └── types.ts         # Shared type definitions
│       └── stores/              # Zustand stores
│
└── docs/
    ├── adr/                     # Architecture Decision Records
    └── api/                     # API specs (OpenAPI)
```

---

## Environment Setup

### Prerequisites

```bash
# Required tools
python 3.13+
uv >= 0.5
node >= 22
pnpm >= 9
docker + docker compose v2
gcloud CLI (authenticated)
```

### Initial Setup

```bash
# 1. After cloning the repository
cp .env.example .env
# Edit .env to set GCP project info, etc.

# 2. Start local services
make dev

# 3. Install backend dependencies
cd backend && uv sync

# 4. Install frontend dependencies
cd frontend && pnpm install

# 5. Initialize databases
make db-init
```

### Makefile Commands

```makefile
make dev          # Start all local services via Docker Compose
make dev-down     # Stop local services
make api          # Start FastAPI server (port 8000)
make mcp          # Start MCP server (stdio transport)
make mcp-http     # Start MCP server (streamable-http transport)
make worker       # Start Temporal Worker
make frontend     # Start Next.js dev server (port 3000)
make test         # Run all tests
make test-unit    # Run unit tests only
make test-int     # Run integration tests only
make lint         # ruff + mypy + tsc
make format       # ruff format + prettier
make db-init      # Initialize Neo4j schema and indexes
make db-reset     # Reset all local DBs (development only)
```

---

## Environment Variables

All variables are listed in `.env.example`. Below are the key variables.

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Elasticsearch
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=dse-memories
ELASTICSEARCH_VECTOR_DIMS=3072

# Gemini
GEMINI_API_KEY=your-api-key                   # For Gemini Developer API
GEMINI_LLM_MODEL=gemini-3.1-flash-lite-preview             # MMA reasoning model
GEMINI_EMBEDDING_MODEL=gemini-embedding-2-preview

# GCS / MinIO
GCS_BUCKET_NAME=dse-memories
# Local development: point to MinIO endpoint
STORAGE_ENDPOINT_URL=http://localhost:9000     # MinIO (local only)
STORAGE_ACCESS_KEY=minioadmin
STORAGE_SECRET_KEY=minioadmin

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Redis
REDIS_URL=redis://localhost:6379

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=dse-local
TEMPORAL_TASK_QUEUE=dse-main

# PostgreSQL (Temporal backend)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=temporal
POSTGRES_USER=temporal
POSTGRES_PASSWORD=temporal

# Redpanda / Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Application settings
APP_ENV=local                      # local | staging | production
USE_MOCK_LLM=false                 # true: replace Gemini API with mock
USE_MOCK_SEARCH=false              # true: replace Elasticsearch with mock
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000

# Security
JWT_SECRET_KEY=change-me-in-production
CORS_ORIGINS=http://localhost:3000
```

---

## Docker Compose Configuration

Local services managed by `docker-compose.yml`:

```yaml
# docker-compose.yml configuration (overview)
services:
  neo4j:
    image: neo4j:5
    ports: ["7474:7474", "7687:7687"]
    volumes: ["neo4j_data:/data"]
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc"]'

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]

  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: temporal
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal

  temporal:
    image: temporalio/auto-setup:1.24
    ports: ["7233:7233"]
    depends_on: [postgres]
    environment:
      DB: postgres12
      DB_PORT: 5432
      POSTGRES_USER: temporal
      POSTGRES_PWD: temporal
      POSTGRES_SEEDS: postgres

  temporal-ui:
    image: temporalio/ui:latest
    ports: ["8080:8080"]
    depends_on: [temporal]
    environment:
      TEMPORAL_ADDRESS: temporal:7233

  minio:
    image: minio/minio:latest
    ports: ["9000:9000", "9001:9001"]
    volumes: ["minio_data:/data"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"

  redpanda:
    image: redpandadata/redpanda:latest
    ports: ["9092:9092", "9644:9644"]
    command:
      - redpanda start
      - --smp 1
      - --memory 512M
      - --overprovisioned
      - --node-id 0
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://localhost:9092
```

---

## Backend Implementation Guidelines

### Configuration Management (`config.py`)

```python
# backend/src/dse/config.py
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # GCP
    google_cloud_project: str
    google_cloud_location: str = "us-central1"

    # Gemini
    gemini_llm_model: str = "gemini-3.1-flash-lite-preview"
    gemini_embedding_model: str = "gemini-embedding-2-preview"

    # Feature flags
    use_mock_llm: bool = False
    use_mock_search: bool = False

    # ... other settings

settings = Settings()
```

### Google ADK Agent Definition Pattern

```python
# backend/src/dse/agents/mma/agent.py
from __future__ import annotations
from google.adk.agents import Agent
from .tools import (
    store_memory_tool,
    detect_contradiction_tool,
    classify_relation_tool,
    compress_memories_tool,
)
from .prompts import MMA_SYSTEM_INSTRUCTION

memory_management_agent = Agent(
    model="gemini-3.1-flash-lite-preview",
    name="memory_management_agent",
    description="Agent that manages DSE memories. Handles new memory registration, contradiction detection, relation classification, and Semantic Compression.",
    instruction=MMA_SYSTEM_INSTRUCTION,
    tools=[
        store_memory_tool,
        detect_contradiction_tool,
        classify_relation_tool,
        compress_memories_tool,
    ],
)
```

### ADK Tool Definition Pattern

```python
# backend/src/dse/agents/mma/tools.py
from __future__ import annotations
from dse.services.search import SearchService
from dse.services.graph import GraphService

async def detect_contradiction_tool(
    memory_a_id: str,
    memory_b_id: str,
) -> dict:
    """
    Detect contradictions between two memories.

    Args:
        memory_a_id: ID of memory A
        memory_b_id: ID of memory B

    Returns:
        dict: is_contradictory (bool), reason (str), confidence (float)
    """
    # implementation
    ...
```

> **Important**: ADK Tool docstrings are used by the LLM to select tools.
> Always include `Args:` and `Returns:` sections.

### Temporal Workflow / Activity Pattern

```python
# backend/src/dse/workflows/activities/indexing.py
from __future__ import annotations
from temporalio import activity
from dse.services.search import SearchService
from dse.core.models import MemoryRecord

@activity.defn
async def upsert_search_index(record: MemoryRecord) -> str:
    """Upsert activity for the search index"""
    service = SearchService()
    return await service.upsert(record)

# backend/src/dse/workflows/definitions/memory_write.py
from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta

@workflow.defn
class MemoryWriteWorkflow:
    @workflow.run
    async def run(self, record_dict: dict) -> str:
        retry = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1))

        # Phase 1: Object Storage
        await workflow.execute_activity(
            "store_to_object_storage",
            record_dict,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        # Phase 2: Generate embedding
        await workflow.execute_activity(
            "generate_embedding",
            record_dict["id"],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )

        # Phase 3: Search Index
        await workflow.execute_activity(
            "upsert_search_index",
            record_dict,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        # Phase 4: Graph DB
        await workflow.execute_activity(
            "register_graph_node",
            record_dict["id"],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=retry,
        )

        return record_dict["id"]
```

### Elasticsearch Client

```python
# backend/src/dse/services/search.py
from __future__ import annotations
from elasticsearch import AsyncElasticsearch
from dse.config import settings

class SearchService:
    """Async Elasticsearch client (BM25 + kNN hybrid search)"""

    def __init__(self) -> None:
        self._client: AsyncElasticsearch | None = None
        self._index = settings.elasticsearch_index

    async def _get_client(self) -> AsyncElasticsearch:
        if self._client is None:
            self._client = AsyncElasticsearch(settings.elasticsearch_url)
        return self._client

    async def search(self, query: str, *, namespace: str | None = None, top_k: int = 20) -> list[dict]:
        client = await self._get_client()
        filters = []
        if namespace:
            filters.append({"term": {"namespace": namespace}})
        body = {
            "query": {"bool": {"should": [{"multi_match": {"query": query, "fields": ["summary^3", "content_text"]}}], "filter": filters}},
            "size": top_k,
        }
        resp = await client.search(index=self._index, body=body)
        return [{**hit["_source"], "id": hit["_id"]} for hit in resp["hits"]["hits"]]

    async def upsert(self, record) -> str:
        client = await self._get_client()
        await client.index(index=self._index, id=record.id, document=record.model_dump(mode="json"))
        return record.id

    async def delete(self, memory_id: str) -> None:
        client = await self._get_client()
        await client.delete(index=self._index, id=memory_id, ignore=[404])
```

### Gemini Embedding Client

```python
# backend/src/dse/services/embedding.py
from __future__ import annotations
import google.generativeai as genai
from dse.config import settings

class EmbeddingService:
    """Gemini Embedding client"""

    # Output dimensions for gemini-embedding-2-preview
    EMBEDDING_DIMS = 3072

    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._model = settings.gemini_embedding_model  # "gemini-embedding-2-preview"

    async def encode(self, text: str) -> list[float]:
        """Convert text to a vector"""
        result = genai.embed_content(
            model=self._model,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",  # For memory storage
        )
        return result["embedding"]

    async def encode_query(self, text: str) -> list[float]:
        """Convert query text to a vector (for search)"""
        result = genai.embed_content(
            model=self._model,
            content=text,
            task_type="RETRIEVAL_QUERY",  # For search queries
        )
        return result["embedding"]
```

### Gemini LLM Client

```python
# backend/src/dse/services/llm.py
from __future__ import annotations
import google.generativeai as genai
from dse.config import settings

class LLMService:
    """Gemini LLM client"""

    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.gemini_llm_model)

    async def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        """Generate text"""
        config = genai.GenerationConfig(
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        response = await self._model.generate_content_async(
            prompt,
            generation_config=config,
        )
        return response.text

    async def classify_relation(
        self,
        summary_a: str,
        summary_b: str,
    ) -> dict:
        """Classify the relationship between two memories"""
        prompt = f"""
Classify the relationship between the following two memories.

Memory A: {summary_a}
Memory B: {summary_b}

Return ONLY the following JSON:
{{"type": "SUPERSEDES|COMPLEMENTS|CONTRADICTS|DERIVES|CAUSES|REFERENCES|NONE", "confidence": 0.0-1.0, "reason": "..."}}
"""
        result = await self.generate(prompt, json_mode=True)
        import json
        return json.loads(result)
```

### Error Handling Conventions

```python
# Exceptions are defined in dse/core/exceptions.py
class DSEError(Exception):
    """Base exception class"""

class MemoryNotFoundError(DSEError):
    """Memory not found"""

class SearchServiceError(DSEError):
    """Elasticsearch error"""

class EmbeddingError(DSEError):
    """Embedding generation error"""

class GraphError(DSEError):
    """Neo4j graph operation error"""

# FastAPI error responses must follow this format:
# {"error": {"code": "MEMORY_NOT_FOUND", "message": "...", "details": {}}}
```

---

## Frontend Implementation Guidelines

### API Client (`lib/api.ts`)

```typescript
// frontend/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function retrieveMemories(params: RetrieveParams): Promise<AssembledContext> {
  const res = await fetch(`${API_BASE}/v1/memories/retrieve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new ApiError(await res.json());
  return res.json();
}
```

### Component Conventions

- Default to Server Components; only add `"use client"` for interactive parts
- Use TanStack Query for data fetching (do not use Server Actions)
- Organize components into `components/ui/` (generic) and `components/features/` (feature-specific)
- Use the `cn()` utility (`clsx` + `tailwind-merge`) for Tailwind classes

---

## Elasticsearch Setup

### 1. Start Locally via Docker Compose

```bash
make dev   # Elasticsearch 8.x starts at http://localhost:9200
```

The index is auto-created on the first connection by `SearchService` (`dse-memories`).

### 2. Index Mapping

The mapping definition is managed in `docs/elasticsearch_mapping.json`.
`SearchService._get_client()` auto-applies it when the index does not exist.
Key fields:

- `summary`, `content_text`: `text` type (BM25 full-text search)
- `embedding`: `dense_vector` type (3072 dimensions, cosine similarity, kNN search)
- `memory_type`, `namespace`, `is_archived`: `keyword`/`boolean` types (for filtering)
- `confidence`, `decay_score`, `importance_score`: `float` type

Always create an ADR and update `docs/elasticsearch_mapping.json` for any schema changes.

---

## Temporal Workflow Design

### Task Queue Assignments

| Task Queue | Responsible Workflows / Activities |
|-----------|-------------------------------|
| `dse-main` | MemoryWriteWorkflow, CDCProcessorWorkflow |
| `dse-maintenance` | DailyMaintenanceWorkflow (Decay updates, Semantic Compression) |
| `dse-discovery` | RelationDiscoveryWorkflow |

### Schedule Definitions

```python
# backend/src/dse/workflows/schedules.py
# Workflows executed on a schedule via Temporal Schedule

SCHEDULES = [
    {
        "id": "daily-maintenance",
        "workflow": "DailyMaintenanceWorkflow",
        "cron": "0 2 * * *",        # Daily at 02:00 UTC
        "task_queue": "dse-maintenance",
    },
    {
        "id": "weekly-compression",
        "workflow": "SemanticCompressionWorkflow",
        "cron": "0 3 * * 0",        # Weekly on Sunday at 03:00 UTC
        "task_queue": "dse-maintenance",
    },
    {
        "id": "relation-discovery",
        "workflow": "RelationDiscoveryWorkflow",
        "cron": "0 4 * * *",        # Daily at 04:00 UTC
        "task_queue": "dse-discovery",
    },
    {
        "id": "prospective-scan",
        "workflow": "ProspectiveScanWorkflow",
        "cron": "* * * * *",        # Every minute (prospective memory trigger check)
        "task_queue": "dse-main",
    },
]
```

---

## Testing Strategy

### Unit Tests

- Mock all external services (Elasticsearch, Gemini, Neo4j, Redis)
- Use `pytest-mock` and `unittest.mock.AsyncMock`
- Coverage target: 80% or higher (measured with `make test`)

```python
# tests/unit/test_ranking.py
import pytest
from dse.pipeline.ranking import compute_final_score
from dse.core.models import MemoryRecord

def test_superseded_memory_has_low_score():
    record = MemoryRecord(id="test", superseded_by="other-id", ...)
    score = compute_final_score(record, rrf_score=0.9)
    assert score < 0.2  # Penalty is applied
```

### Integration Tests

- `tests/integration/` connects to actual local Docker services (Neo4j, Redis)
- Elasticsearch and Gemini are mocked via `USE_MOCK_SEARCH=true` / `USE_MOCK_LLM=true`
- Skips with `pytest.skip()` if `docker compose` is not running

### E2E Tests

- `tests/e2e/` connects to real GCP resources — runs only in CI (excluded from local `make test`)

---

## CI/CD (GitHub Actions)

Place the following in `.github/workflows/`:

| Workflow | Trigger | Content |
|----------|---------|---------|
| `ci.yml` | PR / push to main | lint + type check + unit test |
| `integration.yml` | push to main | integration test (Docker Compose) |
| `e2e.yml` | push to main | E2E test (GCP staging environment) |
| `deploy-staging.yml` | push to main | Deploy to staging environment |

---

## Neo4j Schema Initialization

```cypher
// docs/neo4j/init.cypher
// Constraint definitions
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
  FOR (m:Memory) REQUIRE m.id IS UNIQUE;

// Index definitions
CREATE INDEX memory_namespace IF NOT EXISTS
  FOR (m:Memory) ON (m.namespace);

CREATE INDEX memory_type IF NOT EXISTS
  FOR (m:Memory) ON (m.memory_type);

CREATE INDEX memory_created_at IF NOT EXISTS
  FOR (m:Memory) ON (m.created_at);

// Relation types (comments only — Neo4j does not require predefined relation types)
// SUPERSEDED_BY, COMPLEMENTS, CONTRADICTS, DERIVES, CAUSES, REFERENCES,
// HAS_CHILD, TEMPORALLY_PRECEDES
```

---

## Logging Conventions

```python
# Unified across all modules in backend/src/dse/
import structlog

logger = structlog.get_logger(__name__)

# Usage
logger.info("memory.stored", memory_id=record.id, memory_type=record.memory_type)
logger.error("search.failed", error=str(e), query=query)
```

- Use `structlog` with JSON-formatted log output
- Local development: human-readable format (`ConsoleRenderer`)
- Production / staging: JSON (`JSONRenderer`)

---

## Common Implementation Mistakes (Avoid These)

1. **Forgetting to close the async Elasticsearch client**
   → Call `SearchService.close()` in the lifespan shutdown handler

2. **Not using `await` properly in Temporal Activities**
   → Use `async def` activities instead of `asyncio.get_event_loop().run_until_complete()`
   → `@activity.defn` supports `async def`

3. **Elasticsearch filter syntax mistakes**
   → The `filter` in a `bool` query must be passed as an array. Be careful with `term` vs `terms`
   → Official docs: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html

4. **Forgetting to differentiate Gemini Embedding `task_type`**
   → Storage: `RETRIEVAL_DOCUMENT`
   → Search queries: `RETRIEVAL_QUERY`
   → Similarity only: `SEMANTIC_SIMILARITY`

5. **Mixing Neo4j `async` and `sync` drivers**
   → Use only `AsyncDriver` from `neo4j-driver` in FastAPI

6. **MinIO and GCS API compatibility**
   → MinIO uses the S3-compatible API. Use `boto3` or `aiobotocore` instead of the GCS client library
   → Alternatively, use `google-cloud-storage` and point to the GCS emulator locally via the `STORAGE_EMULATOR_HOST` env var

7. **Omitting ADK Tool docstrings**
   → Without docstrings, the LLM cannot correctly invoke tools

8. **Temporal side effects**
   → Do not call `datetime.now()` or `random.random()` directly in Workflow code
   → Use `workflow.now()` and `workflow.random()` instead

---

## MCP Server (AI Agent Interface)

DSE provides a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server,
enabling AI agents to perform memory operations via the standard protocol.

### Starting the Server

```bash
# stdio transport (Claude Desktop / Claude Code, etc.)
make mcp

# streamable-http transport (for remote connections)
make mcp-http
```

### Available Tools

| Tool Name | Description |
|-----------|-------------|
| `retrieve_memories` | Search and retrieve related memories via the Cascade Retrieval pipeline |
| `search_memories` | Direct text search (BM25) on memories |
| `store_memory` | Register a new memory (includes embedding generation, indexing, and graph registration) |
| `get_memory` | Retrieve a memory by ID |
| `update_memory` | Partially update a memory |
| `delete_memory` | Delete a memory |
| `get_related_memories` | Traverse the graph to find related memories |
| `create_memory_relation` | Create a relationship between memories |
| `working_memory_add` | Add an entry to Working Memory (session short-term memory) |
| `working_memory_get` | Retrieve entries from Working Memory |

### Resources

| URI Pattern | Description |
|-------------|-------------|
| `dse://memories/{memory_id}` | Read a memory record |
| `dse://graph/{memory_id}/neighbors` | Read graph neighbor nodes |

### Prompts

| Prompt Name | Description |
|-------------|-------------|
| `memory_context` | Format memory search results as a context prompt |

### Claude Desktop Configuration Example

```json
{
  "mcpServers": {
    "dse": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/dse/backend", "python", "-m", "dse.mcp"],
      "env": {
        "USE_MOCK_LLM": "true",
        "USE_MOCK_SEARCH": "true"
      }
    }
  }
}
```

---

## Reference Documentation

- [Elasticsearch](https://docs.cloud.google.com/generative-ai-app-builder/docs)
- [Gemini API Models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Temporal Python SDK](https://docs.temporal.io/workflows)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [DSE Design Report](./docs/DSE_Design_Report.md)
