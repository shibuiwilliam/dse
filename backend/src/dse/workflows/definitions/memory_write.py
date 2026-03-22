from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
)


@workflow.defn
class MemoryWriteWorkflow:
    """Saga-pattern workflow for writing a new memory record.

    Phases 1-4: persist content, generate embedding, index, register graph node.
    Phase 5: trigger contradiction check as child workflow.
    Phase 6: record provenance.
    """

    @workflow.run
    async def run(self, record_dict: dict[str, Any]) -> str:
        timeout_30s = timedelta(seconds=30)
        timeout_60s = timedelta(seconds=60)

        # Phase 1: Object Storage (source of truth)
        content_path = await workflow.execute_activity(
            "store_to_object_storage",
            record_dict,
            start_to_close_timeout=timeout_30s,
            retry_policy=RETRY_POLICY,
        )
        record_dict["content_path"] = content_path

        # Phase 2: Embedding generation
        embedding = await workflow.execute_activity(
            "generate_embedding",
            record_dict,
            start_to_close_timeout=timeout_60s,
            retry_policy=RETRY_POLICY,
        )
        record_dict["embedding"] = embedding

        # Phase 3: Search Index upsert
        await workflow.execute_activity(
            "upsert_search_index",
            record_dict,
            start_to_close_timeout=timeout_30s,
            retry_policy=RETRY_POLICY,
        )

        # Phase 4: Graph DB registration
        await workflow.execute_activity(
            "register_graph_node",
            record_dict,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RETRY_POLICY,
        )

        # Phase 5: Provenance initialization
        await workflow.execute_activity(
            "initialize_provenance",
            args=[record_dict.get("id", ""), record_dict.get("namespace", "")],
            start_to_close_timeout=timeout_30s,
            retry_policy=RETRY_POLICY,
        )

        # Phase 6: Contradiction check (child workflow — non-blocking)
        memory_id = str(record_dict.get("id", ""))
        namespace = str(record_dict.get("namespace", ""))
        await workflow.execute_child_workflow(
            "ContradictionCheckWorkflow",
            args=[memory_id, namespace],
            id=f"contradiction-check-{memory_id}",
            task_queue=workflow.info().task_queue,
        )

        return memory_id
