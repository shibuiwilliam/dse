from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from dse.api.deps import (
    get_cache_service,
    get_embedding_service,
    get_graph_service,
    get_llm_service,
    get_search_service,
    get_storage_service,
)
from dse.api.schemas import (
    CurateRequest,
    EvidenceRequest,
    FeedbackRequest,
    MemoryCreateRequest,
    MemoryResponse,
    MemoryUpdateRequest,
)
from dse.core.models import Evidence, MemoryRecord
from dse.services.cache import CacheService
from dse.services.embedding import EmbeddingService
from dse.services.graph import GraphService
from dse.services.llm import LLMService
from dse.services.search import SearchService
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/memories", tags=["memories"])


@router.post("", response_model=MemoryResponse, status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    search: Annotated[SearchService, Depends(get_search_service)],
    embedding: Annotated[EmbeddingService, Depends(get_embedding_service)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    graph: Annotated[GraphService, Depends(get_graph_service)],
    llm: Annotated[LLMService, Depends(get_llm_service)],
) -> MemoryResponse:
    """Create a new memory record (Write Path)."""
    # 1. Enrich content via LLM (summary, tags, entities, importance)
    enrichment = await llm.enrich_memory(request.content_text)

    summary = request.summary or str(enrichment.get("summary", request.content_text[:200]))
    tags = request.tags or list(enrichment.get("tags", []))
    entities = request.entities or list(enrichment.get("entities", []))
    importance_score = float(enrichment.get("importance_score", 0.5))

    # 2. Generate embedding from enriched summary + entities
    embed_text = f"{summary} {' '.join(entities)}" if summary else request.content_text
    vector = await embedding.encode(embed_text)

    # 3. Create record
    record = MemoryRecord(
        namespace=request.namespace,
        summary=summary,
        content_text=request.content_text,
        embedding=vector,
        memory_type=request.memory_type,
        memory_subtype=request.memory_subtype,
        content_type=request.content_type,
        confidence=request.confidence,
        source_type=request.source_type,
        source_id=request.source_id,
        importance_score=importance_score,
        tags=tags,
        entities=entities,
        language=request.language,
        trigger_type=request.trigger_type,
        trigger_at=request.trigger_at,
        trigger_condition=request.trigger_condition,
    )

    # 5. Store content in object storage
    content_path = await storage.store_content(record.namespace, record.id, record.content_text)
    record.content_path = content_path

    # 6. Upsert to search index
    await search.upsert(record)

    # 7. Register graph node
    await graph.register_node(record)

    logger.info(
        "memory.created",
        memory_id=record.id,
        memory_type=record.memory_type,
        namespace=record.namespace,
    )

    return _to_response(record)


@router.get("/stats", response_model=dict)
async def get_stats(
    namespace: str = Query(...),
    search: Annotated[SearchService, Depends(get_search_service)] = ...,  # noqa: B008
) -> dict[str, object]:
    """Get statistics for a namespace using ES aggregations (no top_k cap)."""
    stats = await search.get_namespace_detailed_stats(namespace)
    return stats


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    search: Annotated[SearchService, Depends(get_search_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> MemoryResponse:
    """Get a memory by ID."""
    # Try cache first
    cached = await cache.get_cached_memory(memory_id)
    if cached:
        return MemoryResponse(**cached)

    # Search by ID
    results = await search.search(
        memory_id,
        top_k=1,
        filter_archived=False,
    )
    if not results:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

    return MemoryResponse(**results[0])


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    search: Annotated[SearchService, Depends(get_search_service)],
    embedding: Annotated[EmbeddingService, Depends(get_embedding_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> MemoryResponse:
    """Update an existing memory record."""
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

    existing = results[0]

    # Apply updates
    update_data = request.model_dump(exclude_none=True)
    for key, value in update_data.items():
        existing[key] = value
    existing["updated_at"] = datetime.now(UTC).isoformat()

    # Re-embed if content changed
    if request.content_text or request.summary:
        embed_text = existing.get("summary", "") or existing.get("content_text", "")
        vector = await embedding.encode(embed_text)
        existing["embedding"] = vector

    record = MemoryRecord(**existing)
    await search.upsert(record)
    await cache.invalidate_memory(memory_id)

    logger.info("memory.updated", memory_id=memory_id)
    return _to_response(record)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    search: Annotated[SearchService, Depends(get_search_service)],
    graph: Annotated[GraphService, Depends(get_graph_service)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
    cascade: bool = Query(default=False),
) -> None:
    """Delete a memory record. With cascade=true, also deletes derived memories."""
    if cascade:
        # Find derived memories via graph and delete them too
        try:
            lineage = await graph.get_lineage(memory_id)
            for entry in lineage:
                for derived_id in entry.get("lineage", [])[1:]:
                    await search.delete(derived_id)
                    await graph.delete_node(derived_id)
                    await cache.invalidate_memory(derived_id)
        except Exception:
            logger.warning("memory.cascade_delete_partial", memory_id=memory_id)

    await search.delete(memory_id)
    await graph.delete_node(memory_id)
    await cache.invalidate_memory(memory_id)
    logger.info("memory.deleted", memory_id=memory_id, cascade=cascade)


@router.post("/{memory_id}/feedback", status_code=204)
async def record_feedback(
    memory_id: str,
    request: FeedbackRequest,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> None:
    """Record utility feedback for a memory (reinforcement)."""
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

    existing = results[0]

    # Reinforce: increase decay score based on utility
    recovery = request.utility_score * (0.15 if request.accessor_type == "user" else 0.05)
    current_decay = float(existing.get("decay_score", 0.5))
    new_decay = min(1.0, current_decay + recovery)
    access_count = int(existing.get("access_count", 0)) + 1

    record = MemoryRecord(
        **{
            **existing,
            "decay_score": new_decay,
            "access_count": access_count,
            "accessed_at": datetime.now(UTC).isoformat(),
            "last_access_utility": request.utility_score,
        }
    )
    await search.upsert(record)
    logger.info(
        "memory.feedback",
        memory_id=memory_id,
        utility=request.utility_score,
        new_decay=new_decay,
    )


@router.post("/{memory_id}/curate", status_code=204)
async def curate_memory(
    memory_id: str,
    request: CurateRequest,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> None:
    """Manual curation action on a memory."""
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

    existing = results[0]

    if request.action == "pin":
        existing["importance_score"] = 1.0
        existing["expires_at"] = None
    elif request.action == "archive":
        existing["is_archived"] = True
        existing["archived_at"] = datetime.now(UTC).isoformat()
        existing["archive_reason"] = request.reason
    elif request.action == "update_importance" and request.importance_score is not None:
        existing["importance_score"] = request.importance_score

    record = MemoryRecord(**existing)
    await search.upsert(record)
    logger.info("memory.curated", memory_id=memory_id, action=request.action)


@router.post("/{memory_id}/evidence")
async def submit_evidence(
    memory_id: str,
    request: EvidenceRequest,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> dict[str, object]:
    """Submit evidence to update a memory's confidence score (Bayesian update)."""
    from dse.workflows.activities.confidence import compute_confidence_update

    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

    existing = results[0]
    prior = float(existing.get("confidence", 0.5))

    evidence = Evidence(
        type=request.evidence_type,
        source_independent=request.source_independent,
        forced_value=request.forced_value,
        description=request.description,
    )
    posterior = compute_confidence_update(prior, evidence)

    patch = {
        **existing,
        "confidence": posterior,
        "confidence_updated_at": datetime.now(UTC).isoformat(),
    }
    if request.evidence_type.value == "corroborating_source":
        patch["corroborating_sources"] = int(existing.get("corroborating_sources", 0)) + 1
    elif request.evidence_type.value == "contradicting_source":
        patch["contradicting_sources"] = int(existing.get("contradicting_sources", 0)) + 1

    record = MemoryRecord(**patch)
    await search.upsert(record)

    logger.info(
        "memory.evidence_submitted",
        memory_id=memory_id,
        prior=round(prior, 3),
        posterior=round(posterior, 3),
        evidence_type=request.evidence_type,
    )
    return {"memory_id": memory_id, "prior": prior, "posterior": posterior}


def _to_response(record: MemoryRecord) -> MemoryResponse:
    return MemoryResponse(
        id=record.id,
        namespace=record.namespace,
        summary=record.summary,
        content_text=record.content_text,
        content_path=record.content_path,
        memory_type=record.memory_type,
        memory_subtype=record.memory_subtype,
        content_type=record.content_type,
        confidence=record.confidence,
        source_type=record.source_type,
        source_id=record.source_id,
        verification_status=record.verification_status.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
        decay_score=record.decay_score,
        importance_score=record.importance_score,
        tags=record.tags,
        entities=record.entities,
        language=record.language,
        is_archived=record.is_archived,
        superseded_by=record.superseded_by,
        trigger_type=record.trigger_type,
        trigger_at=record.trigger_at,
        is_triggered=record.is_triggered,
    )
