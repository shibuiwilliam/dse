# DSE — Phase 3: Intelligence Implementation Guide

> **Target Phase**: Phase 3: Intelligence
> **Prerequisites**: Phase 1 (Elasticsearch basic search, GCS storage, FastAPI, basic MMA) and
>                    Phase 2 (Neo4j Graph DB, contradiction detection, Confidence, Working Memory, CDC, Provenance) are complete
> **Design Reference**: `docs/DSE_Design_Report.md` (especially sections 5.3-5.5, 6.1-6.3, 6.6, 7, 9.1)

---

## How to Use This File

Claude Code must read this entire file before starting any task.
When implementation questions arise, refer to the relevant section in `docs/DSE_Design_Report.md` before making decisions.
**Follow this order: Read design report -> Implement -> Add tests. Do not skip this sequence.**

---

## Features to Implement in Phase 3

The theme of Phase 3 is **"intelligent management features where memories autonomously improve"**.
Build a self-evolution loop where memory quality improves the more the agent is used.

| # | Feature | Priority | Design Report Reference |
|---|---------|----------|------------------------|
| P3-1 | Semantic Compression (episodic -> semantic distillation) | Highest | Section 5.3 |
| P3-2 | Prospective Memory Engine (future intentions, automatic firing) | Highest | Section 6.1 |
| P3-3 | Automatic Relation Discovery | High | Section 9.1 |
| P3-4 | Temporal Reasoning (Allen's Interval Algebra) | High | Section 6.3 |
| P3-5 | Contextual Importance Estimator (dynamic importance evaluation) | High | Section 6.6, 7.2 |
| P3-6 | Human-in-the-Loop Curation UI (memory management dashboard) | Medium | Section 5.4 |

**Implementation order**: P3-5 -> P3-1 -> P3-3 -> P3-4 -> P3-2 -> P3-6

> P3-5 is implemented first because P3-1 (Semantic Compression) references
> importance_score when selecting distillation candidates, so importance evaluation is needed first.

---

## Critical Rules (Highest Priority)

1. **Read this entire file before starting implementation**
2. **Type annotations are mandatory** — Include `from __future__ import annotations` at the top of every Python file
3. **Never merge code without tests** — Add tests under `tests/` for each feature
4. **Never hardcode secrets in code** — Use `.env` only
5. **Do not call `datetime.now()` / `random()` directly in Temporal Workflows** — Use `workflow.now()` / `workflow.random()`
6. **Confine batch processing like HDBSCAN to Temporal Activities** — Do not write it directly in Workflows
7. **Route all Gemini API calls through `services/llm.py`** — No direct calls allowed
8. **Semantic Compression must be idempotent** — Running twice on the same episode group must not change the result
9. **Prospective Memory firing must always go through Temporal Workflows** — Do not fire directly from FastAPI handlers
10. **Maintain the ability to start all local services with `make dev`**

---

## Tech Stack (Phase 3 Additions)

### Additional Python Dependencies

```toml
# Add to pyproject.toml
[project.dependencies]
# Phase 3 additions
hdbscan = ">=0.8"           # Episodic memory clustering (Semantic Compression)
numpy = ">=2.0"             # Vector operations
scikit-learn = ">=1.5"      # Cosine similarity computation, PCA (visualization aid)
apscheduler = ">=3.10"      # Local scheduler for Prospective Memory scanning
                            # (replaced by Temporal Schedule in production)
```

> **Note**: `hdbscan` includes C extensions, so `build-essential` is needed
> during Docker image builds. Add it to the `Dockerfile` dependencies.

### Additional Frontend Dependencies

```bash
pnpm add @xyflow/react          # Graph visualization (continued from Phase 2)
pnpm add recharts               # Importance score trend charts
pnpm add @radix-ui/react-dialog # Modal (Curation UI)
pnpm add @radix-ui/react-tabs   # Tabs (Curation dashboard)
pnpm add cmdk                   # Command palette (memory search)
```

---

## Directory Structure (Phase 3 Additions/Changes)

```
backend/src/dse/
|
├── intelligence/                    # [NEW DIRECTORY] Phase 3 core logic
│   ├── __init__.py
│   ├── compression.py               # Semantic Compression engine
│   ├── prospective.py               # Prospective Memory engine
│   ├── relation_discovery.py        # Automatic relation discovery engine
│   ├── temporal_reasoning.py        # Allen's Interval Algebra
│   └── importance.py                # Contextual Importance Estimator
│
├── agents/
│   └── mma/
│       ├── agent.py                 # [EXISTING - EXTENDED] Phase 3 tool additions
│       └── tools/
│           ├── compression.py       # [NEW] compress_memories_tool
│           ├── prospective.py       # [NEW] schedule_prospective_tool, fire_prospective_tool
│           ├── discovery.py         # [NEW] discover_relations_tool
│           ├── temporal.py          # [NEW] classify_temporal_relation_tool
│           └── importance.py        # [NEW] estimate_importance_tool, reinforce_memory_tool
│
├── workflows/
│   ├── activities/
│   │   ├── compression.py           # [NEW] Semantic Compression activities
│   │   ├── prospective.py           # [NEW] Prospective Memory activities
│   │   ├── discovery.py             # [NEW] Relation discovery activities
│   │   ├── temporal.py              # [NEW] Temporal Reasoning activities
│   │   └── importance.py            # [NEW] Importance evaluation/reinforcement activities
│   └── definitions/
│       ├── semantic_compression.py  # [NEW] SemanticCompressionWorkflow
│       ├── prospective_scan.py      # [NEW] ProspectiveScanWorkflow
│       ├── relation_discovery.py    # [NEW] RelationDiscoveryWorkflow
│       └── daily_maintenance.py     # [EXISTING - EXTENDED] Phase 3 batches added
│
├── api/
│   └── routers/
│       ├── curation.py              # [NEW] Human-in-the-Loop Curation API
│       ├── prospective.py           # [NEW] Prospective Memory API
│       └── intelligence.py          # [NEW] Phase 3 statistics/trigger API
│
└── pipeline/
    └── retrieval.py                 # [EXISTING - EXTENDED] Integrate Temporal Reasoning into Stage 3

frontend/src/
├── app/
│   ├── curation/                    # [NEW] Human-in-the-Loop Curation UI
│   │   ├── page.tsx                 # Curation dashboard main page
│   │   └── components/
│   │       ├── MemoryBrowser.tsx    # Memory list/search/filter
│   │       ├── MemoryEditor.tsx     # Memory content editor modal
│   │       ├── ImportanceChart.tsx  # Importance score trends
│   │       ├── CompressionPanel.tsx # Semantic Compression execution/results
│   │       └── ProspectiveList.tsx  # Prospective Memory list/management
│   └── intelligence/                # [NEW] Autonomous improvement monitoring
│       ├── page.tsx
│       └── components/
│           ├── CompressionHistory.tsx   # Distillation history
│           ├── DiscoveryLog.tsx         # Relation discovery log
│           └── ImportanceHeatmap.tsx    # Namespace-wide importance heatmap
└── lib/
    └── api/
        ├── curation.ts              # [NEW] Curation API client
        ├── prospective.ts           # [NEW] Prospective API client
        └── intelligence.ts          # [NEW] Intelligence API client
```

---

## Environment Variables (Phase 3 Additions)

Add the following to `.env.example`:

```bash
# --- Phase 3: Semantic Compression ---
# Minimum number of episodes in a cluster (below this, do not distill)
COMPRESSION_MIN_CLUSTER_SIZE=5
# Minimum average confidence for a distillation candidate cluster
COMPRESSION_MIN_AVG_CONFIDENCE=0.70
# Embedding similarity threshold for finding similar episodes
COMPRESSION_SIMILARITY_THRESHOLD=0.75
# Time period (in days) to look back for Semantic Compression batch
COMPRESSION_LOOKBACK_DAYS=30
# Penalty multiplier for source episode importance_score after distillation
COMPRESSION_SOURCE_IMPORTANCE_DECAY=0.5

# --- Phase 3: Prospective Memory ---
# Prospective scan interval (seconds) - for local development
PROSPECTIVE_SCAN_INTERVAL_SECONDS=60
# Days until fired Prospective Memories are auto-archived
PROSPECTIVE_ARCHIVE_AFTER_DAYS=7

# --- Phase 3: Relation Discovery ---
# Embedding similarity threshold for finding relation candidate pairs
DISCOVERY_SIMILARITY_THRESHOLD=0.75
# Minimum LLM judgment confidence to register a relation in the graph
DISCOVERY_MIN_LLM_CONFIDENCE=0.70
# Maximum number of pairs to process per discovery batch (cost control)
DISCOVERY_MAX_PAIRS_PER_BATCH=200

# --- Phase 3: Temporal Reasoning ---
# Time window (days) for automatic TEMPORALLY_PRECEDES edge assignment
TEMPORAL_WINDOW_DAYS=7

# --- Phase 3: Importance Estimator ---
# Minimum importance_score value (never goes below 0.0)
IMPORTANCE_SCORE_MIN=0.05
# Maximum importance_score value (never exceeds 1.0)
IMPORTANCE_SCORE_MAX=1.0
# Decay recovery: recovery coefficient on user access
IMPORTANCE_USER_ACCESS_RECOVERY=0.15
# Decay recovery: recovery coefficient on agent access
IMPORTANCE_AGENT_ACCESS_RECOVERY=0.05
```

---

## P3-5: Contextual Importance Estimator — Implementation Spec

> See Design Report sections 6.6 and 7.2.
> Implemented first because P3-1 depends on it.

### Importance Estimator Core Logic

File: `backend/src/dse/intelligence/importance.py`

```python
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from dse.services.llm import LLMService

logger = structlog.get_logger(__name__)

# --- Signal Definitions ---
# Conforms to Design Report section 6.6. Update the report when modifying this code.
CONTENT_SIGNALS: dict[str, float] = {
    "contains_decision":         0.30,   # Decision record
    "contains_error_correction": 0.25,   # Error correction
    "contains_user_preference":  0.20,   # User preference
    "contains_factual_claim":    0.15,   # Factual claim
    "contains_deadline":         0.25,   # Deadline
}

BEHAVIOR_SIGNALS: dict[str, float] = {
    "user_explicitly_marked":   0.50,   # User marked as important
    "agent_re_referenced":      0.10,   # Agent re-referenced
    "led_to_successful_action": 0.20,   # Contributed to successful action
    "led_to_failed_action":    -0.10,   # Used in failed action
}

STRUCTURAL_SIGNALS: dict[str, float] = {
    "many_dependents_in_graph": 0.15,   # Referenced by many memories
    "unique_in_namespace":      0.10,   # Rare information with no similar records
}

BASELINE = 0.5  # Score baseline


@dataclass
class ImportanceContext:
    """Context information used for importance evaluation."""
    user_explicitly_marked: bool = False
    agent_re_referenced_count: int = 0
    led_to_successful_action: bool = False
    led_to_failed_action: bool = False
    graph_dependent_count: int = 0    # Number of other memories referencing this one
    similar_memory_count: int = 0     # Number of similar memories (0 = rare)
    utility_score: float | None = None


class ImportanceEstimator:
    """Dynamically evaluates memory importance based on context.

    Combines content signals (detected by LLM) + behavior signals (usage history) +
    structural signals (graph dependency count) to compute a score.
    See Design Report section 6.6.
    """

    def __init__(self) -> None:
        self._llm = LLMService()

    async def estimate(
        self,
        memory_id: str,
        summary: str,
        memory_type: str,
        context: ImportanceContext,
    ) -> float:
        """Compute and return an importance score (0.0-1.0)."""
        score = BASELINE

        # --- Content Signals (using LLM) ---
        content_flags = await self._detect_content_signals(summary)
        for signal, weight in CONTENT_SIGNALS.items():
            if content_flags.get(signal, False):
                score += weight
                logger.debug("importance.signal_fired",
                             memory_id=memory_id, signal=signal, weight=weight)

        # --- Behavior Signals (from context) ---
        if context.user_explicitly_marked:
            score += BEHAVIOR_SIGNALS["user_explicitly_marked"]
        if context.agent_re_referenced_count > 0:
            score += BEHAVIOR_SIGNALS["agent_re_referenced"] * min(context.agent_re_referenced_count, 5)
        if context.led_to_successful_action:
            score += BEHAVIOR_SIGNALS["led_to_successful_action"]
        if context.led_to_failed_action:
            score += BEHAVIOR_SIGNALS["led_to_failed_action"]

        # --- Structural Signals ---
        if context.graph_dependent_count >= 3:
            score += STRUCTURAL_SIGNALS["many_dependents_in_graph"]
        if context.similar_memory_count == 0:
            score += STRUCTURAL_SIGNALS["unique_in_namespace"]

        # Procedural memories maintain higher importance (procedures are rare and valuable)
        if memory_type == "procedural":
            score = max(score, 0.60)

        final = _clamp(score)
        logger.info("importance.estimated",
                    memory_id=memory_id, score=final, memory_type=memory_type)
        return final

    async def reinforce(
        self,
        current_score: float,
        utility_score: float,
        accessor_type: str,  # "user" | "agent"
    ) -> float:
        """Reinforce importance_score based on post-access feedback.

        See Design Report section 7.2 Memory Reinforcement.
        """
        recovery_rate = (
            0.15 if accessor_type == "user" else 0.05
        )
        recovery = utility_score * recovery_rate
        return _clamp(current_score + recovery)

    async def _detect_content_signals(self, summary: str) -> dict[str, bool]:
        """Detect content signals using LLM.

        Uses only the summary for cost reduction (does not use full content).
        """
        prompt = f"""
Detect all applicable signals from the following memory summary.

Memory: {summary}

Signal list (answer true/false):
- contains_decision: Is this a record of a decision?
- contains_error_correction: Is this a record of an error or correction?
- contains_user_preference: Is this about user preferences?
- contains_factual_claim: Is this a verifiable factual claim?
- contains_deadline: Does it contain deadlines or scheduled dates?

Return ONLY the following JSON (no preamble):
{{
  "contains_decision": true|false,
  "contains_error_correction": true|false,
  "contains_user_preference": true|false,
  "contains_factual_claim": true|false,
  "contains_deadline": true|false
}}
"""
        return await self._llm.generate_json(prompt)


def _clamp(v: float) -> float:
    from dse.config import settings
    return max(settings.importance_score_min, min(settings.importance_score_max, v))
```

### Importance Activities

File: `backend/src/dse/workflows/activities/importance.py`

```python
from __future__ import annotations

from temporalio import activity

from dse.intelligence.importance import ImportanceContext, ImportanceEstimator
from dse.services.search import SearchService


@activity.defn
async def estimate_importance_activity(
    memory_id: str,
    context_dict: dict,
) -> float:
    """Activity that computes a memory's importance score and updates the Search Index."""
    search_svc = SearchService()
    record = await search_svc.get_by_id(memory_id)
    if record is None:
        raise ValueError(f"Memory not found: {memory_id}")

    estimator = ImportanceEstimator()
    context = ImportanceContext(**context_dict)
    new_score = await estimator.estimate(
        memory_id=memory_id,
        summary=record["summary"],
        memory_type=record["memory_type"],
        context=context,
    )

    await search_svc.patch(memory_id, {
        "importance_score": new_score,
        "importance_updated_at": _now_iso(),
    })
    return new_score


@activity.defn
async def reinforce_memory_activity(
    memory_id: str,
    utility_score: float,
    accessor_type: str,
) -> float:
    """Reinforce importance_score and decay_score based on post-access feedback."""
    search_svc = SearchService()
    record = await search_svc.get_by_id(memory_id)
    if record is None:
        raise ValueError(f"Memory not found: {memory_id}")

    estimator = ImportanceEstimator()

    # Reinforce importance
    new_importance = await estimator.reinforce(
        current_score=record["importance_score"],
        utility_score=utility_score,
        accessor_type=accessor_type,
    )

    # Reinforce decay (recovered on access)
    from dse.config import settings
    recovery_rate = (
        settings.importance_user_access_recovery
        if accessor_type == "user"
        else settings.importance_agent_access_recovery
    )
    new_decay = min(1.0, record["decay_score"] + utility_score * recovery_rate)

    await search_svc.patch(memory_id, {
        "importance_score": new_importance,
        "decay_score": new_decay,
        "access_count": record.get("access_count", 0) + 1,
        "access_count_7d": record.get("access_count_7d", 0) + 1,
        "access_count_30d": record.get("access_count_30d", 0) + 1,
        "accessed_at": _now_iso(),
        "last_access_utility": utility_score,
    })
    return new_importance


def _now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
```

---

## P3-1: Semantic Compression — Implementation Spec

> See Design Report section 5.3.
> **Idempotency is required**: Running twice on the same episode group
> must not create duplicate semantic memories.

### Compression Engine

File: `backend/src/dse/intelligence/compression.py`

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import hdbscan
import numpy as np
import structlog

from dse.config import settings
from dse.core.enums import RelationType
from dse.services.embedding import EmbeddingService
from dse.services.graph import GraphService
from dse.services.llm import LLMService
from dse.services.search import SearchService

logger = structlog.get_logger(__name__)


@dataclass
class CompressionCluster:
    """Distillation candidate cluster."""
    episode_ids: list[str]
    episode_summaries: list[str]
    avg_confidence: float
    embeddings: list[list[float]]


@dataclass
class CompressionResult:
    """Distillation result."""
    semantic_memory_id: str
    source_episode_ids: list[str]
    generated_summary: str
    confidence: float
    skipped_reason: str | None = None  # None = success, string = skip reason


class SemanticCompressionEngine:
    """Analyzes groups of episodic memories and distills them into semantic memories.

    Processing flow:
      1. Retrieve episodic memories for the target period
      2. HDBSCAN vector clustering
      3. Distillation condition check (minimum count, minimum confidence, no existing semantic)
      4. Generalize and summarize cluster using Gemini
      5. Register as new semantic memory
      6. Connect to source episodes with DERIVES edges
      7. Decay source episode importance

    See Design Report section 5.3.
    """

    def __init__(self) -> None:
        self._search = SearchService()
        self._embed = EmbeddingService()
        self._llm = LLMService()
        self._graph = GraphService()

    async def run(self, namespace: str, lookback_days: int | None = None) -> list[CompressionResult]:
        """Execute compression batch and return results list."""
        days = lookback_days or settings.compression_lookback_days
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Step 1: Retrieve episodic memories
        episodes = await self._fetch_episodes(namespace, since=cutoff)
        if len(episodes) < settings.compression_min_cluster_size:
            logger.info("compression.skipped_too_few", namespace=namespace, count=len(episodes))
            return []

        # Step 2: Clustering
        clusters = await self._cluster(episodes)
        logger.info("compression.clusters_found", namespace=namespace, count=len(clusters))

        # Steps 3-7: Distill each cluster
        results: list[CompressionResult] = []
        for cluster in clusters:
            result = await self._distill_cluster(namespace, cluster)
            results.append(result)

        return results

    # --- private ---

    async def _fetch_episodes(self, namespace: str, since: datetime) -> list[dict]:
        """Retrieve episodic memories for the target period."""
        return await self._search.query(
            namespace=namespace,
            memory_types=["episodic"],
            created_after=since.isoformat(),
            is_archived=False,
            page_size=500,
        )

    async def _cluster(self, episodes: list[dict]) -> list[CompressionCluster]:
        """Build semantic clusters using HDBSCAN."""
        if not episodes:
            return []

        # Get embeddings (from Search Index)
        embeddings = [ep.get("embedding") or await self._embed.encode(ep["summary"])
                      for ep in episodes]
        matrix = np.array(embeddings, dtype=np.float32)

        # HDBSCAN clustering
        # min_cluster_size: minimum cluster size
        # metric: euclidean distance (optimal for embedding space)
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=settings.compression_min_cluster_size,
            metric="euclidean",   # Gemini Embeddings are L2-normalized, so euclidean ~ cosine
            cluster_selection_method="eom",
        )
        labels = clusterer.fit_predict(matrix)

        # label=-1 is noise (does not belong to any cluster) -> exclude
        cluster_map: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            if label >= 0:
                cluster_map.setdefault(label, []).append(idx)

        clusters: list[CompressionCluster] = []
        for indices in cluster_map.values():
            cluster_episodes = [episodes[i] for i in indices]
            avg_conf = sum(ep.get("confidence", 0.5) for ep in cluster_episodes) / len(cluster_episodes)

            clusters.append(CompressionCluster(
                episode_ids=[ep["id"] for ep in cluster_episodes],
                episode_summaries=[ep["summary"] for ep in cluster_episodes],
                avg_confidence=avg_conf,
                embeddings=[embeddings[i] for i in indices],
            ))

        return clusters

    async def _distill_cluster(
        self,
        namespace: str,
        cluster: CompressionCluster,
    ) -> CompressionResult:
        """Distill a cluster into a single semantic memory."""

        # Distillation condition check: skip clusters with too low average confidence
        if cluster.avg_confidence < settings.compression_min_avg_confidence:
            return CompressionResult(
                semantic_memory_id="",
                source_episode_ids=cluster.episode_ids,
                generated_summary="",
                confidence=0.0,
                skipped_reason=f"avg_confidence={cluster.avg_confidence:.2f} < threshold",
            )

        # Distillation condition check: verify no existing similar semantic memory (idempotency)
        cluster_center_embedding = np.mean(cluster.embeddings, axis=0).tolist()
        existing = await self._search.vector_search(
            embedding=cluster_center_embedding,
            namespace=namespace,
            memory_types=["semantic"],
            top_k=1,
            min_score=settings.compression_similarity_threshold,
        )
        if existing:
            return CompressionResult(
                semantic_memory_id=existing[0]["id"],
                source_episode_ids=cluster.episode_ids,
                generated_summary=existing[0]["summary"],
                confidence=existing[0]["confidence"],
                skipped_reason="similar_semantic_already_exists",
            )

        # Generalize using LLM
        generated_summary = await self._generalize(cluster.episode_summaries)

        # Register as semantic memory
        semantic_id = await self._search.create({
            "namespace": namespace,
            "memory_type": "semantic",
            "memory_subtype": "compressed",
            "summary": generated_summary,
            "content_text": generated_summary,
            "confidence": round(cluster.avg_confidence * 0.9, 4),  # Per design report
            "source_type": "inference",
            "importance_score": 0.70,   # Semantic memories registered with high importance
            "decay_score": 1.0,
            "is_archived": False,
            "created_at": datetime.now(UTC).isoformat(),
        })

        # Create DERIVES edges in Neo4j
        for episode_id in cluster.episode_ids:
            await self._graph.create_relation_if_not_exists(
                from_id=semantic_id,
                to_id=episode_id,
                relation_type=RelationType.DERIVES,
                properties={
                    "method": "semantic_compression",
                    "confidence": cluster.avg_confidence,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )

        # Decay source episode importance (Design Report: x0.5)
        for episode_id in cluster.episode_ids:
            record = await self._search.get_by_id(episode_id)
            if record:
                new_imp = record["importance_score"] * settings.compression_source_importance_decay
                await self._search.patch(episode_id, {"importance_score": max(0.1, new_imp)})

        logger.info(
            "compression.distilled",
            namespace=namespace,
            semantic_id=semantic_id,
            source_count=len(cluster.episode_ids),
            summary_preview=generated_summary[:60],
        )

        return CompressionResult(
            semantic_memory_id=semantic_id,
            source_episode_ids=cluster.episode_ids,
            generated_summary=generated_summary,
            confidence=cluster.avg_confidence,
        )

    async def _generalize(self, summaries: list[str]) -> str:
        """Extract general knowledge and patterns from episode groups."""
        episodes_text = "\n".join(f"- {s}" for s in summaries)
        prompt = f"""
You are a memory management AI for an AI agent.
From the following group of episodic memories, express the common patterns,
knowledge, and rules as a single semantic memory (a general fact, trend, or knowledge).

Episode group:
{episodes_text}

Requirements:
- Avoid specific dates and proper nouns; express as generalized knowledge
- Summarize concisely in 1-3 sentences
- No JSON or other structures needed, text only

Semantic memory:"""
        return (await self._llm.generate(prompt)).strip()
```

### Semantic Compression Temporal Workflow

File: `backend/src/dse/workflows/definitions/semantic_compression.py`

```python
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))
LONG_TIMEOUT = timedelta(minutes=30)   # Clustering can take time
SHORT_TIMEOUT = timedelta(seconds=60)


