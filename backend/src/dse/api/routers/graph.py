from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query

from dse.api.deps import get_graph_service
from dse.config import settings
from dse.services.graph import GraphService

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


@router.get("/lineage/{memory_id}")
async def get_lineage(
    memory_id: str,
    graph: Annotated[GraphService, Depends(get_graph_service)] = ...,  # noqa: B008
) -> dict[str, Any]:
    """Get the DERIVES lineage chain for a memory."""
    lineage = await graph.get_lineage(memory_id)
    return {"memory_id": memory_id, "lineage": lineage}
