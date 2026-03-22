from __future__ import annotations

from typing import Any

import structlog
from temporalio import activity

from dse.agents.mma.tools import compress_memories_tool
from dse.api.deps import get_search_service

logger = structlog.get_logger(__name__)


@activity.defn
async def find_compression_candidates(namespace: str) -> list[list[str]]:
    """Find clusters of episodic memories suitable for semantic compression.

    Returns groups of memory IDs that could be compressed together.
    Simplified version — full implementation would use HDBSCAN on embeddings.
    """
    search = get_search_service()

    # Get episodic memories from the last 30 days
    results = await search.search(
        "",
        namespace=namespace,
        memory_types=["episodic"],
        top_k=500,
        filter_archived=False,
    )

    if len(results) < 5:
        return []

    # Simplified clustering: group by tags
    tag_groups: dict[str, list[str]] = {}
    for r in results:
        tags = r.get("tags", [])
        confidence = float(r.get("confidence", 0.0))
        if confidence < 0.7:
            continue
        for tag in tags:
            if tag not in tag_groups:
                tag_groups[tag] = []
            tag_groups[tag].append(r.get("id", ""))

    # Return groups with >= 5 members
    candidates = [ids for ids in tag_groups.values() if len(ids) >= 5]
    logger.info(
        "compress.candidates_found",
        namespace=namespace,
        groups=len(candidates),
    )
    return candidates


@activity.defn
async def compress_memory_cluster(
    namespace: str,
    memory_ids: list[str],
) -> dict[str, Any]:
    """Compress a cluster of episodic memories into a semantic memory."""
    result = await compress_memories_tool(
        namespace=namespace,
        memory_ids=memory_ids,
    )
    return result
