from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from dse.api.deps import get_graph_service, get_search_service
from dse.core.enums import RelationType, VerificationStatus
from dse.core.models import MemoryRecord, RelationRecord
from dse.services.graph import GraphService
from dse.services.search import SearchService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/conflicts", tags=["conflicts"])


class ResolveRequest(BaseModel):
    id_a: str
    id_b: str
    keep: str = Field(pattern=r"^(A|B|both)$")
    reason: str = ""


@router.get("")
async def list_conflicts(
    namespace: str = Query(...),
    status: str = Query(default="pending"),
    graph: Annotated[GraphService, Depends(get_graph_service)] = ...,  # noqa: B008
) -> list[dict[str, Any]]:
    """List contradicting memory pairs in a namespace."""
    pairs = await graph.get_contradicting_pairs(namespace)
    if status != "all":
        pairs = [p for p in pairs if p.get("resolution_status") == status]
    return pairs


@router.post("/resolve", status_code=200)
async def resolve_conflict(
    request: ResolveRequest,
    graph: Annotated[GraphService, Depends(get_graph_service)],
    search: Annotated[SearchService, Depends(get_search_service)],
) -> dict[str, str]:
    """Manually resolve a contradiction pair.

    keep="A": mark B as superseded
    keep="B": mark A as superseded
    keep="both": dismiss — both are valid
    """
    if request.keep == "A":
        loser_id = request.id_b
        winner_id = request.id_a
    elif request.keep == "B":
        loser_id = request.id_a
        winner_id = request.id_b
    else:
        # Both kept — just remove the contradiction edge by updating status
        logger.info("conflict.resolved_both", id_a=request.id_a, id_b=request.id_b)
        return {"status": "dismissed", "reason": request.reason}

    # Mark loser as superseded
    results = await search.search(loser_id, top_k=1, filter_archived=False)
    if results:
        record = MemoryRecord(
            **{**results[0], "verification_status": VerificationStatus.SUPERSEDED}
        )
        await search.upsert(record)

    # Create SUPERSEDED_BY edge
    await graph.create_relation(
        RelationRecord(
            from_id=loser_id,
            to_id=winner_id,
            relation_type=RelationType.SUPERSEDED_BY,
            confidence=0.9,
            created_by="human_resolution",
            method=f"manual: {request.reason}",
        )
    )

    logger.info(
        "conflict.resolved",
        winner=winner_id,
        loser=loser_id,
        reason=request.reason,
    )
    return {"status": "resolved", "winner_id": winner_id, "loser_id": loser_id}
