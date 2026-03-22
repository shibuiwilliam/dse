from __future__ import annotations

from typing import Any

import structlog
from temporalio import activity

from dse.api.deps import (
    get_embedding_service,
    get_graph_service,
    get_search_service,
    get_storage_service,
)
from dse.core.models import MemoryRecord

logger = structlog.get_logger(__name__)


@activity.defn
async def store_to_object_storage(record_dict: dict[str, Any]) -> str:
    """Phase 1: Persist content to Object Storage (source of truth)."""
    storage = get_storage_service()
    record = MemoryRecord(**record_dict)
    content_path = await storage.store_content(
        record.namespace,
        record.id,
        record.content_text,
    )
    logger.info("activity.stored_content", memory_id=record.id, path=content_path)
    return content_path


@activity.defn
async def generate_embedding(record_dict: dict[str, Any]) -> list[float]:
    """Phase 2: Generate embedding vector for the memory content."""
    embedding = get_embedding_service()
    record = MemoryRecord(**record_dict)
    embed_text = record.summary or record.content_text[:1000]
    vector = await embedding.encode(embed_text)
    logger.info("activity.embedding_generated", memory_id=record.id, dims=len(vector))
    return vector


@activity.defn
async def upsert_search_index(record_dict: dict[str, Any]) -> str:
    """Phase 3: Upsert record to the Search Index."""
    search = get_search_service()
    record = MemoryRecord(**record_dict)
    result = await search.upsert(record)
    logger.info("activity.index_upserted", memory_id=record.id)
    return result


@activity.defn
async def register_graph_node(record_dict: dict[str, Any]) -> None:
    """Phase 4: Register node and detect relations in Graph DB."""
    graph = get_graph_service()
    record = MemoryRecord(**record_dict)
    await graph.register_node(record)
    logger.info("activity.graph_registered", memory_id=record.id)
