"""DSE MCP Server — exposes memory operations as MCP tools for AI agents.

Run with:
    uv run python -m dse.mcp.server          # stdio (default)
    uv run python -m dse.mcp.server --http    # streamable-http on MCP_PORT
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from dse.api.deps import (
    get_cache_service,
    get_embedding_service,
    get_graph_service,
    get_llm_service,
    get_retrieval_pipeline,
    get_search_service,
)
from dse.config import configure_logging, settings
from dse.core.enums import (
    CascadeStage,
    ContentType,
    MemorySubtype,
    MemoryType,
    RelationType,
    SourceType,
)
from dse.core.models import MemoryRecord, RelationRecord

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: initialise shared services once, clean up on shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Startup / shutdown lifecycle for the MCP server."""
    configure_logging(settings.log_level)
    logger.info(
        "mcp.starting",
        env=settings.app_env,
        mock_llm=settings.use_mock_llm,
        mock_search=settings.use_mock_search,
    )
    yield {}
    # Shutdown: close service connections
    import contextlib

    with contextlib.suppress(Exception):
        await get_search_service().close()
    with contextlib.suppress(Exception):
        await get_graph_service().close()
    with contextlib.suppress(Exception):
        await get_cache_service().close()
    logger.info("mcp.shutting_down")


mcp = FastMCP(
    "DSE — Dynamic Search Engine for Agentic Memory",
    lifespan=_lifespan,
    host="0.0.0.0",
    port=int(os.environ.get("MCP_PORT", "8001")),
)


# ---------------------------------------------------------------------------
# Tools: Memory Retrieval
# ---------------------------------------------------------------------------


