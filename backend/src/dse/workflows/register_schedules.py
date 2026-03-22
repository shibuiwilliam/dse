"""Register Temporal Schedules for DSE.

Connects to Temporal using the configured namespace (TEMPORAL_NAMESPACE),
fetches all DSE memory namespaces from Elasticsearch, and registers
recurring schedules for each one.

Run with: make register-schedules
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
)
from temporalio.common import RetryPolicy

from dse.config import settings


async def get_dse_namespaces() -> list[str]:
    """Fetch all DSE memory namespaces from the search index."""
    from dse.api.deps import get_search_service

    search = get_search_service()
    try:
        namespaces = await search.list_namespaces()
        if namespaces:
            return namespaces
    except Exception as e:
        print(f"[warn] Could not fetch namespaces from search index: {e}")  # noqa: T201

    # Fallback: return a default namespace so schedules are still registered
    return ["default"]


async def register_all(client: Client, namespaces: list[str], *, force: bool = False) -> None:
    """Register schedules for all namespaces.

    If force=True, deletes existing schedules first and re-creates them.
    """
    for namespace in namespaces:
        print(f"\n--- Namespace: {namespace} ---")  # noqa: T201

        await _upsert_schedule(
            client,
            schedule_id=f"prospective-scan-{namespace}",
            workflow="ProspectiveScanWorkflow",
            args=[namespace],
            task_queue="dse-main",
            interval=timedelta(minutes=1),
            force=force,
        )

        await _upsert_schedule(
            client,
            schedule_id=f"semantic-compression-{namespace}",
            workflow="P3SemanticCompressionWorkflow",
            args=[namespace, settings.compression_lookback_days],
            task_queue="dse-maintenance",
            interval=timedelta(weeks=1),
            force=force,
        )

        await _upsert_schedule(
            client,
            schedule_id=f"relation-discovery-{namespace}",
            workflow="P3RelationDiscoveryWorkflow",
            args=[namespace],
            task_queue="dse-discovery",
            interval=timedelta(days=1),
            force=force,
        )

        await _upsert_schedule(
            client,
            schedule_id=f"temporal-edges-{namespace}",
            workflow="TemporalEdgeBuildWorkflow",
            args=[namespace],
            task_queue="dse-discovery",
            interval=timedelta(days=1),
            force=force,
        )


async def _upsert_schedule(
    client: Client,
    schedule_id: str,
    workflow: str,
    args: list,  # noqa: ANN401
    task_queue: str,
    interval: timedelta,
    *,
    force: bool = False,
) -> None:
    # Check if exists
    exists = False
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.describe()
        exists = True
    except Exception:
        pass

    if exists and force:
        await client.get_schedule_handle(schedule_id).delete()
        print(f"  [deleted] {schedule_id}")  # noqa: T201
        exists = False

    if exists:
        print(f"  [skip] already exists: {schedule_id}")  # noqa: T201
        return

    await client.create_schedule(
        schedule_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                workflow,
                # Use keyword `args=` so Temporal spreads the list as
                # individual workflow parameters.
                args=args,
                id=f"{schedule_id}-run",
                task_queue=task_queue,
                retry_policy=RetryPolicy(maximum_attempts=3),
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=interval)]),
        ),
    )
    print(f"  [created] {schedule_id}")  # noqa: T201


async def main() -> None:
    import sys

    force = "--force" in sys.argv

    print(  # noqa: T201
        f"Connecting to Temporal at {settings.temporal_host} "
        f"(namespace: {settings.temporal_namespace})"
        f"{' [FORCE recreate]' if force else ''}"
    )
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    try:
        namespaces = await get_dse_namespaces()
        print(f"Found {len(namespaces)} namespace(s): {namespaces}")  # noqa: T201

        await register_all(client, namespaces, force=force)
        print("\nDone.")  # noqa: T201
    finally:
        import contextlib

        from dse.api.deps import get_search_service

        with contextlib.suppress(Exception):
            await get_search_service().close()


if __name__ == "__main__":
    asyncio.run(main())
