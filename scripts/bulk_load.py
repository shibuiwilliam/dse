#!/usr/bin/env python3
"""Bulk-load memory records from a JSONL file into DSE via the REST API.

Each line in the JSONL file is sent to POST /v1/memories, which triggers
the full write path: LLM enrichment, embedding, Elasticsearch index,
object storage, and Neo4j graph registration.

Usage:
    python scripts/bulk_load.py data/sample_memories.jsonl
    python scripts/bulk_load.py data/sample_memories.jsonl --concurrency 10 --api-url http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import click
import httpx


async def post_memory(
    client: httpx.AsyncClient,
    record: dict,
    api_url: str,
    semaphore: asyncio.Semaphore,
) -> tuple[bool, str]:
    """Send a single memory record to the API. Returns (success, detail)."""
    async with semaphore:
        try:
            resp = await client.post(
                f"{api_url}/v1/memories",
                json=record,
                timeout=30.0,
            )
            if resp.status_code == 201:
                body = resp.json()
                return True, body.get("id", "ok")
            return False, f"HTTP {resp.status_code}: {resp.text[:120]}"
        except httpx.TimeoutException:
            return False, "timeout"
        except Exception as e:
            return False, str(e)[:120]


async def run_bulk(
    records: list[dict],
    api_url: str,
    concurrency: int,
    on_progress: callable,
) -> tuple[int, int, list[str]]:
    """Load all records with bounded concurrency. Returns (ok, fail, errors)."""
    semaphore = asyncio.Semaphore(concurrency)
    ok = 0
    fail = 0
    errors: list[str] = []

    async with httpx.AsyncClient() as client:
        tasks = [post_memory(client, rec, api_url, semaphore) for rec in records]

        for i, coro in enumerate(asyncio.as_completed(tasks)):
            success, detail = await coro
            if success:
                ok += 1
            else:
                fail += 1
                errors.append(detail)
            on_progress(i + 1, ok, fail)

    return ok, fail, errors


@click.command()
@click.argument("jsonl_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--api-url",
    default="http://localhost:8000",
    show_default=True,
    help="DSE API base URL.",
)
@click.option(
    "--concurrency",
    "-c",
    default=5,
    show_default=True,
    help="Max concurrent API requests.",
)
@click.option(
    "--limit",
    "-n",
    default=None,
    type=int,
    help="Only load the first N records (default: all).",
)
@click.option(
    "--skip",
    default=0,
    show_default=True,
    type=int,
    help="Skip the first N records.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Parse and validate the file without sending to API.",
)
def cli(
    jsonl_file: str,
    api_url: str,
    concurrency: int,
    limit: int | None,
    skip: int,
    dry_run: bool,
) -> None:
    """Bulk-load memory records from a JSONL file into DSE.

    \b
    Each line in JSONL_FILE must be a JSON object with at least:
      {"namespace": "...", "content_text": "..."}

    \b
    The API applies the full write path for each record:
      LLM enrichment → embedding → Elasticsearch → object storage → Neo4j graph

    \b
    Examples:
      python scripts/bulk_load.py data/sample_memories.jsonl
      python scripts/bulk_load.py data/sample_memories.jsonl -c 10 -n 100
      python scripts/bulk_load.py data/sample_memories.jsonl --dry-run
    """
    path = Path(jsonl_file)

    # ── Parse JSONL ──────────────────────────────────────────────────
    records: list[dict] = []
    parse_errors = 0

    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if lineno <= skip:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                if parse_errors <= 3:
                    click.echo(
                        f"  [warn] Line {lineno}: invalid JSON, skipped", err=True
                    )
                continue

            if "content_text" not in rec or "namespace" not in rec:
                parse_errors += 1
                if parse_errors <= 3:
                    click.echo(
                        f"  [warn] Line {lineno}: missing namespace/content_text, skipped",
                        err=True,
                    )
                continue

            records.append(rec)
            if limit and len(records) >= limit:
                break

    click.echo(f"DSE Bulk Loader", err=True)
    click.echo(f"  File:        {path} ({path.stat().st_size / 1024:.0f} KB)", err=True)
    click.echo(
        f"  Records:     {len(records)} (skipped {skip}, parse errors {parse_errors})",
        err=True,
    )
    click.echo(f"  API:         {api_url}", err=True)
    click.echo(f"  Concurrency: {concurrency}", err=True)
    click.echo(err=True)

    if not records:
        click.echo("No records to load.", err=True)
        return

    # ── Type distribution ────────────────────────────────────────────
    type_counts: dict[str, int] = {}
    for r in records:
        mt = r.get("memory_type", "episodic")
        type_counts[mt] = type_counts.get(mt, 0) + 1
    click.echo("  Type distribution:", err=True)
    for mt, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        click.echo(f"    {mt:15s} {c:5d}", err=True)
    click.echo(err=True)

    if dry_run:
        click.echo("Dry run — no records sent to API.", err=True)
        return

    # ── Health check ─────────────────────────────────────────────────
    try:
        resp = httpx.get(f"{api_url}/health", timeout=5.0)
        if resp.status_code != 200:
            click.echo(
                f"Error: API health check failed (HTTP {resp.status_code})", err=True
            )
            sys.exit(1)
    except httpx.ConnectError:
        click.echo(
            f"Error: Cannot connect to {api_url}. Is the API server running?", err=True
        )
        sys.exit(1)

    # ── Load ─────────────────────────────────────────────────────────
    start = time.monotonic()

    def on_progress(done: int, ok: int, fail: int) -> None:
        if done % 10 == 0 or done == len(records):
            elapsed = time.monotonic() - start
            rate = done / elapsed if elapsed > 0 else 0
            click.echo(
                f"\r  Progress: {done}/{len(records)} "
                f"({ok} ok, {fail} fail, {rate:.1f} rec/s)   ",
                nl=False,
                err=True,
            )

    ok, fail, errors = asyncio.run(run_bulk(records, api_url, concurrency, on_progress))

    elapsed = time.monotonic() - start
    click.echo(err=True)
    click.echo(err=True)
    click.echo(f"Done in {elapsed:.1f}s", err=True)
    click.echo(f"  Success: {ok}", err=True)
    click.echo(f"  Failed:  {fail}", err=True)
    if errors:
        click.echo(f"  First errors:", err=True)
        for e in errors[:5]:
            click.echo(f"    - {e}", err=True)


if __name__ == "__main__":
    cli()
