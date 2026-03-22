from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends

from dse.api.deps import get_retrieval_pipeline
from dse.api.schemas import ContextItemResponse, RetrieveRequest, RetrieveResponse
from dse.pipeline.retrieval import CascadeRetrieval

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/memories", tags=["retrieve"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_memories(
    request: RetrieveRequest,
    pipeline: Annotated[CascadeRetrieval, Depends(get_retrieval_pipeline)],
) -> RetrieveResponse:
    """Retrieve memory context for an agent using Cascade Retrieval.

    The main search API. Accepts a natural language query and returns
    assembled context within the specified token budget.
    """
    context = await pipeline.retrieve(
        query=request.query,
        namespace=request.namespace,
        memory_types=[mt.value for mt in request.memory_types] if request.memory_types else None,
        token_budget=request.token_budget,
        cascade_stage=request.cascade_stage,
        task_context=request.task_context,
    )

    items = [
        ContextItemResponse(
            memory_id=item.memory_id,
            memory_type=item.memory_type,
            content=item.content,
            tier=item.tier,
            score=item.score,
            confidence=item.confidence,
            created_at=item.created_at,
            tokens=item.tokens,
        )
        for item in context.items
    ]

    logger.info(
        "retrieve.complete",
        query=request.query[:50],
        results=len(items),
        tokens=context.total_tokens,
    )

    return RetrieveResponse(
        items=items,
        total_tokens=context.total_tokens,
        query=context.query,
        namespace=context.namespace,
    )
