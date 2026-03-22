from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dse.api.deps import get_cache_service
from dse.services.cache import WorkingMemoryService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/sessions", tags=["working_memory"])


class ContextBody(BaseModel):
    context: dict[str, Any]


class TurnBody(BaseModel):
    turn: dict[str, Any]


@router.get("/{session_id}/context")
async def get_session_context(
    session_id: str,
    wm: Annotated[WorkingMemoryService, Depends(get_cache_service)],
) -> dict[str, Any]:
    """Get the current working memory context for a session."""
    ctx = await wm.get_context(session_id)
    return {"session_id": session_id, "context": ctx}


@router.put("/{session_id}/context")
async def set_session_context(
    session_id: str,
    body: ContextBody,
    wm: Annotated[WorkingMemoryService, Depends(get_cache_service)],
) -> dict[str, str]:
    """Update the working memory context for a session."""
    await wm.set_context(session_id, body.context)
    return {"status": "ok"}


@router.get("/{session_id}/turns")
async def get_session_turns(
    session_id: str,
    wm: Annotated[WorkingMemoryService, Depends(get_cache_service)],
    count: int = 20,
) -> dict[str, Any]:
    """Get recent conversation turns for a session."""
    turns = await wm.get_recent_turns(session_id, count=count)
    return {"session_id": session_id, "turns": turns}


@router.post("/{session_id}/turns")
async def append_session_turn(
    session_id: str,
    body: TurnBody,
    wm: Annotated[WorkingMemoryService, Depends(get_cache_service)],
) -> dict[str, str]:
    """Append a conversation turn to the session's stream."""
    entry_id = await wm.append_turn(session_id, body.turn)
    return {"entry_id": entry_id}


@router.post("/{session_id}/persist")
async def persist_session(
    session_id: str,
    wm: Annotated[WorkingMemoryService, Depends(get_cache_service)],
) -> dict[str, Any]:
    """Snapshot the session for MMA to decide what to persist to DSE."""
    snapshot = await wm.snapshot_for_persistence(session_id)
    return snapshot


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    wm: Annotated[WorkingMemoryService, Depends(get_cache_service)],
) -> None:
    """End a session and clean up working memory."""
    await wm.delete_session(session_id)
    logger.info("session.deleted", session_id=session_id)