@workflow.defn
class SemanticCompressionWorkflow:
    """Weekly episodic -> semantic distillation workflow.

    See Design Report section 5.3.
    Idempotent: running twice on the same namespace does not create duplicate semantics.
    """

    @workflow.run
    async def run(self, namespace: str, lookback_days: int = 30) -> dict:
        workflow.logger.info("compression.started",
                             namespace=namespace, lookback_days=lookback_days)

        # Step 1: Episode retrieval & clustering (heavy processing)
        clusters = await workflow.execute_activity(
            "cluster_episodes_activity",
            args=[namespace, lookback_days],
            start_to_close_timeout=LONG_TIMEOUT,
            retry_policy=RETRY,
        )

        if not clusters:
            return {"status": "no_clusters", "namespace": namespace}

        # Step 2: Distill each cluster in parallel
        distillation_handles = [
            workflow.execute_activity(
                "distill_cluster_activity",
                args=[namespace, cluster],
                start_to_close_timeout=SHORT_TIMEOUT,
                retry_policy=RETRY,
            )
            for cluster in clusters
        ]

        results = []
        for handle in distillation_handles:
            result = await handle
            results.append(result)

        success = [r for r in results if not r.get("skipped_reason")]
        skipped = [r for r in results if r.get("skipped_reason")]

        workflow.logger.info(
            "compression.completed",
            namespace=namespace,
            total_clusters=len(clusters),
            distilled=len(success),
            skipped=len(skipped),
        )

        return {
            "status": "completed",
            "namespace": namespace,
            "total_clusters": len(clusters),
            "distilled": len(success),
            "skipped": len(skipped),
            "results": results,
        }
