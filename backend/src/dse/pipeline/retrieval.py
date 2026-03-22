from __future__ import annotations

from typing import Any

import structlog

from dse.core.enums import CascadeStage
from dse.core.models import AssembledContext, MemoryRecord, SearchResult
from dse.pipeline.assembly import ContextAssembler
from dse.pipeline.preprocessing import QueryPreprocessor, SearchQuery
from dse.pipeline.ranking import rerank
from dse.services.cache import CacheService
from dse.services.embedding import EmbeddingService
from dse.services.graph import GraphService
from dse.services.llm import LLMService
from dse.services.search import SearchService
from dse.services.storage import StorageService

logger = structlog.get_logger(__name__)


class CascadeRetrieval:
    """Implements the 3-stage Cascade Retrieval pipeline.

    Stage 1 (Fast, <50ms):    Cache + approximate nearest neighbor
    Stage 2 (Precision, <200ms): Exact KNN + BM25 hybrid with re-ranking
    Stage 3 (Deep, <1000ms):  Graph traversal + LLM context scoring
    """

    def __init__(
        self,
        search: SearchService,
        embedding: EmbeddingService,
        graph: GraphService,
        cache: CacheService,
        storage: StorageService,
        llm: LLMService,
    ) -> None:
        self._search = search
        self._embedding = embedding
        self._graph = graph
        self._cache = cache
        self._storage = storage
        self._llm = llm
        self._preprocessor = QueryPreprocessor(llm, embedding)
        self._assembler = ContextAssembler(storage)

    async def retrieve(
        self,
        query: str,
        *,
        namespace: str | None = None,
        memory_types: list[str] | None = None,
        token_budget: int = 4000,
        cascade_stage: CascadeStage | None = None,
        task_context: str = "",
    ) -> AssembledContext:
        """Execute cascade retrieval and return assembled context."""
        # Preprocess query
        search_query = await self._preprocessor.process(
            query,
            namespace=namespace,
            task_context=task_context,
            token_budget=token_budget,
            cascade_stage=cascade_stage,
        )

        if memory_types:
            search_query.memory_types = memory_types

        # Execute retrieval stages
        stage = search_query.cascade_stage

        if stage == CascadeStage.FAST:
            results = await self._stage_fast(search_query)
        elif stage == CascadeStage.PRECISION:
            results = await self._stage_precision(search_query)
        else:
            results = await self._stage_deep(search_query)

        # Assemble context within token budget
        return await self._assembler.assemble(
            results,
            token_budget,
            query=query,
            namespace=namespace or "",
        )

    async def _stage_fast(self, query: SearchQuery) -> list[SearchResult]:
        """Stage 1: Fast path — cache + basic vector search."""
        logger.debug("retrieval.stage_fast")

        # Try cache first
        # For simplicity, do a single vector-based search
        raw_results = await self._search.search(
            query.text_queries[0],
            memory_types=query.memory_types or None,
            namespace=query.namespace,
            top_k=query.top_k,
        )

        return self._parse_results(raw_results, "vector")

    async def _stage_precision(self, query: SearchQuery) -> list[SearchResult]:
        """Stage 2: Precision path — hybrid search with re-ranking."""
        logger.debug("retrieval.stage_precision")

        # Execute BM25 and vector searches
        bm25_raw = await self._search.search(
            query.text_queries[0],
            memory_types=query.memory_types or None,
            namespace=query.namespace,
            top_k=query.top_k,
        )
        bm25_results = self._parse_results(bm25_raw, "bm25")

        # For additional query variants
        vector_results: list[SearchResult] = []
        for q in query.text_queries[1:2]:  # Use first expansion
            raw = await self._search.search(
                q,
                memory_types=query.memory_types or None,
                namespace=query.namespace,
                top_k=query.top_k,
            )
            vector_results.extend(self._parse_results(raw, "vector"))

        if not vector_results:
            vector_results = bm25_results

        return rerank(bm25_results, vector_results, query)

    async def _stage_deep(self, query: SearchQuery) -> list[SearchResult]:
        """Stage 3: Deep path — precision + graph expansion."""
        logger.debug("retrieval.stage_deep")

        # First get precision results
        precision_results = await self._stage_precision(query)

        # Expand with graph neighbors
        expanded: list[SearchResult] = list(precision_results)
        seen_ids = {r.record.id for r in precision_results}

        from dse.config import settings as _settings
        from dse.core.enums import RelationType

        for result in precision_results[:5]:  # Expand top-5 only
            try:
                neighbors = await self._graph.get_neighbors(
                    result.record.id,
                    hop_depth=_settings.graph_default_hop_depth,
                    exclude_relation_types=[RelationType.CONTRADICTS],
                    limit=3,
                )
                for neighbor in neighbors:
                    nid = neighbor.get("id")
                    if nid and nid not in seen_ids:
                        seen_ids.add(nid)
                        # Create a SearchResult from neighbor data
                        neighbor_record = MemoryRecord(
                            id=nid,
                            namespace=query.namespace or "",
                            summary=neighbor.get("summary", ""),
                            memory_type=neighbor.get("memory_type", "episodic"),
                            confidence=neighbor.get("confidence", 0.5),
                        )
                        expanded.append(
                            SearchResult(
                                record=neighbor_record,
                                score=result.score * 0.6,  # Discount graph expansions
                                match_source="graph",
                            )
                        )
            except Exception:
                logger.warning(
                    "retrieval.graph_expansion_failed",
                    memory_id=result.record.id,
                )

        expanded.sort(key=lambda x: x.score, reverse=True)
        return expanded[: query.top_k]

    @staticmethod
    def _parse_results(raw: list[dict[str, Any]], source: str) -> list[SearchResult]:
        """Convert raw search results to SearchResult models."""
        results: list[SearchResult] = []
        for item in raw:
            try:
                # Handle created_at: could be datetime, string, or missing
                created_at = item.get("created_at")
                if isinstance(created_at, str):
                    from datetime import datetime

                    created_at = datetime.fromisoformat(created_at)
                elif created_at is None:
                    from datetime import UTC, datetime

                    created_at = datetime.now(UTC)

                # Handle memory_type: could be MemoryType enum or string
                memory_type = item.get("memory_type", "episodic")
                if hasattr(memory_type, "value"):
                    memory_type = memory_type.value

                record = MemoryRecord(
                    id=item.get("id", ""),
                    namespace=item.get("namespace", ""),
                    summary=item.get("summary", ""),
                    content_text=item.get("content_text", ""),
                    content_path=item.get("content_path", ""),
                    memory_type=memory_type,
                    confidence=float(item.get("confidence", 0.5)),
                    decay_score=float(item.get("decay_score", 1.0)),
                    importance_score=float(item.get("importance_score", 0.5)),
                    access_count_30d=int(item.get("access_count_30d", 0)),
                    superseded_by=item.get("superseded_by"),
                    created_at=created_at,
                )
                results.append(SearchResult(record=record, score=0.0, match_source=source))
            except Exception:
                logger.warning("retrieval.parse_failed", item_id=item.get("id"))
        return results
