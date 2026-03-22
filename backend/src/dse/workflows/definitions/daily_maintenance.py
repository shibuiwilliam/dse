from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY_POLICY = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=1),
)


@workflow.defn
class DailyMaintenanceWorkflow:
    """Daily maintenance workflow for memory decay and archiving.

    Runs at 02:00 UTC daily:
      1. Update decay scores for all active memories
      2. Archive memories below threshold
    """

    @workflow.run
    async def run(self, namespace: str) -> dict[str, Any]:
        # Step 1: Update decay scores
        decay_result = await workflow.execute_activity(
            "update_decay_scores",
            namespace,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RETRY_POLICY,
        )

        # Step 2: Archive decayed memories
        archived = await workflow.execute_activity(
            "archive_decayed_memories",
            namespace,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY_POLICY,
        )

        return {
            "decay_result": decay_result,
            "archived_count": archived,
        }


@workflow.defn
class SemanticCompressionWorkflow:
    """Weekly workflow for compressing episodic memories into semantic memories.

    Runs at 03:00 UTC on Sundays.
    """

    @workflow.run
    async def run(self, namespace: str) -> dict[str, Any]:
        # Find compression candidates
        candidates = await workflow.execute_activity(
            "find_compression_candidates",
            namespace,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY_POLICY,
        )

        results: list[dict[str, Any]] = []
        for cluster_ids in candidates:
            result = await workflow.execute_activity(
                "compress_memory_cluster",
                [namespace, cluster_ids],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_POLICY,
            )
            results.append(result)

        return {
            "clusters_processed": len(results),
            "results": results,
        }


@workflow.defn
class RelationDiscoveryWorkflow:
    """Daily workflow for discovering latent relationships between memories."""

    @workflow.run
    async def run(self, namespace: str) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "discover_relations",
            namespace,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RETRY_POLICY,
        )
        return result  # type: ignore[return-value]