```

---

## P3-2: Prospective Memory Engine — Implementation Spec

> See Design Report section 6.1.
> Holds "things to do in the future" as memories and automatically fires them
> based on time, event, or condition triggers.

### Prospective Memory Index Fields (Additions)

Add the following fields to `docs/vertex_schema.json`:

```json
{
  "trigger_type":      { "type": "string",  "filterable": true,  "retrievable": true },
  "trigger_at":        { "type": "string",  "filterable": true,  "retrievable": true },
  "trigger_event":     { "type": "string",  "filterable": true,  "retrievable": true },
  "trigger_condition": { "type": "string",  "retrievable": true },
  "recurrence":        { "type": "string",  "filterable": true,  "retrievable": true },
  "is_triggered":      { "type": "boolean", "filterable": true,  "retrievable": true },
  "triggered_at":      { "type": "string",  "filterable": true,  "retrievable": true }
}
```

### Prospective Memory Engine

File: `backend/src/dse/intelligence/prospective.py`

```python
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

import structlog

from dse.config import settings
from dse.services.llm import LLMService
from dse.services.search import SearchService

logger = structlog.get_logger(__name__)


class TriggerType(StrEnum):
    TIME      = "time"       # Fire at specific time
    EVENT     = "event"      # Fire on external event
    CONDITION = "condition"  # Fire when LLM-evaluated condition is met


