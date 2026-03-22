#!/usr/bin/env python3
"""Ingest a document (text, Markdown, or PDF) into DSE memory.

For text/Markdown files, the content is read directly and chunked.
For PDFs, the Gemini document processing API extracts text via OCR,
then chunks and registers each chunk as a memory.

Usage:
    python scripts/ingest_document.py paper.pdf
    python scripts/ingest_document.py notes.md --chunk-size 500
    python scripts/ingest_document.py report.pdf --namespace "project:alpha" --memory-type semantic
    python scripts/ingest_document.py README.txt --tags "docs,readme" --dry-run

Environment:
    GEMINI_API_KEY  — required for PDF processing and summary generation
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import sys
import time
import uuid
from pathlib import Path

import click
import httpx

# Load .env from project root if present
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from google import genai


# ── Text extraction ──────────────────────────────────────────────────────────


def read_text_file(path: Path) -> str:
    """Read a plain text or Markdown file."""
    return path.read_text(encoding="utf-8")


# PDF extraction requires a multimodal model — lite models can't process documents.
# This list is tried in order until one succeeds.
_PDF_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash",
]


async def extract_pdf_with_gemini(
    path: Path,
    client: genai.Client,
    model: str,
) -> str:
    """Upload a PDF to Gemini and extract its full text content.

    Tries the provided model first. If it fails or returns empty (common with
    lite models that lack vision), falls back to known multimodal models.
    """
    click.echo(f"  Uploading {path.name} to Gemini Files API...", err=True)
    uploaded = await client.aio.files.upload(file=path)

    # Build model list: user's model first, then fallbacks
    models_to_try = [model] + [m for m in _PDF_MODELS if m != model]
    prompt = (
        "Extract ALL text content from this document. "
        "Preserve the structure: headings, paragraphs, lists, tables, code blocks. "
        "Output the full text in Markdown format. Do not summarize — extract everything."
    )

    for try_model in models_to_try:
        click.echo(f"  Extracting text via Gemini ({try_model})...", err=True)
        try:
            response = await client.aio.models.generate_content(
                model=try_model,
                contents=[uploaded, prompt],
            )
            text = (response.text or "").strip()
            if text and len(text) > 50:
                click.echo(
                    f"  Extraction succeeded with {try_model} ({len(text)} chars).",
                    err=True,
                )
                return text
            click.echo(
                f"  [warn] {try_model} returned empty/short response, trying next...",
                err=True,
            )
        except Exception as e:
            click.echo(
                f"  [warn] {try_model} failed: {str(e)[:100]}, trying next...", err=True
            )

    # Last resort: return whatever we got
    click.echo("  [error] All models failed to extract text from PDF.", err=True)
    return ""


def detect_file_type(path: Path) -> str:
    """Detect whether a file is text, markdown, or PDF."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in (".md", ".markdown"):
        return "markdown"
    # Default: treat as plain text
    return "text"


# ── Chunking ─────────────────────────────────────────────────────────────────

import re
from dataclasses import dataclass, field


@dataclass
class _Section:
    """A section of a document defined by heading level and content."""

    heading: str
    level: int  # 0 = no heading (body text), 1 = h1, 2 = h2, etc.
    paragraphs: list[str] = field(default_factory=list)


