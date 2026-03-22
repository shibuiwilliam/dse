# DSE Example Chat

A general-purpose chat UI powered by **Claude Agent SDK** and **DSE** (Dynamic Search Engine for Agentic Memory). The AI assistant has persistent memory — it remembers things across conversations using Elasticsearch, Neo4j, and Redis.

## Architecture

```
┌─────────────────────┐     SSE Stream      ┌──────────────────────────┐
│   React Chat UI     │ ◄─────────────────► │  Express Server (:4000)  │
│   (Vite :4001)      │     POST /api/chat   │  (Claude Agent SDK)      │
│                     │                      │                          │
│ - Message bubbles   │                      │  query({                 │
│ - Tool activity bar │                      │    prompt: "...",        │
│ - 14 DSE tools      │                      │    mcpServers: { dse }   │
└─────────────────────┘                      │  })                      │
                                             └──────────┬───────────────┘
                                                        │ MCP (HTTP or stdio)
                                             ┌──────────▼───────────────┐
                                             │  DSE MCP Server (:8001)  │
                                             │  14 tools:               │
                                             │  retrieve · search ·      │
                                             │  store · update · delete  │
                                             │  get_related · relations  │
                                             │  namespaces · sessions    │
                                             └──────────┬───────────────┘
                                                        │
                                     ┌──────────────────┼──────────────────┐
                                     │                  │                  │
                              Elasticsearch         Neo4j            Redis
                              (:9200)           (:7687)          (:6379)
```

### Port allocation

| Port | Service | Owner |
|------|---------|-------|
| 3000 | Next.js dashboard | DSE frontend |
| 4000 | Express chat backend | example-chat |
| 4001 | Vite dev server | example-chat (dev only) |
| 8000 | FastAPI | DSE backend |
| 8001 | MCP server (HTTP) | DSE |
| 8080 | Temporal UI | DSE |
| 9200 | Elasticsearch | DSE |
| 7474/7687 | Neo4j | DSE |
| 6379 | Redis | DSE |

## Quick Start

### Prerequisites

- Node.js 18+
- DSE running via `make run-all` (from the repo root)
- An [Anthropic API key](https://platform.claude.com/)

### 1. Install and configure

```bash
cd example-chat
npm install
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY and DSE_NAMESPACE
```

### 2. Run

```bash
# Start the backend (port 4000) — connects to DSE MCP via HTTP
npm run dev

# In another terminal, start the frontend dev server (port 4001)
npm run dev:client
```

Open **http://localhost:4001** in your browser.

## MCP Connection Modes

### HTTP mode (recommended)

When DSE is running via `make run-all`, the MCP server is at `http://localhost:8001/mcp`:

```bash
DSE_MCP_URL=http://localhost:8001/mcp
```

### stdio mode

Spawns DSE MCP as a subprocess. Useful when running standalone:

```bash
# Comment out DSE_MCP_URL and set:
DSE_BACKEND_DIR=../backend
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | (required) |
| `DSE_MCP_URL` | DSE MCP HTTP endpoint | `http://localhost:8001/mcp` |
| `DSE_BACKEND_DIR` | Path to DSE backend (stdio mode) | `../backend` |
| `DSE_NAMESPACE` | Namespace for chat memories | `user:engineer-dev` |
| `PORT` | Express server port | `4000` |

## What Claude Can Do

Claude has access to all 14 DSE tools:

| Category | Tools | Description |
|----------|-------|-------------|
| **Retrieval** | `retrieve_memories`, `search_memories`, `get_memory`, `get_related_memories` | BM25 + kNN cascade search, graph traversal |
| **Storage** | `store_memory`, `update_memory`, `delete_memory` | Create/update/delete with auto embedding + graph |
| **Graph** | `create_memory_relation` | 8 edge types (COMPLEMENTS, DERIVES, CAUSES, etc.) |
| **Namespaces** | `list_namespaces`, `get_namespace` | Browse available memory scopes |
| **Session** | `working_memory_add`, `working_memory_get` | Redis Stream session buffer |

Every conversation turn is guaranteed to be stored — Claude stores actively, with a server-side fallback if it skips.
