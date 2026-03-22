from __future__ import annotations

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from dse.config import settings

# Phase 1 activities
from dse.workflows.activities.compress import compress_memory_cluster, find_compression_candidates

# Phase 2 activities
from dse.workflows.activities.confidence import update_confidence_activity
from dse.workflows.activities.contradiction import (
    auto_resolve_contradiction,
    create_graph_relation,
    create_supersedes_relation,
    enqueue_manual_resolution,
    llm_judge_contradiction,
    search_contradiction_candidates,
)
from dse.workflows.activities.decay import archive_decayed_memories, update_decay_scores
from dse.workflows.activities.discover import discover_relations
from dse.workflows.activities.indexing import (
    generate_embedding,
    register_graph_node,
    store_to_object_storage,
    upsert_search_index,
)

# Phase 3 activities
from dse.workflows.activities.p3_compression import (
    cluster_episodes_activity,
    distill_cluster_activity,
)
from dse.workflows.activities.p3_discovery import discover_relations_activity
from dse.workflows.activities.p3_importance import (
    estimate_importance_activity,
    reinforce_memory_activity,
)
from dse.workflows.activities.p3_prospective import (
    publish_prospective_fired_events_activity,
    scan_and_fire_prospective_activity,
)
from dse.workflows.activities.p3_temporal import build_temporal_edges_activity
from dse.workflows.activities.provenance_activity import initialize_provenance

# Workflows
from dse.workflows.definitions.contradiction_check import ContradictionCheckWorkflow
from dse.workflows.definitions.daily_maintenance import (
    DailyMaintenanceWorkflow,
    RelationDiscoveryWorkflow,
    SemanticCompressionWorkflow,
)
from dse.workflows.definitions.memory_write import MemoryWriteWorkflow
from dse.workflows.definitions.p3_relation_discovery import (
    P3RelationDiscoveryWorkflow,
    TemporalEdgeBuildWorkflow,
)
from dse.workflows.definitions.prospective_scan import ProspectiveScanWorkflow
from dse.workflows.definitions.semantic_compression import P3SemanticCompressionWorkflow

logger = structlog.get_logger(__name__)

ALL_ACTIVITIES = [
    # Phase 1
    store_to_object_storage,
    generate_embedding,
    upsert_search_index,
    register_graph_node,
    update_decay_scores,
    archive_decayed_memories,
    find_compression_candidates,
    compress_memory_cluster,
    discover_relations,
    # Phase 2
    search_contradiction_candidates,
    llm_judge_contradiction,
    auto_resolve_contradiction,
    enqueue_manual_resolution,
    create_graph_relation,
    create_supersedes_relation,
    update_confidence_activity,
    initialize_provenance,
    # Phase 3
    cluster_episodes_activity,
    distill_cluster_activity,
    scan_and_fire_prospective_activity,
    publish_prospective_fired_events_activity,
    discover_relations_activity,
    build_temporal_edges_activity,
    estimate_importance_activity,
    reinforce_memory_activity,
]

ALL_WORKFLOWS = [
    MemoryWriteWorkflow,
    ContradictionCheckWorkflow,
    DailyMaintenanceWorkflow,
    SemanticCompressionWorkflow,
    RelationDiscoveryWorkflow,
    # Phase 3
    P3SemanticCompressionWorkflow,
    ProspectiveScanWorkflow,
    P3RelationDiscoveryWorkflow,
    TemporalEdgeBuildWorkflow,
]


TASK_QUEUES = ["dse-main", "dse-maintenance", "dse-discovery"]


async def run_worker() -> None:
    """Start Temporal workers on all task queues (main, maintenance, discovery)."""
    logger.info(
        "worker.starting",
        host=settings.temporal_host,
        namespace=settings.temporal_namespace,
        task_queues=TASK_QUEUES,
    )

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    workers = [
        Worker(
            client,
            task_queue=queue,
            workflows=ALL_WORKFLOWS,
            activities=ALL_ACTIVITIES,
        )
        for queue in TASK_QUEUES
    ]

    logger.info("worker.running", task_queues=TASK_QUEUES)

    # Run all workers concurrently — stops when any one fails or is cancelled
    async with asyncio.TaskGroup() as tg:
        for w in workers:
            tg.create_task(w.run())


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