class RecurrenceType(StrEnum):
    ONCE   = "once"
    DAILY  = "daily"
    WEEKLY = "weekly"


class ProspectiveMemoryEngine:
    """Evaluation and firing engine for Prospective Memory.

    See Design Report section 6.1.
    This engine is called from Temporal Activities.
    Do not call directly from FastAPI routers.
    """

    def __init__(self) -> None:
        self._search = SearchService()
        self._llm = LLMService()

    async def scan_and_fire(self, namespace: str) -> list[dict]:
        """Scan unfired Prospective Memories and evaluate their firing conditions.

        Returns:
            List of fired memories
        """
        # Retrieve all unfired, non-archived prospective memories
        records = await self._search.query(
            namespace=namespace,
            memory_types=["prospective"],
            is_triggered=False,
            is_archived=False,
            page_size=200,
        )

        fired: list[dict] = []
        for record in records:
            should_fire = await self._evaluate(record)
            if should_fire:
                await self._fire(record)
                fired.append(record)

        if fired:
            logger.info("prospective.fired", namespace=namespace, count=len(fired))

        return fired

    async def create(
        self,
        namespace: str,
        summary: str,
        trigger_type: TriggerType,
        *,
        trigger_at: datetime | None = None,
        trigger_event: str | None = None,
        trigger_condition: str | None = None,
        recurrence: RecurrenceType = RecurrenceType.ONCE,
        importance_score: float = 0.80,
    ) -> str:
        """Create a new Prospective memory and return its ID.

        Required fields based on trigger_type:
          TIME      -> trigger_at is required
          EVENT     -> trigger_event is required
          CONDITION -> trigger_condition is required
        """
        if trigger_type == TriggerType.TIME and trigger_at is None:
            raise ValueError("trigger_at is required for TIME trigger")
        if trigger_type == TriggerType.EVENT and not trigger_event:
            raise ValueError("trigger_event is required for EVENT trigger")
        if trigger_type == TriggerType.CONDITION and not trigger_condition:
            raise ValueError("trigger_condition is required for CONDITION trigger")

        record = {
            "namespace": namespace,
            "memory_type": "prospective",
            "summary": summary,
            "content_text": summary,
            "trigger_type": trigger_type.value,
            "trigger_at": trigger_at.isoformat() if trigger_at else None,
            "trigger_event": trigger_event,
            "trigger_condition": trigger_condition,
            "recurrence": recurrence.value,
            "is_triggered": False,
            "triggered_at": None,
            "importance_score": importance_score,
            "confidence": 1.0,   # User-explicitly created plans have max confidence
            "decay_score": 1.0,  # Does not decay until fired (per design report)
            "is_archived": False,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return await self._search.create(record)

    # --- private ---

    async def _evaluate(self, record: dict) -> bool:
        """Evaluate firing condition and return True/False."""
        trigger_type = record.get("trigger_type")

        if trigger_type == TriggerType.TIME:
            trigger_at_str = record.get("trigger_at")
            if not trigger_at_str:
                return False
            trigger_at = datetime.fromisoformat(trigger_at_str)
            return datetime.now(UTC) >= trigger_at

        elif trigger_type == TriggerType.EVENT:
            # Event triggers are fired by directly calling fire() from external sources
            # Always returns False here
            return False

        elif trigger_type == TriggerType.CONDITION:
            return await self._evaluate_condition(record)

        return False

    async def _evaluate_condition(self, record: dict) -> bool:
        """Evaluate condition expression using LLM."""
        condition = record.get("trigger_condition", "")
        if not condition:
            return False

        # Simple rule-based evaluation (to reduce LLM costs)
        # In production, provide external context to the LLM for evaluation
        prompt = f"""
Determine whether the following condition is currently met.
Current time: {datetime.now(UTC).isoformat()}

Condition: {condition}

Return only true if the condition is met, or false if not.
"""
        result = await self._llm.generate(prompt)
        return result.strip().lower() == "true"

    async def _fire(self, record: dict) -> None:
        """Firing process: update record and notify agent."""
        patch: dict = {
            "is_triggered": True,
            "triggered_at": datetime.now(UTC).isoformat(),
        }

        # For recurring triggers, update the next firing time
        recurrence = record.get("recurrence", "once")
        if recurrence != RecurrenceType.ONCE and record.get("trigger_type") == TriggerType.TIME:
            next_trigger = self._next_trigger_at(
                current=datetime.fromisoformat(record["trigger_at"]),
                recurrence=recurrence,
            )
            patch["trigger_at"] = next_trigger.isoformat()
            patch["is_triggered"] = False  # Reset to False for recurring

        await self._search.patch(record["id"], patch)

        logger.info(
            "prospective.memory_fired",
            memory_id=record["id"],
            namespace=record.get("namespace"),
            summary=record.get("summary", "")[:50],
        )

    @staticmethod
    def _next_trigger_at(current: datetime, recurrence: str) -> datetime:
        """Calculate the next firing time."""
        from datetime import timedelta
        if recurrence == RecurrenceType.DAILY:
            return current + timedelta(days=1)
        elif recurrence == RecurrenceType.WEEKLY:
            return current + timedelta(weeks=1)
        return current
```

### Prospective Scan Temporal Workflow

File: `backend/src/dse/workflows/definitions/prospective_scan.py`

```python
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))


