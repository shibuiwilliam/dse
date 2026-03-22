from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog

from dse.core.models import AccessLogEntry, MemoryProvenance, ProvenanceEntry
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)

PROVENANCE_PATH_TEMPLATE = "provenance/{namespace}/{memory_id}.json"


class ProvenanceService:
    """Manages memory provenance records in Object Storage.

    Provenance is stored separately from the search index to avoid
    unnecessary index bloat on every access log update.
    Design ref: PROJECT.md Section 6.5
    """

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def _path(self, namespace: str, memory_id: str) -> str:
        return PROVENANCE_PATH_TEMPLATE.format(namespace=namespace, memory_id=memory_id)

    async def initialize(
        self,
        memory_id: str,
        namespace: str,
        created_by: ProvenanceEntry,
    ) -> None:
        """Create the provenance record when a memory is first stored."""
        provenance = MemoryProvenance(memory_id=memory_id, created_by=created_by)
        await self._write(namespace, memory_id, provenance)
        logger.info("provenance.initialized", memory_id=memory_id)

    async def record_transformation(
        self,
        memory_id: str,
        namespace: str,
        entry: ProvenanceEntry,
    ) -> None:
        """Record a transformation step (summarization, inference, etc.)."""
        provenance = await self.get(memory_id, namespace)
        if provenance is None:
            logger.warning("provenance.not_found_on_transform", memory_id=memory_id)
            return
        provenance.transformations.append(entry)
        await self._write(namespace, memory_id, provenance)

    async def record_access(
        self,
        memory_id: str,
        namespace: str,
        accessed_by: str,
        task_id: str | None = None,
        utility_score: float | None = None,
    ) -> None:
        """Record a memory access event."""
        provenance = await self.get(memory_id, namespace)
        if provenance is None:
            return
        entry = AccessLogEntry(
            accessed_by=accessed_by,
            accessed_at=datetime.now(UTC).isoformat(),
            task_id=task_id,
            utility_score=utility_score,
        )
        provenance.access_log.append(entry)
        if len(provenance.access_log) > 500:
            provenance.access_log = provenance.access_log[-500:]
        await self._write(namespace, memory_id, provenance)

    async def get(self, memory_id: str, namespace: str) -> MemoryProvenance | None:
        """Retrieve the full provenance for a memory."""
        return await self._read(namespace, memory_id)

    async def _read(self, namespace: str, memory_id: str) -> MemoryProvenance | None:
        try:
            bucket = getattr(self._storage, "_bucket_name", "mock-bucket")
            path = f"gs://{bucket}/memories/{namespace}/provenance_{memory_id}.json"
            raw = await self._storage.fetch_content(path)
            return MemoryProvenance(**json.loads(raw))
        except Exception:
            return None

    async def _write(
        self,
        namespace: str,
        memory_id: str,
        provenance: MemoryProvenance,
    ) -> None:
        await self._storage.store_content(
            namespace,
            f"provenance_{memory_id}",
            provenance.model_dump_json(indent=2),
            content_type="application/json",
            ext="json",
        )
