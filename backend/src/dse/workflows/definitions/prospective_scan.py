from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))


@workflow.defn
class ProspectiveScanWorkflow:
    """Runs every minute: check and fire prospective memories.

    Design ref: PROJECT.md Section 6.1
    """

    @workflow.run
    async def run(self, namespace: str) -> dict[str, Any]:
        fired: list[dict[str, Any]] = await workflow.execute_activity(
            "scan_and_fire_prospective_activity",
            args=[namespace],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY,
        )

        if fired:
            await workflow.execute_activity(
                "publish_prospective_fired_events_activity",
                args=[fired],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RETRY,
            )

        return {"fired_count": len(fired), "namespace": namespace}
