from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))


@workflow.defn
class P3RelationDiscoveryWorkflow:
    """Daily workflow: discover latent relations between memories.

    Design ref: PROJECT.md Section 9.1
    """

    @workflow.run
    async def run(self, namespace: str) -> dict[str, Any]:
        result: dict[str, Any] = await workflow.execute_activity(
            "discover_relations_activity",
            args=[namespace],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RETRY,
        )
        return result


@workflow.defn
class TemporalEdgeBuildWorkflow:
    """Daily workflow: build TEMPORALLY_PRECEDES edges via Allen's Interval Algebra.

    Design ref: PROJECT.md Section 6.3
    """

    @workflow.run
    async def run(self, namespace: str) -> dict[str, Any]:
        result: dict[str, Any] = await workflow.execute_activity(
            "build_temporal_edges_activity",
            args=[namespace],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RETRY,
        )
        return result
