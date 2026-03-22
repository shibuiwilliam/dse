"""Manually trigger Temporal workflows from the command line.

Usage:
    python -m dse.workflows.trigger <workflow> [--namespace NS]

Examples:
    python -m dse.workflows.trigger prospective-scan
    python -m dse.workflows.trigger daily-maintenance --namespace user:ml-engineer
    python -m dse.workflows.trigger semantic-compression --namespace default --lookback-days 60
    python -m dse.workflows.trigger relation-discovery
    python -m dse.workflows.trigger temporal-edges
    python -m dse.workflows.trigger memory-write --record '{"namespace":"default","content_text":"hello"}'
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import click
from temporalio.client import Client
from temporalio.common import RetryPolicy

from dse.config import settings


async def _get_client() -> Client:
    return await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )


async def _start_workflow(
    workflow: str,
    args: list[object],
    task_queue: str,
    workflow_id: str | None = None,
) -> str:
    client = await _get_client()
    wf_id = workflow_id or f"{workflow}-manual-{uuid.uuid4().hex[:8]}"
    handle = await client.start_workflow(
        workflow,
        args=args,
        id=wf_id,
        task_queue=task_queue,
        retry_policy=RetryPolicy(maximum_attempts=1),
    )
    return handle.id


@click.group()
def cli() -> None:
    """Manually trigger DSE Temporal workflows."""


@cli.command()
@click.option("--namespace", default="default", help="Memory namespace to scan.")
def prospective_scan(namespace: str) -> None:
    """Scan and fire due prospective memories."""
    wf_id = asyncio.run(_start_workflow("ProspectiveScanWorkflow", [namespace], "dse-main"))
    click.echo(f"Started ProspectiveScanWorkflow: {wf_id}")


@cli.command()
@click.option("--namespace", default="default", help="Memory namespace.")
def daily_maintenance(namespace: str) -> None:
    """Update decay scores and archive decayed memories."""
    wf_id = asyncio.run(_start_workflow("DailyMaintenanceWorkflow", [namespace], "dse-maintenance"))
    click.echo(f"Started DailyMaintenanceWorkflow: {wf_id}")


@cli.command()
@click.option("--namespace", default="default", help="Memory namespace.")
@click.option("--lookback-days", default=30, help="Days to look back for episodes.")
def semantic_compression(namespace: str, lookback_days: int) -> None:
    """Distill episodic memory clusters into semantic knowledge."""
    wf_id = asyncio.run(
        _start_workflow(
            "P3SemanticCompressionWorkflow",
            [namespace, lookback_days],
            "dse-maintenance",
        )
    )
    click.echo(f"Started P3SemanticCompressionWorkflow: {wf_id}")


@cli.command()
@click.option("--namespace", default="default", help="Memory namespace.")
def relation_discovery(namespace: str) -> None:
    """Discover latent relations between memories via LLM."""
    wf_id = asyncio.run(
        _start_workflow("P3RelationDiscoveryWorkflow", [namespace], "dse-discovery")
    )
    click.echo(f"Started P3RelationDiscoveryWorkflow: {wf_id}")


@cli.command()
@click.option("--namespace", default="default", help="Memory namespace.")
def temporal_edges(namespace: str) -> None:
    """Build TEMPORALLY_PRECEDES edges via Allen's Interval Algebra."""
    wf_id = asyncio.run(_start_workflow("TemporalEdgeBuildWorkflow", [namespace], "dse-discovery"))
    click.echo(f"Started TemporalEdgeBuildWorkflow: {wf_id}")


@cli.command()
@click.option("--namespace", default="default", help="Memory namespace.")
def contradiction_check(namespace: str, memory_id: str = "") -> None:
    """Run contradiction check for a specific memory."""
    if not memory_id:
        click.echo("Error: --memory-id is required for contradiction-check", err=True)
        sys.exit(1)
    wf_id = asyncio.run(
        _start_workflow("ContradictionCheckWorkflow", [memory_id, namespace], "dse-main")
    )
    click.echo(f"Started ContradictionCheckWorkflow: {wf_id}")


@cli.command()
@click.option(
    "--record",
    required=True,
    help='JSON dict of the memory record (e.g. \'{"namespace":"default","content_text":"hello"}\')',
)
def memory_write(record: str) -> None:
    """Execute the full memory write saga."""
    try:
        record_dict = json.loads(record)
    except json.JSONDecodeError as e:
        click.echo(f"Error: invalid JSON: {e}", err=True)
        sys.exit(1)

    if "id" not in record_dict:
        record_dict["id"] = str(uuid.uuid4())

    wf_id = asyncio.run(_start_workflow("MemoryWriteWorkflow", [record_dict], "dse-main"))
    click.echo(f"Started MemoryWriteWorkflow: {wf_id}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