def _parse_sections(text: str) -> list[_Section]:
    """Parse text into sections based on Markdown headings.

    Headings (# / ## / ###) create hard section boundaries.
    Text before the first heading goes into a level-0 section.
    """
    lines = text.split("\n")
    sections: list[_Section] = []
    current = _Section(heading="", level=0)
    current_para: list[str] = []

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            # Flush current paragraph
            if current_para:
                para_text = "\n".join(current_para).strip()
                if para_text:
                    current.paragraphs.append(para_text)
                current_para = []
            # Flush current section
            if current.paragraphs or current.heading:
                sections.append(current)
            # Start new section
            level = len(heading_match.group(1))
            current = _Section(heading=heading_match.group(2).strip(), level=level)
        elif line.strip() == "":
            # Paragraph break
            if current_para:
                para_text = "\n".join(current_para).strip()
                if para_text:
                    current.paragraphs.append(para_text)
                current_para = []
        else:
            current_para.append(line)

    # Flush remaining
    if current_para:
        para_text = "\n".join(current_para).strip()
        if para_text:
            current.paragraphs.append(para_text)
    if current.paragraphs or current.heading:
        sections.append(current)

    return sections


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _embed_paragraphs(
    paragraphs: list[str],
    gemini_client: genai.Client | None,
    model: str,
) -> list[list[float]] | None:
    """Embed paragraphs for semantic similarity. Returns None if unavailable."""
    if gemini_client is None or not paragraphs:
        return None

    try:
        embeddings: list[list[float]] = []
        for para in paragraphs:
            # Use first 500 chars of each paragraph to keep API calls fast
            result = await gemini_client.aio.models.embed_content(
                model=model,
                contents=para[:500],
                config=genai.types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            embeddings.append(list(result.embeddings[0].values))
        return embeddings
    except Exception:
        return None


async def chunk_text_semantic(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100,
    similarity_threshold: float = 0.5,
    gemini_client: genai.Client | None = None,
    embedding_model: str = "",
) -> list[str]:
    """Split text into semantically coherent chunks.

    Strategy:
      1. Parse document into sections (headings = hard boundaries)
      2. Within each section, compute embedding similarity between
         consecutive paragraphs
      3. Break chunks where similarity drops below threshold
      4. Merge small consecutive chunks within the same section
      5. Force-split any chunk that still exceeds chunk_size * 2

    Falls back to structural chunking (sections + paragraph grouping)
    when embeddings are unavailable.
    """
    text = text.strip()
    if not text:
        return []

    sections = _parse_sections(text)
    if not sections:
        return [text] if text else []

    all_chunks: list[str] = []

    for section in sections:
        heading_prefix = f"## {section.heading}\n\n" if section.heading else ""
        paragraphs = section.paragraphs

        if not paragraphs:
            if section.heading:
                all_chunks.append(f"## {section.heading}")
            continue

        # Try semantic grouping with embeddings
        embeddings = await _embed_paragraphs(paragraphs, gemini_client, embedding_model)

        if embeddings and len(embeddings) == len(paragraphs):
            # Semantic chunking: group paragraphs by embedding similarity
            groups: list[list[int]] = [[0]]

            for i in range(1, len(paragraphs)):
                sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
                current_group_text = "\n\n".join(paragraphs[j] for j in groups[-1])

                # Break if: similarity is low OR adding this paragraph would exceed size limit
                if (
                    sim < similarity_threshold
                    or len(current_group_text) + len(paragraphs[i]) > chunk_size
                ):
                    groups.append([i])
                else:
                    groups[-1].append(i)

            for group in groups:
                chunk_text_str = heading_prefix + "\n\n".join(
                    paragraphs[j] for j in group
                )
                all_chunks.append(chunk_text_str.strip())
        else:
            # Fallback: structural chunking (group paragraphs by size only)
            current = heading_prefix
            for para in paragraphs:
                if current and len(current) + len(para) + 2 > chunk_size:
                    all_chunks.append(current.strip())
                    current = heading_prefix + para
                else:
                    current = (
                        current + "\n\n" + para
                        if current.strip()
                        else heading_prefix + para
                    )

            if current.strip():
                all_chunks.append(current.strip())

    # Force-split any chunk that's still too large
    final: list[str] = []
    for chunk in all_chunks:
        if len(chunk) <= chunk_size * 2:
            final.append(chunk)
        else:
            # Split on sentence boundaries within the oversized chunk
            sentences = re.split(r"(?<=[.!?。！？])\s+", chunk)
            current = ""
            for sentence in sentences:
                if current and len(current) + len(sentence) + 1 > chunk_size:
                    final.append(current.strip())
                    current = sentence
                else:
                    current = current + " " + sentence if current else sentence
            if current.strip():
                final.append(current.strip())

    # Remove empty chunks
    return [c for c in final if c.strip()]


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[str]:
    """Synchronous fallback chunker (structural only, no embeddings)."""
    import asyncio

    return asyncio.run(
        chunk_text_semantic(text, chunk_size=chunk_size, overlap=overlap)
    )


# ── Summary generation ───────────────────────────────────────────────────────


async def generate_summary(
    client: genai.Client,
    model: str,
    text: str,
) -> str:
    """Generate a concise summary of a text chunk using Gemini."""
    prompt = (
        "Summarize the following text in 1-2 sentences (max 150 characters). "
        "Be specific and preserve key details.\n\n"
        f"{text[:2000]}"
    )
    config = genai.types.GenerateContentConfig(temperature=0.3)
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    summary = (response.text or text[:150]).strip()
    return summary[:200]


# ── Memory registration ─────────────────────────────────────────────────────


async def register_chunk(
    http_client: httpx.AsyncClient,
    api_url: str,
    record: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[bool, str]:
    """Send a single memory record to the DSE API."""
    async with semaphore:
        try:
            resp = await http_client.post(
                f"{api_url}/v1/memories",
                json=record,
                timeout=60.0,
            )
            if resp.status_code == 201:
                return True, resp.json().get("id", "ok")
            return False, f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as e:
            return False, str(e)[:120]


# ── Main pipeline ────────────────────────────────────────────────────────────


async def ingest(
    path: Path,
    file_type: str,
    gemini_client: genai.Client,
    model: str,
    api_url: str,
    namespace: str,
    memory_type: str,
    source_type: str,
    tags: list[str],
    chunk_size: int,
    overlap: int,
    concurrency: int,
    generate_summaries: bool,
    dry_run: bool,
) -> tuple[int, int]:
    """Full ingestion pipeline: extract → chunk → summarize → register."""

    # ── Step 1: Extract text ─────────────────────────────────────────
    click.echo(f"  Step 1: Extracting text ({file_type})...", err=True)
    if file_type == "pdf":
        text = await extract_pdf_with_gemini(path, gemini_client, model)
    else:
        text = read_text_file(path)

    if not text.strip():
        click.echo("  [error] No text extracted from document.", err=True)
        return 0, 0

    click.echo(f"  Extracted {len(text)} characters.", err=True)

    # ── Step 2: Semantic chunking ─────────────────────────────────────
    click.echo(
        f"  Step 2: Semantic chunking (size={chunk_size}, overlap={overlap})...",
        err=True,
    )
    embedding_model = os.environ.get(
        "GEMINI_EMBEDDING_MODEL", "gemini-embedding-2-preview"
    )
    chunks = await chunk_text_semantic(
        text,
        chunk_size=chunk_size,
        overlap=overlap,
        gemini_client=gemini_client,
        embedding_model=embedding_model,
    )
    click.echo(f"  Created {len(chunks)} chunks.", err=True)

    if not chunks:
        return 0, 0

    # ── Step 3: Build records ────────────────────────────────────────
    click.echo(f"  Step 3: Building memory records...", err=True)
    records: list[dict] = []
    source_id = f"document:{path.name}:{uuid.uuid4().hex[:6]}"

    for i, chunk in enumerate(chunks):
        summary = chunk[:150]

        if generate_summaries:
            try:
                summary = await generate_summary(gemini_client, model, chunk)
            except Exception:
                summary = chunk[:150]

        record = {
            "namespace": namespace,
            "content_text": chunk,
            "summary": summary,
            "memory_type": memory_type,
            "memory_subtype": "observation",
            "content_type": "text",
            "confidence": 0.85,
            "source_type": source_type,
            "source_id": source_id,
            "tags": [*tags, f"chunk:{i + 1}/{len(chunks)}"],
            "entities": [],
            "language": "en",
        }
        records.append(record)

    # ── Step 4: Register ─────────────────────────────────────────────
    if dry_run:
        click.echo(
            f"\n  Dry run — {len(records)} records would be registered.", err=True
        )
        click.echo(f"  Sample record:", err=True)
        click.echo(
            f"    {json.dumps(records[0], ensure_ascii=False)[:200]}...", err=True
        )
        return len(records), 0

    click.echo(
        f"  Step 4: Registering {len(records)} memories (concurrency={concurrency})...",
        err=True,
    )
    semaphore = asyncio.Semaphore(concurrency)
    ok = 0
    fail = 0

    async with httpx.AsyncClient() as http_client:
        tasks = [
            register_chunk(http_client, api_url, rec, semaphore) for rec in records
        ]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            success, detail = await coro
            if success:
                ok += 1
            else:
                fail += 1
                if fail <= 3:
                    click.echo(f"    [fail] {detail}", err=True)

            done = i + 1
            if done % 5 == 0 or done == len(records):
                click.echo(
                    f"\r    Progress: {done}/{len(records)} ({ok} ok, {fail} fail)   ",
                    nl=False,
                    err=True,
                )

    click.echo(err=True)
    return ok, fail


# ── CLI ──────────────────────────────────────────────────────────────────────


async def ingest_via_api(
    path: Path,
    api_url: str,
    namespace: str,
    memory_type: str,
    source_type: str,
    tags: list[str],
    chunk_size: int,
    overlap: int,
) -> tuple[int, int]:
    """Upload the file directly to the DSE ingest API endpoint.

    The server handles extraction, chunking, enrichment, and registration.
    """
    click.echo("  Uploading file to POST /v1/memories/ingest...", err=True)

    async with httpx.AsyncClient() as client:
        with open(path, "rb") as f:
            resp = await client.post(
                f"{api_url}/v1/memories/ingest",
                files={"file": (path.name, f, "application/octet-stream")},
                data={
                    "namespace": namespace,
                    "memory_type": memory_type,
                    "source_type": source_type,
                    "tags": ",".join(tags),
                    "chunk_size": str(chunk_size),
                    "overlap": str(overlap),
                },
                timeout=300.0,
            )

    if resp.status_code != 200:
        click.echo(f"  [error] HTTP {resp.status_code}: {resp.text[:200]}", err=True)
        return 0, 1

    body = resp.json()
    click.echo(
        f"  Extracted {body.get('text_length', '?')} chars, {body.get('chunks', '?')} chunks.",
        err=True,
    )
    return body.get("created", 0), body.get("failed", 0)


@click.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--mode",
    type=click.Choice(["client", "api"], case_sensitive=False),
    default="client",
    show_default=True,
    help="client: extract+chunk locally, register via POST /v1/memories. api: upload file to POST /v1/memories/ingest (server does everything).",
)
@click.option(
    "--api-url",
    default="http://localhost:8000",
    show_default=True,
    help="DSE API base URL.",
)
@click.option(
    "--namespace",
    "-ns",
    default="user:default",
    show_default=True,
    help="Target namespace.",
)
@click.option(
    "--memory-type",
    type=click.Choice(["episodic", "semantic", "procedural"], case_sensitive=False),
    default="semantic",
    show_default=True,
    help="Memory type for all chunks.",
)
@click.option(
    "--source-type",
    type=click.Choice(
        ["observation", "external_api", "user_explicit"], case_sensitive=False
    ),
    default="external_api",
    show_default=True,
    help="Source type for provenance.",
)
@click.option("--tags", default="", help="Comma-separated tags to add to all chunks.")
@click.option(
    "--chunk-size",
    default=1000,
    show_default=True,
    help="Target chunk size in characters.",
)
@click.option(
    "--overlap",
    default=100,
    show_default=True,
    help="Overlap between chunks in characters.",
)
@click.option(
    "--similarity-threshold",
    default=0.5,
    show_default=True,
    help="Cosine similarity threshold for semantic chunk boundaries (0.0-1.0).",
)
@click.option(
    "-c",
    "--concurrency",
    default=5,
    show_default=True,
    help="Max concurrent API requests (client mode).",
)
@click.option(
    "--summarize/--no-summarize",
    default=True,
    show_default=True,
    help="Generate LLM summaries per chunk (client mode).",
)
@click.option(
    "--model",
    default=None,
    help="Gemini model (client mode). [default: GEMINI_LLM_MODEL env]",
)
@click.option(
    "--api-key",
    default=None,
    help="Gemini API key (client mode). [default: GEMINI_API_KEY env]",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Extract and chunk without registering (client mode).",
)
def cli(
    file: str,
    mode: str,
    api_url: str,
    namespace: str,
    memory_type: str,
    source_type: str,
    tags: str,
    chunk_size: int,
    overlap: int,
    similarity_threshold: float,
    concurrency: int,
    summarize: bool,
    model: str | None,
    api_key: str | None,
    dry_run: bool,
) -> None:
    """Ingest a document (text, Markdown, or PDF) into DSE memory.

    \b
    Modes:
      client — Extract text locally (Gemini OCR for PDF), chunk, summarize,
               then register each chunk via POST /v1/memories.
      api    — Upload the file to POST /v1/memories/ingest and let the
               server handle everything (extraction, chunking, enrichment).

    \b
    Supported formats:
      .txt, .text    — plain text
      .md, .markdown — Markdown
      .pdf           — PDF (Gemini document processing / OCR)

    \b
    Examples:
      python scripts/ingest_document.py paper.pdf
      python scripts/ingest_document.py paper.pdf --mode api
      python scripts/ingest_document.py notes.md --no-summarize --mode client
      python scripts/ingest_document.py report.pdf -ns "project:alpha" --tags "report,q1"
      python scripts/ingest_document.py README.txt --dry-run
    """
    path = Path(file)
    file_type = detect_file_type(path)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    tag_list.append(f"source:{path.name}")

    click.echo("DSE Document Ingestion", err=True)
    click.echo(
        f"  File:        {path} ({path.stat().st_size / 1024:.0f} KB, {file_type})",
        err=True,
    )
    click.echo(f"  Mode:        {mode}", err=True)
    click.echo(f"  Namespace:   {namespace}", err=True)
    click.echo(f"  Memory type: {memory_type}", err=True)
    click.echo(f"  API:         {api_url}", err=True)
    click.echo(err=True)

    start = time.monotonic()

    if mode == "api":
        # Server-side: upload file to the ingest endpoint
        ok, fail = asyncio.run(
            ingest_via_api(
                path=path,
                api_url=api_url,
                namespace=namespace,
                memory_type=memory_type,
                source_type=source_type,
                tags=tag_list,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
    else:
        # Client-side: extract, chunk, summarize locally, then register per-chunk
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if file_type == "pdf" and not resolved_key:
            raise click.UsageError(
                "GEMINI_API_KEY required for PDF processing. Pass --api-key or set env."
            )
        if summarize and not resolved_key:
            raise click.UsageError(
                "GEMINI_API_KEY required for --summarize. Pass --api-key, set env, or use --no-summarize."
            )

        resolved_model = model or os.environ.get(
            "GEMINI_LLM_MODEL", "gemini-3-flash-preview"
        )
        gemini_client = genai.Client(api_key=resolved_key) if resolved_key else None

        ok, fail = asyncio.run(
            ingest(
                path=path,
                file_type=file_type,
                gemini_client=gemini_client,
                model=resolved_model,
                api_url=api_url,
                namespace=namespace,
                memory_type=memory_type,
                source_type=source_type,
                tags=tag_list,
                chunk_size=chunk_size,
                overlap=overlap,
                concurrency=concurrency,
                generate_summaries=summarize and gemini_client is not None,
                dry_run=dry_run,
            )
        )

    elapsed = time.monotonic() - start

    click.echo(f"\nDone in {elapsed:.1f}s.", err=True)
    if not dry_run:
        click.echo(f"  Registered: {ok}", err=True)
        click.echo(f"  Failed:     {fail}", err=True)


if __name__ == "__main__":
    cli()
