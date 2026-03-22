from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))
TIMEOUT = timedelta(seconds=60)


@workflow.defn
class ContradictionCheckWorkflow:
    """Check a newly written memory against existing memories for contradictions.

    Called as a child workflow from MemoryWriteWorkflow.
    Design ref: PROJECT.md Section 4.3
    """

    @workflow.run
    async def run(self, memory_id: str, namespace: str) -> dict[str, Any]:
        candidates: list[str] = await workflow.execute_activity(
            "search_contradiction_candidates",
            args=[memory_id, namespace],
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

        if not candidates:
            return {"status": "no_candidates", "memory_id": memory_id}

        results: list[dict[str, Any]] = []
        for candidate_id in candidates:
            judgment: dict[str, Any] = await workflow.execute_activity(
                "llm_judge_contradiction",
                args=[memory_id, candidate_id],
                start_to_close_timeout=TIMEOUT,
                retry_policy=RETRY,
            )

            relation = judgment.get("relation", "UNRELATED")

            if relation == "CONTRADICTS":
                if judgment.get("auto_resolvable", False):
                    await workflow.execute_activity(
                        "auto_resolve_contradiction",
                        args=[memory_id, candidate_id, judgment],
                        start_to_close_timeout=TIMEOUT,
                        retry_policy=RETRY,
                    )
                    results.append({"type": "auto_resolved", "candidate_id": candidate_id})
                else:
                    await workflow.execute_activity(
                        "enqueue_manual_resolution",
                        args=[memory_id, candidate_id, judgment],
                        start_to_close_timeout=TIMEOUT,
                        retry_policy=RETRY,
                    )
                    results.append({"type": "manual_required", "candidate_id": candidate_id})

            elif relation == "COMPLEMENTS":
                await workflow.execute_activity(
                    "create_graph_relation",
                    args=[memory_id, candidate_id, "COMPLEMENTS", judgment.get("confidence", 0.5)],
                    start_to_close_timeout=TIMEOUT,
                    retry_policy=RETRY,
                )
                results.append({"type": "complemented", "candidate_id": candidate_id})

            elif relation in ("SUPERSEDES", "DUPLICATE"):
                await workflow.execute_activity(
                    "create_supersedes_relation",
                    args=[memory_id, candidate_id],
                    start_to_close_timeout=TIMEOUT,
                    retry_policy=RETRY,
                )
                results.append({"type": "superseded", "candidate_id": candidate_id})

        return {"status": "completed", "memory_id": memory_id, "results": results}
