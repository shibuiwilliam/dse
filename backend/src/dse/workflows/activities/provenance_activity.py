from __future__ import annotations

import structlog
from temporalio import activity

from dse.core.models import ProvenanceEntry

logger = structlog.get_logger(__name__)


@activity.defn
async def initialize_provenance(memory_id: str, namespace: str) -> None:
    """Initialize provenance record when a memory is first created."""
    from dse.api.deps import get_storage_service
    from dse.infrastructure.provenance import ProvenanceService

    storage = get_storage_service()
    prov = ProvenanceService(storage)
    entry = ProvenanceEntry(
        step="creation",
        performed_by="system",
        description=f"Memory {memory_id} created",
    )
    await prov.initialize(memory_id, namespace, created_by=entry)
    logger.info("provenance.activity.initialized", memory_id=memory_id)
