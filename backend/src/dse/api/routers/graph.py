from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query

from dse.api.deps import get_graph_service, get_search_service
from dse.config import settings
from dse.core.enums import RelationType
from dse.services.graph import GraphService
from dse.services.search import SearchService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/graph", tags=["graph"])


@router.get("/subgraph")
async def get_subgraph(
    namespace: str = Query(...),
    limit: int = Query(default=100, ge=1, le=500),
    graph: Annotated[GraphService, Depends(get_graph_service)] = ...,  # noqa: B008
) -> dict[str, Any]:
    """Get the full subgraph for a namespace (React Flow visualization)."""
    return await graph.get_subgraph_for_visualization(namespace, limit_nodes=limit)


@router.get("/neighbors/{memory_id}")
async def get_neighbors(
    memory_id: str,
    depth: int = Query(
        default=settings.graph_default_hop_depth,
        ge=1,
        le=settings.graph_max_hop_depth,
    ),
    limit: int = Query(default=10, ge=1, le=50),
    graph: Annotated[GraphService, Depends(get_graph_service)] = ...,  # noqa: B008
) -> list[dict[str, Any]]:
    """Get neighboring memories via graph traversal."""
    return await graph.get_neighbors(memory_id, hop_depth=depth, limit=limit)


@router.get("/by-relation")
async def find_by_relation(
    namespace: str = Query(...),
    relation_type: str = Query(..., description="Edge type, e.g. COMPLEMENTS"),
    limit: int = Query(default=50, ge=1, le=200),
    graph: Annotated[GraphService, Depends(get_graph_service)] = ...,  # noqa: B008
    search: Annotated[SearchService, Depends(get_search_service)] = ...,  # noqa: B008
) -> dict[str, Any]:
    """Find memories that have at least one edge of the given relation type.

    Returns graph node metadata enriched with summary from Elasticsearch.
    """
    try:
        rel = RelationType(relation_type)
    except ValueError:
        valid = [r.value for r in RelationType]
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"Invalid relation_type '{relation_type}'. Must be one of: {valid}",
        )

    nodes = await graph.find_memories_by_relation_type(namespace, rel, limit=limit)

    # Enrich with summary from ES
    for node in nodes:
        doc = await search.get_by_id(node["id"])
        if doc:
            node["summary"] = doc.get("summary", "")
            node["content_text"] = doc.get("content_text", "")[:200]
            node["importance_score"] = doc.get("importance_score", node.get("importance", 0.5))
            node["decay_score"] = doc.get("decay_score", 1.0)

    return {"relation_type": relation_type, "namespace": namespace, "memories": nodes}


@router.get("/lineage/{memory_id}")
async def get_lineage(
    memory_id: str,
    graph: Annotated[GraphService, Depends(get_graph_service)] = ...,  # noqa: B008
) -> dict[str, Any]:
    """Get the DERIVES lineage chain for a memory."""
    lineage = await graph.get_lineage(memory_id)
    return {"memory_id": memory_id, "lineage": lineage}
