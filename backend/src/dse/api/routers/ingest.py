from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from dse.api.deps import (
    get_embedding_service,
    get_graph_service,
    get_llm_service,
    get_search_service,
    get_storage_service,
)
from dse.core.models import MemoryRecord
from dse.services.embedding import EmbeddingService
from dse.services.graph import GraphService
from dse.services.llm import LLMService
from dse.services.search import SearchService
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/memories", tags=["ingest"])

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "text",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
}

# Also detect by extension when MIME is ambiguous
EXT_MAP = {
    ".pdf": "pdf",
    ".txt": "text",
    ".text": "text",
    ".md": "markdown",
    ".markdown": "markdown",
}


@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),  # noqa: B008
    namespace: str = Form(default="user:default"),
    memory_type: str = Form(default=""),
    source_type: str = Form(default="external_api"),
    tags: str = Form(default=""),
    chunk_size: int = Form(default=1000),
    overlap: int = Form(default=100),
    llm: Annotated[LLMService, Depends(get_llm_service)] = ...,  # noqa: B008
    embedding: Annotated[EmbeddingService, Depends(get_embedding_service)] = ...,  # noqa: B008
    search: Annotated[SearchService, Depends(get_search_service)] = ...,  # noqa: B008
    storage: Annotated[StorageService, Depends(get_storage_service)] = ...,  # noqa: B008
    graph: Annotated[GraphService, Depends(get_graph_service)] = ...,  # noqa: B008
) -> dict[str, Any]:
    """Ingest a document (text, Markdown, or PDF) into DSE memory.

    The file is processed through:
      1. Text extraction (direct read for text/md, Gemini OCR for PDF)
      2. Chunking with configurable size and overlap
      3. LLM enrichment per chunk (summary, tags, entities, importance)
      4. Embedding generation
      5. Registration in Elasticsearch, Object Storage, and Neo4j

    Accepts multipart/form-data with:
      - file: the document to ingest
      - namespace: target namespace (default: user:default)
      - memory_type: override memory type for all chunks (default: LLM-inferred)
      - source_type: observation | inference | user_explicit | external_api
      - tags: comma-separated additional tags
      - chunk_size: target chunk size in characters (default: 1000)
      - overlap: overlap between chunks in characters (default: 100)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    # Detect file type
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    file_type = EXT_MAP.get(ext) or SUPPORTED_TYPES.get(file.content_type or "")

    if not file_type:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type} ({ext}). Supported: .txt, .md, .pdf",
        )

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    tag_list.append(f"source:{file.filename}")

    source_id = f"document:{file.filename}:{uuid.uuid4().hex[:6]}"

    logger.info(
        "ingest.started",
        filename=file.filename,
        file_type=file_type,
        namespace=namespace,
        chunk_size=chunk_size,
    )

    # ── Step 1: Extract text ─────────────────────────────────────────
    import tempfile
    from pathlib import Path

    content = await file.read()

    if file_type == "pdf":
        # Write to temp file for Gemini Files API upload
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            text = await llm.extract_document_text(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    else:
        text = content.decode("utf-8")

    if not text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the document")

    # ── Step 2: Chunk and enrich ─────────────────────────────────────
    enriched_chunks = await llm.chunk_and_enrich_document(
        text,
        source_filename=file.filename,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    if not enriched_chunks:
        raise HTTPException(status_code=422, detail="Document produced no chunks")

    # ── Step 3: Register each chunk ──────────────────────────────────
    created_ids: list[str] = []
    errors: list[str] = []

    for chunk_data in enriched_chunks:
        try:
            chunk_text = str(chunk_data["content_text"])
            summary = str(chunk_data.get("summary", chunk_text[:150]))
            chunk_tags = list(chunk_data.get("tags", []))
            chunk_entities = list(chunk_data.get("entities", []))
            importance = float(chunk_data.get("importance_score", 0.5))
            inferred_type = str(chunk_data.get("memory_type", "semantic"))

            # memory_type: use override if provided, else LLM-inferred
            final_type = memory_type if memory_type else inferred_type
            if final_type not in ("episodic", "semantic", "procedural", "prospective"):
                final_type = "semantic"

            # Merge tags
            all_tags = list(set(tag_list + chunk_tags))
            chunk_idx = chunk_data.get("chunk_index", 0)
            total = chunk_data.get("total_chunks", len(enriched_chunks))
            all_tags.append(f"chunk:{int(chunk_idx) + 1}/{int(total)}")

            # Generate embedding
            embed_text = f"{summary} {' '.join(chunk_entities)}" if summary else chunk_text
            vector = await embedding.encode(embed_text)

            record = MemoryRecord(
                namespace=namespace,
                content_text=chunk_text,
                summary=summary,
                embedding=vector,
                memory_type=final_type,
                memory_subtype="observation",
                content_type="text",
                confidence=0.85,
                source_type=source_type,
                source_id=source_id,
                importance_score=importance,
                tags=all_tags,
                entities=chunk_entities,
                language="en",
            )

            # Store content
            content_path = await storage.store_content(
                record.namespace, record.id, record.content_text
            )
            record.content_path = content_path

            # Index
            await search.upsert(record)

            # Graph
            await graph.register_node(record)

            created_ids.append(record.id)
        except Exception as e:
            errors.append(f"Chunk {chunk_data.get('chunk_index', '?')}: {e}")
            logger.warning("ingest.chunk_failed", error=str(e))

    logger.info(
        "ingest.completed",
        filename=file.filename,
        chunks=len(enriched_chunks),
        created=len(created_ids),
        errors=len(errors),
    )

    return {
        "filename": file.filename,
        "file_type": file_type,
        "text_length": len(text),
        "chunks": len(enriched_chunks),
        "created": len(created_ids),
        "failed": len(errors),
        "memory_ids": created_ids,
        "errors": errors[:5],
    }
