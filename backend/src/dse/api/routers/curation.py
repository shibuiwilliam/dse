from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dse.api.deps import get_graph_service, get_search_service
from dse.core.models import MemoryRecord
from dse.services.graph import GraphService
from dse.services.search import SearchService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/curation", tags=["curation"])


class PinRequest(BaseModel):
    pinned: bool = True


class ForgetResponse(BaseModel):
    deleted_ids: list[str]


class CompressRequest(BaseModel):
    namespace: str
    lookback_days: int = Field(default=30, ge=1, le=365)


class ProspectiveCreateRequest(BaseModel):
    namespace: str
    summary: str
    trigger_type: str  # "time" | "event" | "condition"
    trigger_at: str | None = None
    trigger_condition: str | None = None
    recurrence: str = "once"


# ── Memory browse & edit ─────────────────────────────────────────────


@router.get("/memories")
async def list_memories(
    namespace: str = Query(...),
    memory_type: str = Query(default="all"),
    min_importance: float = Query(default=0.0, ge=0.0, le=1.0),
    sort_by: str = Query(default="importance"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Annotated[SearchService, Depends(get_search_service)] = ...,  # noqa: B008
) -> dict[str, Any]:
    """List memories with filtering and pagination."""
    memory_types = [memory_type] if memory_type != "all" else None
    results = await search.search(
        "",
        namespace=namespace,
        memory_types=memory_types,
        top_k=page_size * page,
        filter_archived=True,
    )

    # Filter by min importance
    if min_importance > 0:
        results = [r for r in results if float(r.get("importance_score", 0)) >= min_importance]

    # Sort
    sort_key = (
        sort_by
        if sort_by in ("importance_score", "created_at", "decay_score")
        else "importance_score"
    )
    if sort_key == "created_at":
        results.sort(key=lambda r: str(r.get(sort_key, "")), reverse=True)
    else:
        results.sort(key=lambda r: float(r.get(sort_key, 0)), reverse=True)

    # Paginate
    start = (page - 1) * page_size
    page_results = results[start : start + page_size]

    return {
        "memories": page_results,
        "total": len(results),
        "page": page,
        "page_size": page_size,
    }


@router.post("/memories/{memory_id}/pin", status_code=200)
async def pin_memory(
    memory_id: str,
    body: PinRequest,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> dict[str, str]:
    """Pin a memory (importance=1.0, no expiry) or unpin."""
    results = await search.search(memory_id, top_k=1, filter_archived=False)
    if not results:
        raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")

    patch = dict(results[0])
    if body.pinned:
        patch["importance_score"] = 1.0
        patch["expires_at"] = None
    else:
        patch["importance_score"] = 0.5

    record = MemoryRecord(**patch)
    await search.upsert(record)
    logger.info("curation.pin", memory_id=memory_id, pinned=body.pinned)
    return {"status": "pinned" if body.pinned else "unpinned"}


@router.post("/memories/{memory_id}/forget")
async def forget_memory(
    memory_id: str,
    search: Annotated[SearchService, Depends(get_search_service)],
    graph: Annotated[GraphService, Depends(get_graph_service)],
) -> ForgetResponse:
    """Forget a memory and all its derived memories."""
    deleted: list[str] = []

    # Find derived memories
    try:
        lineage = await graph.get_lineage(memory_id)
        for entry in lineage:
            for lid in entry.get("lineage_ids", []):
                if lid != memory_id and lid not in deleted:
                    await search.delete(lid)
                    await graph.delete_node(lid)
                    deleted.append(lid)
    except Exception:
        logger.warning("curation.forget_lineage_partial", memory_id=memory_id)

    # Delete the main memory
    await search.delete(memory_id)
    await graph.delete_node(memory_id)
    deleted.append(memory_id)

    logger.info("curation.forget", memory_id=memory_id, deleted_count=len(deleted))
    return ForgetResponse(deleted_ids=deleted)


# ── Compression ──────────────────────────────────────────────────────


@router.post("/compress")
async def trigger_compression(
    body: CompressRequest,
) -> dict[str, str]:
    """Manually trigger Semantic Compression."""
    # In production, this would start a Temporal workflow
    logger.info("curation.compress_triggered", namespace=body.namespace, days=body.lookback_days)
    return {"status": "triggered", "namespace": body.namespace}


# ── Prospective Memory ───────────────────────────────────────────────


@router.get("/prospective")
async def list_prospective(
    namespace: str = Query(...),
    status: str = Query(default="pending"),
    search: Annotated[SearchService, Depends(get_search_service)] = ...,  # noqa: B008
) -> list[dict[str, Any]]:
    """List prospective memories."""
    results = await search.search(
        "",
        namespace=namespace,
        memory_types=["prospective"],
        top_k=100,
        filter_archived=True,
    )
    if status == "pending":
        results = [r for r in results if not r.get("is_triggered", False)]
    elif status == "triggered":
        results = [r for r in results if r.get("is_triggered", False)]
    return results


@router.post("/prospective", status_code=201)
async def create_prospective(
    body: ProspectiveCreateRequest,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> dict[str, str]:
    """Create a new prospective memory."""
    record = MemoryRecord(
        namespace=body.namespace,
        summary=body.summary,
        content_text=body.summary,
        memory_type="prospective",
        trigger_type=body.trigger_type,
        trigger_at=datetime.fromisoformat(body.trigger_at) if body.trigger_at else None,
        trigger_condition=body.trigger_condition,
        confidence=1.0,
        decay_score=1.0,
        importance_score=0.80,
    )
    await search.upsert(record)
    logger.info("curation.prospective_created", memory_id=record.id)
    return {"memory_id": record.id, "status": "created"}


@router.delete("/prospective/{memory_id}", status_code=204)
async def delete_prospective(
    memory_id: str,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> None:
    """Delete a prospective memory."""
    await search.delete(memory_id)


# ── Stats ────────────────────────────────────────────────────────────


@router.get("/stats")
async def get_curation_stats(
    namespace: str = Query(...),
    search: Annotated[SearchService, Depends(get_search_service)] = ...,  # noqa: B008
) -> dict[str, Any]:
    """Get memory statistics for a namespace using ES aggregations."""
    return await search.get_curation_stats(namespace)
