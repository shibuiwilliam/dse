from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from dse.core.enums import CascadeStage
from dse.services.embedding import EmbeddingService
from dse.services.llm import LLMService

logger = structlog.get_logger(__name__)


@dataclass
class SearchIntent:
    """Parsed search intent from a natural language query."""

    primary_intent: str
    memory_types: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    time_range: dict[str, str] | None = None
    urgency: str = "medium"


@dataclass
class SearchQuery:
    """Fully processed search query ready for execution."""

    text_queries: list[str]
    embedding: list[float]
    filters: dict[str, object]
    memory_types: list[str]
    cascade_stage: CascadeStage
    top_k: int = 20
    namespace: str | None = None
    exploration_factor: float = 0.05

    # Scoring weights
    relevance_weight: float = 0.5
    quality_weight: float = 0.3
    temporal_weight: float = 0.2


class QueryPreprocessor:
    """Transforms natural language queries into structured search queries."""

    def __init__(
        self,
        llm: LLMService,
        embedding: EmbeddingService,
    ) -> None:
        self._llm = llm
        self._embedding = embedding

    async def process(
        self,
        query: str,
        *,
        namespace: str | None = None,
        task_context: str = "",
        token_budget: int = 4000,
        cascade_stage: CascadeStage | None = None,
    ) -> SearchQuery:
        """Process a raw query into a structured SearchQuery."""
        # 1. Intent extraction
        intent = await self._extract_intent(query, task_context)

        # 2. Query expansion
        expanded = await self._expand_query(query, intent)

        # 3. Embedding generation
        embed_text = f"{intent.primary_intent} {' '.join(intent.entities)}"
        embedding = await self._embedding.encode_query(embed_text)

        # 4. Determine cascade stage
        stage = cascade_stage or self._select_stage(intent.urgency)

        # 5. Build filters
        filters = self._build_filters(intent, namespace)

        return SearchQuery(
            text_queries=expanded,
            embedding=embedding,
            filters=filters,
            memory_types=intent.memory_types,
            cascade_stage=stage,
            namespace=namespace,
            exploration_factor=self._exploration_factor(task_context),
        )

    async def _extract_intent(self, query: str, task_context: str) -> SearchIntent:
        """Use LLM to extract search intent from the query."""
        try:
            result = await self._llm.extract_intent(query, task_context)
            return SearchIntent(
                primary_intent=str(result.get("primary_intent", query)),
                memory_types=list(result.get("memory_types", [])),
                entities=list(result.get("entities", [])),
                time_range=result.get("time_range"),  # type: ignore[arg-type]
                urgency=str(result.get("urgency", "medium")),
            )
        except Exception:
            logger.warning("preprocessing.intent_extraction_failed", query=query)
            return SearchIntent(primary_intent=query)

    async def _expand_query(self, query: str, intent: SearchIntent) -> list[str]:
        """Generate multiple query variants for better recall."""
        queries = [query]
        if intent.primary_intent != query:
            queries.append(intent.primary_intent)
        if intent.entities:
            queries.append(" ".join(intent.entities))
        return queries

    @staticmethod
    def _select_stage(urgency: str) -> CascadeStage:
        mapping = {
            "high": CascadeStage.FAST,
            "medium": CascadeStage.PRECISION,
            "low": CascadeStage.DEEP,
        }
        return mapping.get(urgency, CascadeStage.PRECISION)

    @staticmethod
    def _build_filters(intent: SearchIntent, namespace: str | None) -> dict[str, object]:
        filters: dict[str, object] = {}
        if namespace:
            filters["namespace"] = namespace
        if intent.memory_types:
            filters["memory_types"] = intent.memory_types
        if intent.time_range:
            filters["time_range"] = intent.time_range
        return filters

    @staticmethod
    def _exploration_factor(task_context: str) -> float:
        """Adjust exploration based on task type."""
        context_lower = task_context.lower()
        if any(w in context_lower for w in ("creative", "brainstorm", "idea")):
            return 0.20
        if any(w in context_lower for w in ("debug", "fix", "error")):
            return 0.02
        return 0.05
