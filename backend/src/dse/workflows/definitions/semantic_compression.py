from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))
LONG_TIMEOUT = timedelta(minutes=30)
SHORT_TIMEOUT = timedelta(seconds=60)


@workflow.defn
class P3SemanticCompressionWorkflow:
    """Weekly episodic→semantic distillation workflow.

    Idempotent: running twice on the same namespace won't create duplicate semantics.
    Design ref: PROJECT.md Section 5.3
    """

    @workflow.run
    async def run(self, namespace: str, lookback_days: int = 30) -> dict[str, Any]:
        workflow.logger.info(
            "compression.started", extra={"namespace": namespace, "lookback_days": lookback_days}
        )

        clusters: list[dict[str, Any]] = await workflow.execute_activity(
            "cluster_episodes_activity",
            args=[namespace, lookback_days],
            start_to_close_timeout=LONG_TIMEOUT,
            retry_policy=RETRY,
        )

        if not clusters:
            return {"status": "no_clusters", "namespace": namespace}

        results: list[dict[str, Any]] = []
        for cluster in clusters:
            result: dict[str, Any] = await workflow.execute_activity(
                "distill_cluster_activity",
                args=[namespace, cluster],
                start_to_close_timeout=SHORT_TIMEOUT,
                retry_policy=RETRY,
            )
            results.append(result)

        success = [r for r in results if not r.get("skipped_reason")]
        return {
            "status": "completed",
            "namespace": namespace,
            "total_clusters": len(clusters),
            "distilled": len(success),
            "skipped": len(results) - len(success),
        }
