from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dse.api.deps import get_storage_service
from dse.infrastructure.provenance import ProvenanceService
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/memories", tags=["provenance"])


class AccessLogRequest(BaseModel):
    accessed_by: str
    task_id: str | None = None
    utility_score: float | None = None


def _get_provenance_service(
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> ProvenanceService:
    return ProvenanceService(storage)


@router.get("/{memory_id}/provenance")
async def get_provenance(
    memory_id: str,
    namespace: str,
    prov: Annotated[ProvenanceService, Depends(_get_provenance_service)],
) -> dict[str, Any]:
    """Get the full provenance chain for a memory."""
    result = await prov.get(memory_id, namespace)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Provenance not found for {memory_id}")
    return result.model_dump(mode="json")


@router.post("/{memory_id}/provenance/access", status_code=204)
async def record_provenance_access(
    memory_id: str,
    namespace: str,
    body: AccessLogRequest,
    prov: Annotated[ProvenanceService, Depends(_get_provenance_service)],
) -> None:
    """Record a memory access event in the provenance log."""
    await prov.record_access(
        memory_id,
        namespace,
        accessed_by=body.accessed_by,
        task_id=body.task_id,
        utility_score=body.utility_score,
    )
