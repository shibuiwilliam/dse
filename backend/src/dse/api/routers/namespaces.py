from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from dse.api.deps import get_graph_service, get_search_service, get_storage_service
from dse.services.graph import GraphService
from dse.services.search import SearchService
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/namespaces", tags=["namespaces"])


@router.get("")
async def list_namespaces(
    search: Annotated[SearchService, Depends(get_search_service)],
) -> list[str]:
    """Return all distinct namespace values from the search index."""
    return await search.list_namespaces()


@router.get("/{namespace}")
async def get_namespace(
    namespace: str,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> dict[str, Any]:
    """Return stats for a single namespace."""
    namespaces = await search.list_namespaces()
    if namespace not in namespaces:
        raise HTTPException(status_code=404, detail=f"Namespace not found: {namespace}")
    return await search.get_namespace_stats(namespace)


@router.post("", status_code=201)
async def create_namespace(
    namespace: str,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> dict[str, str]:
    """Register a new namespace by creating a placeholder document."""
    existing = await search.list_namespaces()
    if namespace in existing:
        raise HTTPException(status_code=409, detail=f"Namespace already exists: {namespace}")

    from dse.core.models import MemoryRecord

    placeholder = MemoryRecord(
        namespace=namespace,
        summary="__namespace_placeholder__",
        content_text="",
        is_archived=True,
    )
    await search.upsert(placeholder)
    logger.info("namespace.created", namespace=namespace)
    return {"namespace": namespace, "status": "created"}


@router.delete("/{namespace}", status_code=200)
async def delete_namespace(
    namespace: str,
    search: Annotated[SearchService, Depends(get_search_service)],
    graph: Annotated[GraphService, Depends(get_graph_service)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> dict[str, Any]:
    """Delete a namespace and ALL its data from every store.

    Cleans up:
      - Elasticsearch: all memory documents
      - Neo4j: all memory nodes and edges
      - Object Storage (MinIO/GCS): all content files
      - Temporal: all schedules for this namespace
    """
    namespaces = await search.list_namespaces()
    if namespace not in namespaces:
        raise HTTPException(status_code=404, detail=f"Namespace not found: {namespace}")

    result: dict[str, Any] = {"namespace": namespace, "status": "deleted"}

    # 1. Elasticsearch
    search_deleted = await search.delete_by_namespace(namespace)
    result["search_deleted"] = search_deleted

    # 2. Neo4j
    graph_deleted = await graph.delete_by_namespace(namespace)
    result["graph_deleted"] = graph_deleted

    # 3. Object Storage
    try:
        await storage.delete_namespace(namespace)
        result["storage_deleted"] = True
    except Exception as e:
        logger.warning("namespace.storage_cleanup_failed", namespace=namespace, error=str(e))
        result["storage_deleted"] = False

    # 4. Temporal schedules
    try:
        temporal_deleted = await _cleanup_temporal_schedules(namespace)
        result["temporal_schedules_deleted"] = temporal_deleted
    except Exception as e:
        logger.warning("namespace.temporal_cleanup_failed", namespace=namespace, error=str(e))
        result["temporal_schedules_deleted"] = 0

    logger.info("namespace.deleted", **result)
    return result


async def _cleanup_temporal_schedules(namespace: str) -> int:
    """Delete all Temporal schedules associated with a namespace."""
    from dse.config import settings

    try:
        from temporalio.client import Client

        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
    except Exception:
        return 0

    deleted = 0
    schedule_prefixes = [
        "prospective-scan-",
        "semantic-compression-",
        "relation-discovery-",
        "temporal-edges-",
    ]

    for prefix in schedule_prefixes:
        schedule_id = f"{prefix}{namespace}"
        try:
            handle = client.get_schedule_handle(schedule_id)
            await handle.delete()
            deleted += 1
            logger.info("namespace.schedule_deleted", schedule_id=schedule_id)
        except Exception:
            pass  # Schedule doesn't exist, that's fine

    return deleted