@workflow.defn
class ProspectiveScanWorkflow:
    """Runs every minute: Prospective Memory firing check.

    See Design Report section 6.1.
    Launched every minute via Temporal Schedule.
    """

    @workflow.run
    async def run(self, namespace: str) -> dict:
        fired = await workflow.execute_activity(
            "scan_and_fire_prospective_activity",
            args=[namespace],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY,
        )

        if fired:
            # Notify agents about fired memories (publish to Redpanda topic)
            await workflow.execute_activity(
                "publish_prospective_fired_events_activity",
                args=[fired],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RETRY,
            )

        return {"fired_count": len(fired), "namespace": namespace}
```

---

## P3-3: Automatic Relation Discovery — Implementation Spec

> See Design Report section 9.1.
> Runs daily at 04:00 UTC. Cost is controlled via `DISCOVERY_MAX_PAIRS_PER_BATCH`.

### Relation Discovery Engine

File: `backend/src/dse/intelligence/relation_discovery.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from dse.config import settings
from dse.core.enums import RelationType
from dse.services.embedding import EmbeddingService
from dse.services.graph import GraphService
from dse.services.llm import LLMService
from dse.services.search import SearchService

logger = structlog.get_logger(__name__)

# Mapping from LLM classification results to RelationType
RELATION_MAP: dict[str, RelationType | None] = {
    "SUPERSEDED_BY": RelationType.SUPERSEDED_BY,
    "COMPLEMENTS":   RelationType.COMPLEMENTS,
    "CONTRADICTS":   RelationType.CONTRADICTS,
    "DERIVES":       RelationType.DERIVES,
    "CAUSES":        RelationType.CAUSES,
    "REFERENCES":    RelationType.REFERENCES,
    "NONE":          None,
}


@dataclass
class DiscoveryResult:
    from_id: str
    to_id: str
    relation_type: RelationType | None
    confidence: float
    reason: str
    registered: bool = False