@mcp.tool()
async def retrieve_memories(
    query: str,
    namespace: str | None = None,
    memory_types: list[str] | None = None,
    token_budget: int = 4000,
    cascade_stage: str | None = None,
    task_context: str = "",
    top_k: int = 10,
) -> str:
    """Search and retrieve relevant memories using the cascade retrieval pipeline.

    This is the primary tool for recalling memories. It performs multi-stage
    search (fast→precision→deep) combining full-text, vector, and graph-based
    retrieval, then assembles results within a token budget.

    Args:
        query: Natural language search query describing what you want to recall.
        namespace: Scope filter (e.g. "agent:123" or "project:abc"). If None, searches all.
        memory_types: Filter by type: "episodic", "semantic", "procedural", "prospective".
        token_budget: Maximum tokens for the assembled context (100–100000).
        cascade_stage: Override retrieval stage: "fast", "precision", or "deep".
        task_context: Description of the current task for better relevance ranking.
        top_k: Maximum number of memories to return (1–100).

    Returns:
        JSON with retrieved memory items, total tokens used, and the query.
    """
    pipeline = get_retrieval_pipeline()

    stage = CascadeStage(cascade_stage) if cascade_stage else None
    token_budget = max(100, min(100000, token_budget))
    top_k = max(1, min(100, top_k))

    assembled = await pipeline.retrieve(
        query,
        namespace=namespace,
        memory_types=memory_types,
        token_budget=token_budget,
        cascade_stage=stage,
        task_context=task_context,
    )

    items = []
    for item in assembled.items[:top_k]:
        items.append(
            {
                "memory_id": item.memory_id,
                "memory_type": item.memory_type.value
                if hasattr(item.memory_type, "value")
                else str(item.memory_type),
                "content": item.content,
                "tier": item.tier,
                "score": round(item.score, 4),
                "confidence": round(item.confidence, 4),
                "created_at": item.created_at.isoformat(),
                "tokens": item.tokens,
            }
        )

    return json.dumps(
        {
            "items": items,
            "total_tokens": assembled.total_tokens,
            "query": assembled.query,
            "namespace": assembled.namespace,
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def search_memories(
    query: str,
    namespace: str | None = None,
    memory_types: list[str] | None = None,
    top_k: int = 20,
) -> str:
    """Perform a direct text search against the memory index.

    Use this for simple keyword/text lookups without the full cascade pipeline.
    For richer semantic retrieval, use retrieve_memories instead.

    Args:
        query: Search query text.
        namespace: Scope filter (e.g. "agent:123").
        memory_types: Filter by type: "episodic", "semantic", "procedural", "prospective".
        top_k: Maximum number of results (1–100).

    Returns:
        JSON array of matching memory records.
    """
    search = get_search_service()
    top_k = max(1, min(100, top_k))

    results = await search.search(
        query,
        namespace=namespace,
        memory_types=memory_types,
        top_k=top_k,
    )

    cleaned = []
    for r in results:
        cleaned.append(
            {
                "id": r.get("id", ""),
                "namespace": r.get("namespace", ""),
                "summary": r.get("summary", ""),
                "content_text": r.get("content_text", "")[:500],
                "memory_type": r.get("memory_type", ""),
                "confidence": r.get("confidence", 0.5),
                "decay_score": r.get("decay_score", 1.0),
                "importance_score": r.get("importance_score", 0.5),
                "tags": r.get("tags", []),
                "created_at": str(r.get("created_at", "")),
            }
        )

    return json.dumps(cleaned, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tools: Memory CRUD
# ---------------------------------------------------------------------------


@mcp.tool()
async def store_memory(
    namespace: str,
    content_text: str,
    summary: str = "",
    memory_type: str = "episodic",
    memory_subtype: str = "observation",
    content_type: str = "text",
    confidence: float = 0.5,
    source_type: str = "observation",
    source_id: str = "",
    tags: list[str] | None = None,
    entities: list[str] | None = None,
    language: str = "ja",
) -> str:
    """Store a new memory record in the DSE system.

    Creates a memory with LLM-based enrichment (summary, tags, entities,
    importance inference), embedding generation, search indexing, and
    knowledge graph registration.

    Only ``namespace`` and ``content_text`` are required. All other fields
    are automatically inferred by the LLM when omitted.

    Args:
        namespace: Scope identifier (e.g. "agent:my-agent" or "project:my-project").
        content_text: Full text content of the memory.
        summary: Short summary (max 500 chars). Auto-inferred by LLM if empty.
        memory_type: One of "episodic", "semantic", "procedural", "prospective".
        memory_subtype: One of "observation", "inference", "user_explicit", "agent_generated".
        content_type: One of "text", "image", "audio", "document", "code", "structured_data".
        confidence: Initial confidence score (0.0–1.0).
        source_type: One of "observation", "inference", "user_explicit", "external_api".
        source_id: Identifier of the information source.
        tags: List of tags for categorization. Auto-inferred by LLM if empty.
        entities: List of named entities mentioned. Auto-inferred by LLM if empty.
        language: Language code (default: "ja").

    Returns:
        JSON with the created memory's id and metadata including inferred fields.
    """
    # 1. Enrich content via LLM (summary, tags, entities, importance)
    llm_svc = get_llm_service()
    enrichment = await llm_svc.enrich_memory(content_text)

    resolved_summary = summary or str(enrichment.get("summary", content_text[:200]))
    resolved_tags = tags if tags is not None else list(enrichment.get("tags", []))
    resolved_entities = entities if entities is not None else list(enrichment.get("entities", []))
    importance_score = float(enrichment.get("importance_score", 0.5))

    # 2. Create record
    record = MemoryRecord(
        namespace=namespace,
        content_text=content_text,
        summary=resolved_summary,
        memory_type=MemoryType(memory_type),
        memory_subtype=MemorySubtype(memory_subtype),
        content_type=ContentType(content_type),
        confidence=max(0.0, min(1.0, confidence)),
        source_type=SourceType(source_type),
        source_id=source_id,
        importance_score=max(0.0, min(1.0, importance_score)),
        tags=resolved_tags,
        entities=resolved_entities,
        language=language,
    )

    # 3. Generate embedding from enriched summary + entities
    embedding_svc = get_embedding_service()
    embed_text = f"{record.summary} {' '.join(record.entities)}"
    record.embedding = await embedding_svc.encode(embed_text)

    # 4. Index in search engine
    search_svc = get_search_service()
    await search_svc.upsert(record)

    # 5. Register in graph
    graph_svc = get_graph_service()
    await graph_svc.register_node(record)

    logger.info("mcp.memory_stored", memory_id=record.id, namespace=namespace)

    return json.dumps(
        {
            "id": record.id,
            "namespace": record.namespace,
            "summary": record.summary,
            "memory_type": record.memory_type.value,
            "confidence": record.confidence,
            "importance_score": record.importance_score,
            "tags": record.tags,
            "entities": record.entities,
            "created_at": record.created_at.isoformat(),
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def get_memory(memory_id: str) -> str:
    """Get a single memory record by its ID.

    Args:
        memory_id: The UUID of the memory to retrieve.

    Returns:
        JSON with the full memory record, or an error if not found.
    """
    search_svc = get_search_service()
    doc = await search_svc.get_by_id(memory_id)

    if doc is None:
        return json.dumps({"error": "Memory not found", "memory_id": memory_id})

    return json.dumps(
        {
            "id": doc.get("id", ""),
            "namespace": doc.get("namespace", ""),
            "summary": doc.get("summary", ""),
            "content_text": doc.get("content_text", ""),
            "memory_type": doc.get("memory_type", ""),
            "memory_subtype": doc.get("memory_subtype", ""),
            "confidence": doc.get("confidence", 0.5),
            "decay_score": doc.get("decay_score", 1.0),
            "importance_score": doc.get("importance_score", 0.5),
            "verification_status": doc.get("verification_status", ""),
            "tags": doc.get("tags", []),
            "entities": doc.get("entities", []),
            "is_archived": doc.get("is_archived", False),
            "created_at": str(doc.get("created_at", "")),
            "updated_at": str(doc.get("updated_at", "")),
            "superseded_by": doc.get("superseded_by"),
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def update_memory(
    memory_id: str,
    summary: str | None = None,
    content_text: str | None = None,
    confidence: float | None = None,
    importance_score: float | None = None,
    tags: list[str] | None = None,
    entities: list[str] | None = None,
    is_archived: bool | None = None,
) -> str:
    """Update fields of an existing memory record.

    Only provided fields are updated; others remain unchanged.

    Args:
        memory_id: The UUID of the memory to update.
        summary: New summary text.
        content_text: New content text.
        confidence: New confidence score (0.0–1.0).
        importance_score: New importance score (0.0–1.0).
        tags: New list of tags (replaces existing).
        entities: New list of entities (replaces existing).
        is_archived: Set to true to archive, false to unarchive.

    Returns:
        JSON confirming the update with updated fields.
    """
    search_svc = get_search_service()
    existing = await search_svc.get_by_id(memory_id)
    if existing is None:
        return json.dumps({"error": "Memory not found", "memory_id": memory_id})

    fields: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
    if summary is not None:
        fields["summary"] = summary
    if content_text is not None:
        fields["content_text"] = content_text
        # Re-generate embedding if content changed
        embedding_svc = get_embedding_service()
        fields["embedding"] = await embedding_svc.encode(content_text)
    if confidence is not None:
        fields["confidence"] = max(0.0, min(1.0, confidence))
    if importance_score is not None:
        fields["importance_score"] = max(0.0, min(1.0, importance_score))
    if tags is not None:
        fields["tags"] = tags
    if entities is not None:
        fields["entities"] = entities
    if is_archived is not None:
        fields["is_archived"] = is_archived
        if is_archived:
            fields["archived_at"] = datetime.now(UTC).isoformat()

    await search_svc.patch(memory_id, fields)

    logger.info("mcp.memory_updated", memory_id=memory_id, fields=list(fields.keys()))

    return json.dumps(
        {"memory_id": memory_id, "updated_fields": list(fields.keys())},
        ensure_ascii=False,
    )


@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """Delete a memory record permanently.

    Removes the memory from search index and knowledge graph.

    Args:
        memory_id: The UUID of the memory to delete.

    Returns:
        JSON confirming the deletion.
    """
    search_svc = get_search_service()
    graph_svc = get_graph_service()

    await search_svc.delete(memory_id)
    await graph_svc.delete_node(memory_id)

    logger.info("mcp.memory_deleted", memory_id=memory_id)

    return json.dumps({"deleted": True, "memory_id": memory_id})


# ---------------------------------------------------------------------------
# Tools: Namespace Management
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_namespaces() -> str:
    """List all available namespaces in the DSE system.

    Returns:
        JSON array of namespace strings.
    """
    search_svc = get_search_service()
    namespaces = await search_svc.list_namespaces()
    return json.dumps(namespaces, ensure_ascii=False)


@mcp.tool()
async def get_namespace(namespace: str) -> str:
    """Get details and statistics for a namespace.

    Args:
        namespace: The namespace identifier (e.g. "agent:my-agent").

    Returns:
        JSON with total_memories, archived_count, and memory_type_distribution.
        Returns an error if the namespace does not exist.
    """
    search_svc = get_search_service()
    namespaces = await search_svc.list_namespaces()
    if namespace not in namespaces:
        return json.dumps({"error": "Namespace not found", "namespace": namespace})

    stats = await search_svc.get_namespace_stats(namespace)
    return json.dumps(stats, ensure_ascii=False, default=str)


@mcp.tool()
async def create_namespace(namespace: str) -> str:
    """Create a new namespace.

    Registers the namespace so it appears in list_namespaces even before
    any real memories are stored.

    Args:
        namespace: The namespace identifier to create (e.g. "agent:my-agent" or "project:my-project").

    Returns:
        JSON confirming the creation, or an error if it already exists.
    """
    search_svc = get_search_service()
    existing = await search_svc.list_namespaces()
    if namespace in existing:
        return json.dumps({"error": "Namespace already exists", "namespace": namespace})

    from dse.core.models import MemoryRecord

    placeholder = MemoryRecord(
        namespace=namespace,
        summary="__namespace_placeholder__",
        content_text="",
        is_archived=True,
    )
    await search_svc.upsert(placeholder)
    logger.info("mcp.namespace_created", namespace=namespace)
    return json.dumps({"namespace": namespace, "status": "created"}, ensure_ascii=False)


@mcp.tool()
async def delete_namespace(namespace: str) -> str:
    """Delete a namespace and ALL its memories permanently.

    This removes every memory in the namespace from both the search index
    and the knowledge graph. This action cannot be undone.

    Args:
        namespace: The namespace identifier to delete.

    Returns:
        JSON with deletion counts from search and graph.
    """
    search_svc = get_search_service()
    graph_svc = get_graph_service()

    namespaces = await search_svc.list_namespaces()
    if namespace not in namespaces:
        return json.dumps({"error": "Namespace not found", "namespace": namespace})

    search_deleted = await search_svc.delete_by_namespace(namespace)
    graph_deleted = await graph_svc.delete_by_namespace(namespace)

    logger.info(
        "mcp.namespace_deleted",
        namespace=namespace,
        search_deleted=search_deleted,
        graph_deleted=graph_deleted,
    )

    return json.dumps(
        {
            "namespace": namespace,
            "status": "deleted",
            "search_deleted": search_deleted,
            "graph_deleted": graph_deleted,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Tools: Graph Operations
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_related_memories(
    memory_id: str,
    hop_depth: int = 1,
    limit: int = 10,
) -> str:
    """Get memories related to a given memory via the knowledge graph.

    Traverses the Neo4j graph to find neighboring memories connected by
    relationships like COMPLEMENTS, DERIVES, CAUSES, REFERENCES, etc.

    Args:
        memory_id: The UUID of the central memory.
        hop_depth: Graph traversal depth (1–3).
        limit: Maximum number of neighbors to return (1–50).

    Returns:
        JSON with the list of related memories and their relationship types.
    """
    graph_svc = get_graph_service()
    hop_depth = max(1, min(3, hop_depth))
    limit = max(1, min(50, limit))

    neighbors = await graph_svc.get_neighbors(
        memory_id,
        hop_depth=hop_depth,
        limit=limit,
    )

    return json.dumps(
        {"memory_id": memory_id, "neighbors": neighbors},
        ensure_ascii=False,
        default=str,
    )


@mcp.tool()
async def create_memory_relation(
    from_id: str,
    to_id: str,
    relation_type: str,
    confidence: float = 0.5,
) -> str:
    """Create a relationship between two memories in the knowledge graph.

    Args:
        from_id: Source memory UUID.
        to_id: Target memory UUID.
        relation_type: One of "SUPERSEDED_BY", "COMPLEMENTS", "CONTRADICTS",
                       "DERIVES", "TEMPORALLY_PRECEDES", "CAUSES", "HAS_CHILD", "REFERENCES".
        confidence: Confidence in this relationship (0.0–1.0).

    Returns:
        JSON confirming the relation creation.
    """
    graph_svc = get_graph_service()

    rel = RelationRecord(
        from_id=from_id,
        to_id=to_id,
        relation_type=RelationType(relation_type),
        confidence=max(0.0, min(1.0, confidence)),
        created_by="mcp",
        method="agent_explicit",
    )
    await graph_svc.create_relation(rel)

    logger.info(
        "mcp.relation_created",
        from_id=from_id,
        to_id=to_id,
        relation_type=relation_type,
    )

    return json.dumps(
        {
            "created": True,
            "from_id": from_id,
            "to_id": to_id,
            "relation_type": relation_type,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Tools: Working Memory (Session)
# ---------------------------------------------------------------------------


@mcp.tool()
async def working_memory_add(
    session_id: str,
    content: str,
    role: str = "assistant",
) -> str:
    """Add an entry to the working memory (short-term session memory).

    Working memory is backed by Redis Streams and automatically expires based on TTL.

    Args:
        session_id: Session identifier for scoping.
        content: Text content to store in working memory.
        role: Role of the entry creator (e.g. "user", "assistant", "system").

    Returns:
        JSON confirming the entry was added with its turn ID.
    """
    cache_svc = get_cache_service()
    turn_id = await cache_svc.append_turn(
        session_id,
        {"role": role, "content": content},
    )

    return json.dumps(
        {"added": True, "session_id": session_id, "role": role, "turn_id": turn_id},
        ensure_ascii=False,
    )


@mcp.tool()
async def working_memory_get(
    session_id: str,
    limit: int = 50,
) -> str:
    """Retrieve recent turns from working memory for a session.

    Args:
        session_id: Session identifier.
        limit: Maximum number of turns to return (1–200).

    Returns:
        JSON array of working memory turns (most recent last).
    """
    cache_svc = get_cache_service()
    limit = max(1, min(200, limit))

    entries = await cache_svc.get_recent_turns(session_id, count=limit)

    return json.dumps(entries, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("dse://memories/{memory_id}")
async def memory_resource(memory_id: str) -> str:
    """Read a single memory record by ID.

    Args:
        memory_id: The UUID of the memory.
    """
    search_svc = get_search_service()
    doc = await search_svc.get_by_id(memory_id)
    if doc is None:
        return json.dumps({"error": "Memory not found", "memory_id": memory_id})
    return json.dumps(doc, ensure_ascii=False, default=str)


@mcp.resource("dse://graph/{memory_id}/neighbors")
async def graph_neighbors_resource(memory_id: str) -> str:
    """Read the graph neighbors of a memory.

    Args:
        memory_id: The UUID of the central memory.
    """
    graph_svc = get_graph_service()
    neighbors = await graph_svc.get_neighbors(memory_id, limit=20)
    return json.dumps(
        {"memory_id": memory_id, "neighbors": neighbors},
        ensure_ascii=False,
        default=str,
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
async def memory_context(query: str, namespace: str = "") -> str:
    """Retrieve relevant memories and format as a context prompt.

    Use this to inject memory context into your conversation.

    Args:
        query: What memories to search for.
        namespace: Optional scope filter.
    """
    pipeline = get_retrieval_pipeline()
    assembled = await pipeline.retrieve(
        query,
        namespace=namespace or None,
        token_budget=4000,
    )

    parts = [f"## Retrieved Memories for: {query}\n"]
    for item in assembled.items:
        mt = item.memory_type.value if hasattr(item.memory_type, "value") else str(item.memory_type)
        parts.append(
            f"- **[{mt}]** (confidence={item.confidence:.2f}, score={item.score:.2f}): "
            f"{item.content}"
        )

    if not assembled.items:
        parts.append("_No relevant memories found._")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the DSE MCP server."""
    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