class RelationDiscoveryEngine:
    """Autonomously discovers latent relationships between existing memories
    and registers them in the graph.

    See Design Report section 9.1.
    Narrows candidate pairs using ANN search before classifying with LLM,
    significantly reducing cost compared to running LLM on all pairs.
    """

    def __init__(self) -> None:
        self._search = SearchService()
        self._graph = GraphService()
        self._llm = LLMService()

    async def run(self, namespace: str) -> list[DiscoveryResult]:
        """Execute relation discovery batch."""
        logger.info("discovery.started", namespace=namespace)

        # Step 1: Extract candidate similar pairs (only those without existing relations)
        candidate_pairs = await self._find_candidate_pairs(namespace)
        if not candidate_pairs:
            logger.info("discovery.no_candidates", namespace=namespace)
            return []

        # Step 2: Classify relation type via LLM (with cost cap)
        results: list[DiscoveryResult] = []
        for pair in candidate_pairs[: settings.discovery_max_pairs_per_batch]:
            result = await self._classify_pair(pair["id_a"], pair["id_b"],
                                               pair["summary_a"], pair["summary_b"])
            results.append(result)

            # Register meaningful relations in the graph
            if (result.relation_type is not None
                    and result.confidence >= settings.discovery_min_llm_confidence):
                await self._graph.create_relation(
                    from_id=result.from_id,
                    to_id=result.to_id,
                    relation_type=result.relation_type,
                    properties={
                        "confidence": result.confidence,
                        "discovered_by": "auto",
                        "method": "embedding_similarity+llm",
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                )
                result.registered = True

        registered = [r for r in results if r.registered]
        logger.info(
            "discovery.completed",
            namespace=namespace,
            checked=len(results),
            registered=len(registered),
        )
        return results

    async def _find_candidate_pairs(self, namespace: str) -> list[dict]:
        """Extract similar pairs via ANN search, returning only those without existing edges."""
        # Retrieve memories within namespace
        memories = await self._search.query(
            namespace=namespace,
            is_archived=False,
            page_size=1000,
        )

        pairs: list[dict] = []
        checked: set[tuple[str, str]] = set()

        for mem in memories:
            if not mem.get("embedding"):
                continue

            # ANN search: retrieve similar memories
            similar = await self._search.vector_search(
                embedding=mem["embedding"],
                namespace=namespace,
                top_k=10,
                min_score=settings.discovery_similarity_threshold,
                exclude_ids=[mem["id"]],
            )

            for s in similar:
                pair_key = tuple(sorted([mem["id"], s["id"]]))
                if pair_key in checked:
                    continue
                checked.add(pair_key)

                # Skip if relation already exists
                has_relation = await self._graph.any_relation_exists(mem["id"], s["id"])
                if not has_relation:
                    pairs.append({
                        "id_a": mem["id"],
                        "id_b": s["id"],
                        "summary_a": mem.get("summary", ""),
                        "summary_b": s.get("summary", ""),
                    })

        return pairs

    async def _classify_pair(
        self,
        id_a: str,
        id_b: str,
        summary_a: str,
        summary_b: str,
    ) -> DiscoveryResult:
        """Classify the relationship type between two memories using LLM."""
        prompt = f"""
Classify the relationship between the following two memories.

Memory A: {summary_a}
Memory B: {summary_b}

Relationship types (A -> B direction):
- SUPERSEDED_BY: A updates/replaces B's content
- COMPLEMENTS: A and B together form more complete information
- CONTRADICTS: A and B contradict each other (bidirectional)
- DERIVES: B was inferred/summarized from A
- CAUSES: A caused B
- REFERENCES: A references/cites B
- NONE: No meaningful relationship

Return ONLY the following JSON:
{{"relation_type": "...", "confidence": 0.0-1.0, "reason": "reason in 30 chars or less"}}
"""
        result = await self._llm.generate_json(prompt)
        rel_type = RELATION_MAP.get(result.get("relation_type", "NONE"))

        return DiscoveryResult(
            from_id=id_a,
            to_id=id_b,
            relation_type=rel_type,
            confidence=float(result.get("confidence", 0.0)),
            reason=result.get("reason", ""),
        )
```

---

## P3-4: Temporal Reasoning (Allen's Interval Algebra) — Implementation Spec

> See Design Report section 6.3.
> Classifies temporal relationships between memories using 13 types of time relations,
> and automatically assigns `TEMPORALLY_PRECEDES` edges in the graph.

### Allen's Interval Algebra Implementation

File: `backend/src/dse/intelligence/temporal_reasoning.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import structlog

from dse.config import settings
from dse.core.enums import RelationType
from dse.services.graph import GraphService
from dse.services.search import SearchService

logger = structlog.get_logger(__name__)


class AllenRelation(StrEnum):
    """Allen's Interval Algebra 13 relations.

    See Design Report section 6.3.
    """
    BEFORE           = "BEFORE"            # A ends before B starts
    MEETS            = "MEETS"             # A end = B start
    OVERLAPS         = "OVERLAPS"          # A start < B start < A end < B end
    STARTS           = "STARTS"            # A start = B start, A end < B end
    DURING           = "DURING"            # B start < A start, A end < B end
    FINISHES         = "FINISHES"          # A end = B end, B start < A start
    EQUALS           = "EQUALS"            # A start = B start, A end = B end
    # Inverse relations
    AFTER            = "AFTER"
    MET_BY           = "MET_BY"
    OVERLAPPED_BY    = "OVERLAPPED_BY"
    STARTED_BY       = "STARTED_BY"
    CONTAINS         = "CONTAINS"
    FINISHED_BY      = "FINISHED_BY"


@dataclass
class TimeInterval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            # If end is before start (point event), set them equal
            self.end = self.start


class TemporalReasoningEngine:
    """Temporal reasoning engine based on Allen's Interval Algebra.

    Automatically assigns TEMPORALLY_PRECEDES edges and provides
    "when was this information from" context during search.
    See Design Report section 6.3.
    """

    def __init__(self) -> None:
        self._search = SearchService()
        self._graph = GraphService()

    def classify(self, a: TimeInterval, b: TimeInterval) -> AllenRelation:
        """Classify the Allen relation between two time intervals."""
        if a.end < b.start:
            return AllenRelation.BEFORE
        if a.end == b.start:
            return AllenRelation.MEETS
        if a.start < b.start and a.end < b.end and a.end > b.start:
            return AllenRelation.OVERLAPS
        if a.start == b.start and a.end < b.end:
            return AllenRelation.STARTS
        if a.start > b.start and a.end < b.end:
            return AllenRelation.DURING
        if a.start > b.start and a.end == b.end:
            return AllenRelation.FINISHES
        if a.start == b.start and a.end == b.end:
            return AllenRelation.EQUALS
        if a.start > b.end:
            return AllenRelation.AFTER
        if a.start == b.end:
            return AllenRelation.MET_BY
        if a.start > b.start and a.end > b.end and a.start < b.end:
            return AllenRelation.OVERLAPPED_BY
        if a.start == b.start and a.end > b.end:
            return AllenRelation.STARTED_BY
        if a.start < b.start and a.end > b.end:
            return AllenRelation.CONTAINS
        if a.start < b.start and a.end == b.end:
            return AllenRelation.FINISHED_BY
        # Fallback
        return AllenRelation.BEFORE

    async def build_temporal_edges(self, namespace: str) -> int:
        """Assign TEMPORALLY_PRECEDES edges between memories in a namespace.

        Only assigns edges for BEFORE / MEETS pairs.
        Skips pairs outside the time window for cost reduction.

        Returns:
            Number of edges created
        """
        window = timedelta(days=settings.temporal_window_days)
        memories = await self._search.query(
            namespace=namespace,
            is_archived=False,
            page_size=500,
        )

        created_count = 0
        for i, mem_a in enumerate(memories):
            created_at_a = datetime.fromisoformat(mem_a["created_at"])
            for mem_b in memories[i + 1:]:
                created_at_b = datetime.fromisoformat(mem_b["created_at"])

                # Skip if outside time window
                if abs((created_at_a - created_at_b).total_seconds()) > window.total_seconds():
                    continue

                # Treat as point events (use created_at if updated_at is absent)
                updated_at_a = datetime.fromisoformat(
                    mem_a.get("updated_at") or mem_a["created_at"]
                )
                updated_at_b = datetime.fromisoformat(
                    mem_b.get("updated_at") or mem_b["created_at"]
                )

                interval_a = TimeInterval(start=created_at_a, end=updated_at_a)
                interval_b = TimeInterval(start=created_at_b, end=updated_at_b)
                relation = self.classify(interval_a, interval_b)

                # BEFORE / MEETS -> assign TEMPORALLY_PRECEDES edge
                if relation in (AllenRelation.BEFORE, AllenRelation.MEETS):
                    exists = await self._graph.any_relation_exists(
                        mem_a["id"], mem_b["id"]
                    )
                    if not exists:
                        await self._graph.create_relation(
                            from_id=mem_a["id"],
                            to_id=mem_b["id"],
                            relation_type=RelationType.TEMPORALLY_PRECEDES,
                            properties={
                                "allen_relation": relation.value,
                                "interval_ms": int(
                                    (created_at_b - created_at_a).total_seconds() * 1000
                                ),
                                "created_at": datetime.now(UTC).isoformat(),
                            },
                        )
                        created_count += 1

        logger.info(
            "temporal.edges_created",
            namespace=namespace,
            created=created_count,
        )
        return created_count

    async def find_temporal_context(
        self,
        memory_id: str,
        namespace: str,
        window: timedelta | None = None,
    ) -> list[dict]:
        """Retrieve related memories positioned before/after the target memory.

        Used in Stage 3 Retrieval to enrich "when was this information from" context.
        """
        record = await self._search.get_by_id(memory_id)
        if record is None:
            return []

        win = window or timedelta(days=settings.temporal_window_days)
        created_at = datetime.fromisoformat(record["created_at"])

        neighbors = await self._search.query(
            namespace=namespace,
            created_after=(created_at - win).isoformat(),
            created_before=(created_at + win).isoformat(),
            is_archived=False,
            page_size=20,
        )

        # Attach Allen relation and return
        result = []
        for n in neighbors:
            if n["id"] == memory_id:
                continue
            n_created = datetime.fromisoformat(n["created_at"])
            n_updated = datetime.fromisoformat(n.get("updated_at") or n["created_at"])
            r_created = datetime.fromisoformat(record["created_at"])
            r_updated = datetime.fromisoformat(record.get("updated_at") or record["created_at"])

            allen = self.classify(
                TimeInterval(r_created, r_updated),
                TimeInterval(n_created, n_updated),
            )
            result.append({**n, "allen_relation": allen.value})

        return result
```

---

## P3-6: Human-in-the-Loop Curation UI — Implementation Spec

> See Design Report section 5.4.
> Interface for users to directly manage their own memories.

### Curation API Endpoints

```
# --- Memory Management ---
GET    /v1/curation/memories
       ?namespace={ns}
       &memory_type={type}
       &min_importance={0.0-1.0}
       &sort_by={importance|created_at|decay_score}
       &page={n}
       &page_size={20-100}
                                             # Memory list (with pagination)

PUT    /v1/curation/memories/{id}
       Body: {summary, importance_score, memory_type, tags, expires_at}
                                             # Edit memory content/metadata

DELETE /v1/curation/memories/{id}?cascade=true
                                             # Delete memory (cascade=true deletes derivatives)

POST   /v1/curation/memories/{id}/pin
       Body: {pinned: true|false}            # "Remember this" -> importance=1.0, remove expires_at

POST   /v1/curation/memories/{id}/forget
                                             # "Forget this" -> bulk delete target and DERIVES derivatives

# --- Semantic Compression ---
POST   /v1/curation/compress
       Body: {namespace, lookback_days}      # Manually trigger Semantic Compression

GET    /v1/curation/compress/history?namespace={ns}
                                             # Distillation history list

# --- Prospective Memory ---
GET    /v1/curation/prospective?namespace={ns}&status={pending|triggered|all}

POST   /v1/curation/prospective
       Body: {summary, trigger_type, trigger_at?, trigger_condition?, recurrence}
                                             # Create Prospective memory

DELETE /v1/curation/prospective/{id}         # Delete scheduled memory

# --- Statistics/Monitoring ---
GET    /v1/curation/stats?namespace={ns}
                                             # Memory statistics (type distribution, decay, compression history)
```

### Curation Dashboard (Main Page)

File: `frontend/src/app/curation/page.tsx`

```typescript
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@radix-ui/react-tabs";
import { MemoryBrowser } from "./components/MemoryBrowser";
import { CompressionPanel } from "./components/CompressionPanel";
import { ProspectiveList } from "./components/ProspectiveList";
import { ImportanceChart } from "./components/ImportanceChart";

interface Props {
  searchParams: { namespace?: string };
}

export default function CurationPage({ searchParams }: Props) {
  const namespace = searchParams.namespace ?? "default";

  return (
    <div className="container mx-auto px-4 py-6">
      <header className="mb-6">
        <h1 className="text-2xl font-medium text-slate-900 dark:text-slate-100">
          Memory Management
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Namespace: <code className="font-mono text-xs">{namespace}</code>
        </p>
      </header>

      <Tabs defaultValue="browse">
        <TabsList className="mb-6 flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
          {[
            { value: "browse",      label: "Memory List" },
            { value: "compression", label: "Semantic Compression" },
            { value: "prospective", label: "Prospective Memory" },
            { value: "analytics",   label: "Analytics" },
          ].map(({ value, label }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="flex-1 rounded-md px-3 py-1.5 text-sm font-medium
                         text-slate-600 transition-colors
                         data-[state=active]:bg-white data-[state=active]:text-slate-900
                         dark:text-slate-400 dark:data-[state=active]:bg-slate-700
                         dark:data-[state=active]:text-slate-100"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="browse">
          <MemoryBrowser namespace={namespace} />
        </TabsContent>

        <TabsContent value="compression">
          <CompressionPanel namespace={namespace} />
        </TabsContent>

        <TabsContent value="prospective">
          <ProspectiveList namespace={namespace} />
        </TabsContent>

        <TabsContent value="analytics">
          <ImportanceChart namespace={namespace} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

### Memory Browser (List, Search, Pin, Delete)

File: `frontend/src/app/curation/components/MemoryBrowser.tsx`

```typescript
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchCurationMemories, pinMemory, forgetMemory } from "@/lib/api/curation";

const MEMORY_TYPE_COLORS: Record<string, string> = {
  semantic:    "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  episodic:    "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  procedural:  "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  prospective: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
};

interface Props {
  namespace: string;
}

export function MemoryBrowser({ namespace }: Props) {
  const qc = useQueryClient();
  const [filter, setFilter] = useState({ memoryType: "all", sortBy: "importance" });

  const { data, isLoading } = useQuery({
    queryKey: ["curation-memories", namespace, filter],
    queryFn: () => fetchCurationMemories({ namespace, ...filter }),
  });

  const pinMutation = useMutation({
    mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) =>
      pinMemory(id, pinned),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["curation-memories"] }),
  });

  const forgetMutation = useMutation({
    mutationFn: (id: string) => forgetMemory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["curation-memories"] }),
  });

  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading...</p>;
  }

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex flex-wrap gap-3">
        <select
          value={filter.memoryType}
          onChange={(e) => setFilter((f) => ({ ...f, memoryType: e.target.value }))}
          className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm
                     dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="all">All Types</option>
          <option value="semantic">Semantic</option>
          <option value="episodic">Episodic</option>
          <option value="procedural">Procedural</option>
          <option value="prospective">Prospective</option>
        </select>

        <select
          value={filter.sortBy}
          onChange={(e) => setFilter((f) => ({ ...f, sortBy: e.target.value }))}
          className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm
                     dark:border-slate-700 dark:bg-slate-900"
        >
          <option value="importance">By Importance</option>
          <option value="created_at">By Created Date</option>
          <option value="decay_score">By Decay Score</option>
        </select>
      </div>

      {/* Memory List */}
      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {(data?.memories ?? []).map((m: any) => (
          <li key={m.id} className="flex items-start gap-4 py-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium
                  ${MEMORY_TYPE_COLORS[m.memory_type] ?? "bg-slate-100 text-slate-600"}`}>
                  {m.memory_type}
                </span>
                <span className="text-xs text-slate-400">{m.id.slice(0, 8)}...</span>
              </div>
              <p className="text-sm text-slate-800 dark:text-slate-200 line-clamp-2">
                {m.summary}
              </p>
              <div className="mt-2 flex items-center gap-4 text-xs text-slate-400">
                <span>Importance {(m.importance_score * 100).toFixed(0)}%</span>
                <span>Decay {(m.decay_score * 100).toFixed(0)}%</span>
                <span>Confidence {(m.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>

            <div className="flex shrink-0 gap-2">
              <button
                onClick={() => pinMutation.mutate({ id: m.id, pinned: true })}
                title="Remember this"
                className="rounded-md bg-amber-50 px-2.5 py-1 text-xs text-amber-700
                           hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300"
              >
                Pin
              </button>
              <button
                onClick={() => {
                  if (confirm("Delete this memory and its derivatives?")) {
                    forgetMutation.mutate(m.id);
                  }
                }}
                title="Forget this memory"
                className="rounded-md bg-red-50 px-2.5 py-1 text-xs text-red-700
                           hover:bg-red-100 dark:bg-red-900 dark:text-red-300"
              >
                Forget
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Temporal Task Queues and Schedules (Phase 3 Additions)

| Task Queue | Workflow | Schedule | Description |
|-----------|---------|---------|-------------|
| `dse-main` | `ProspectiveScanWorkflow` | Every minute | Prospective memory firing check |
| `dse-maintenance` | `SemanticCompressionWorkflow` | Weekly Sunday 03:00 UTC | Episodic -> semantic distillation |
| `dse-discovery` | `RelationDiscoveryWorkflow` | Daily 04:00 UTC | Automatic relation discovery |
| `dse-discovery` | `TemporalEdgeBuildWorkflow` | Daily 04:30 UTC | TEMPORALLY_PRECEDES edge assignment |
| `dse-maintenance` | `ImportanceBatchUpdateWorkflow` | Daily 02:30 UTC | Batch re-evaluation of all memory importance |

### Temporal Schedule Registration Script

File: `backend/src/dse/workflows/register_schedules.py`

```python
"""
Script to register Temporal Schedules.
Run with `make register-schedules` during initial setup.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleIntervalSpec, ScheduleSpec
from temporalio.common import RetryPolicy

from dse.config import settings

NAMESPACE_LIST = ["default"]   # Change according to actual namespace list


async def register_all(client: Client) -> None:
    for namespace in NAMESPACE_LIST:
        # --- Prospective Scan: Every minute ---
        await _upsert_schedule(
            client,
            schedule_id=f"prospective-scan-{namespace}",
            workflow="ProspectiveScanWorkflow",
            args=[namespace],
            task_queue="dse-main",
            interval=timedelta(minutes=1),
        )

        # --- Semantic Compression: Weekly on Sunday ---
        await _upsert_schedule(
            client,
            schedule_id=f"semantic-compression-{namespace}",
            workflow="SemanticCompressionWorkflow",
            args=[namespace, 30],
            task_queue="dse-maintenance",
            interval=timedelta(weeks=1),
        )

        # --- Relation Discovery: Daily ---
        await _upsert_schedule(
            client,
            schedule_id=f"relation-discovery-{namespace}",
            workflow="RelationDiscoveryWorkflow",
            args=[namespace],
            task_queue="dse-discovery",
            interval=timedelta(days=1),
        )

        # --- Temporal Edge Build: Daily ---
        await _upsert_schedule(
            client,
            schedule_id=f"temporal-edges-{namespace}",
            workflow="TemporalEdgeBuildWorkflow",
            args=[namespace],
            task_queue="dse-discovery",
            interval=timedelta(days=1),
        )


async def _upsert_schedule(
    client: Client,
    schedule_id: str,
    workflow: str,
    args: list,
    task_queue: str,
    interval: timedelta,
) -> None:
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.describe()
        print(f"[skip] schedule already exists: {schedule_id}")
    except Exception:
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow,
                    args,
                    id=f"{schedule_id}-run",
                    task_queue=task_queue,
                    retry_policy=RetryPolicy(maximum_attempts=3),
                ),
                spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=interval)]),
            ),
        )
        print(f"[created] schedule: {schedule_id}")


if __name__ == "__main__":
    async def main() -> None:
        client = await Client.connect(settings.temporal_host)
        await register_all(client)
        await client.close()

    asyncio.run(main())
```

---

## Test Requirements (Phase 3)

### Unit Tests (Required)

```
tests/unit/
├── test_importance_estimator.py
│   ├── test_baseline_score                          # Default score is 0.5
│   ├── test_user_marked_adds_max_boost              # user_explicitly_marked = +0.50
│   ├── test_failed_action_reduces_score             # led_to_failed_action = -0.10
│   ├── test_procedural_minimum_score                # procedural minimum is 0.60
│   ├── test_clamping_never_exceeds_max              # Never exceeds 1.0
│   └── test_reinforce_decay_recovery                # utility_score * recovery_rate
│
├── test_semantic_compression.py
│   ├── test_skip_when_too_few_episodes              # Skip when below min_cluster_size
│   ├── test_skip_when_low_confidence                # Skip when avg_confidence too low
│   ├── test_idempotency_existing_semantic           # No duplicate creation when similar semantic exists
│   ├── test_derives_edges_created                   # DERIVES edges created for each source
│   ├── test_source_importance_decayed               # Source episode importance is decayed
│   └── test_generated_summary_is_generalized        # No specific proper nouns in output
│
├── test_prospective_memory.py
│   ├── test_time_trigger_fires_when_past            # Fires when trigger_at is in the past
│   ├── test_time_trigger_not_fires_when_future      # Does not fire when trigger_at is future
│   ├── test_recurrence_resets_trigger_at            # Daily recurrence updates trigger_at
│   ├── test_once_trigger_archived_after_fire        # Once trigger sets is_triggered=True after fire
│   ├── test_create_validates_required_fields        # Required fields enforced per trigger_type
│   └── test_condition_trigger_llm_evaluation        # Condition trigger calls LLM
│
├── test_relation_discovery.py
│   ├── test_skip_existing_relations                 # Existing edges are not recreated
│   ├── test_none_relation_not_registered            # NONE is not registered
│   ├── test_max_pairs_per_batch_respected           # DISCOVERY_MAX_PAIRS_PER_BATCH not exceeded
│   └── test_low_confidence_not_registered           # Below confidence threshold not registered
│
├── test_allen_interval_algebra.py
│   ├── test_before                                  # A end < B start
│   ├── test_meets                                   # A end = B start
│   ├── test_overlaps
│   ├── test_during
│   ├── test_equals
│   ├── test_all_13_relations_covered               # All 13 relation patterns covered
│   └── test_point_events                           # Edge case where start == end
│
└── test_compression_workflow.py
    └── test_workflow_idempotency                   # No duplicates after running twice on same namespace
```

### Integration Tests (Required)

```
tests/integration/
├── test_compression_pipeline.py
│   └── test_end_to_end_compression               # Real Search Index + Neo4j + LLM mock
│
├── test_prospective_scan.py
│   └── test_scan_fires_overdue_memories          # Real Search Index (no local Docker needed)
│
└── test_relation_discovery_pipeline.py
    └── test_pairs_registered_in_neo4j            # Real Neo4j + LLM mock
```

---

## Phase 3 Completion Checklist

Phase 3 is complete when all of the following are satisfied:

- [ ] `make test-unit` passes 100%
- [ ] `make test-int` passes 100%
- [ ] `make register-schedules` registers 4 types of Temporal Schedules
- [ ] Schedules are visible in Temporal UI (http://localhost:8080)
- [ ] Semantic Compression workflow completes successfully on manual trigger
- [ ] Semantic memory is generated from 5+ episodic memories
- [ ] DERIVES edges are created in Neo4j for the generated semantic memory
- [ ] Prospective memory created with TIME trigger fires successfully
- [ ] ProspectiveScanWorkflow runs every minute in Temporal
- [ ] RelationDiscoveryWorkflow adds new relation edges to Neo4j
- [ ] Allen's Interval assigns TEMPORALLY_PRECEDES edges
- [ ] `/v1/curation/memories` works with importance / memory_type filters
- [ ] Frontend `/curation` displays all 4 tabs
- [ ] "Pin" button sets importance_score = 1.0
- [ ] "Forget" button deletes target and derived memories
- [ ] `make lint` passes with no errors (mypy strict + ruff + tsc)
- [ ] `make dev` starts all local services

---

## Common Implementation Mistakes (Phase 3 Specific)

**Semantic Compression**

1. **Setting HDBSCAN `metric` to `cosine` is slow for sparse high-dimensional vectors**
   -> Gemini Embeddings are L2-normalized, so use `metric="euclidean"`.
   Euclidean distance on L2-normalized vectors is approximately cosine distance.

2. **Forgetting to pre-filter by `importance_score` before distillation**
   -> Distilling extremely low-importance episodes produces low-quality semantic memories.
   Add a `min_importance_score >= 0.3` filter.

3. **Skipping the idempotency check (existing semantic memory verification)**
   -> Re-running the same batch creates massive duplicate semantic memories.
   Always verify with `vector_search` for similar existing semantic memories.

**Prospective Memory**

4. **Forgetting to patch `is_triggered = True` after firing**
   -> The same memory "fires" repeatedly on every minute scan.
   Update `is_triggered = True` at the start of `_fire()`.

5. **Incorrect ONCE recurrence judgment**
   -> If you update `trigger_at` for a `recurrence = "once"` memory after firing,
   it will re-fire. Always check the `recurrence != ONCE` condition.

**Relation Discovery**

6. **Forgetting the direction check in `any_relation_exists()`**
   -> A->B DERIVES edge is different from B->A COMPLEMENTS edge.
   The graph service's `any_relation_exists(a, b)` should check **bidirectionally**.

7. **Setting the LLM classification prompt's `relation_type` to SUPERSEDES**
   -> The index field name is `SUPERSEDED_BY` (past tense).
   Use `RELATION_MAP` to ensure prompts and Enum values match exactly.

**Allen's Interval Algebra**

8. **Point events (created_at == updated_at) create zero-width intervals**
   -> Handle with fallback in `TimeInterval.__post_init__` (already implemented).
   Zero-width intervals become `EQUALS` — be careful not to misjudge as `BEFORE`.

9. **Comparing all pairs becomes O(n^2) and slows down with many memories**
   -> Narrow with `temporal_window_days` time window.
   Skip pairs outside the window with `abs(created_at_a - created_at_b) > window` (already implemented).

**Temporal**

10. **Executing clustering (heavy processing) directly in SemanticCompressionWorkflow**
    -> Always delegate to an Activity. Keep Workflow code as a thin orchestrator.

11. **Too many parallel Activities (`distill_cluster_activity`) hitting Gemini API rate limits**
    -> Limit parallelism using a config value like `DISCOVERY_MAX_PAIRS_PER_BATCH`.
    Alternatively, control concurrency with `asyncio.Semaphore`.

---

## Reference Documentation

- [DSE Design Report](./docs/DSE_Design_Report.md) <- **Always reference during Phase 3 implementation**
- [Vertex AI Search](https://docs.cloud.google.com/generative-ai-app-builder/docs)
- [Gemini API Models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [Google ADK](https://google.github.io/adk-docs/)
- [Temporal Workflow + Schedule](https://docs.temporal.io/workflows)
- [HDBSCAN Documentation](https://hdbscan.readthedocs.io/)
- [Allen's Interval Algebra (Wikipedia)](https://en.wikipedia.org/wiki/Allen%27s_interval_algebra)
- [React Flow](https://reactflow.dev/)
