from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dse.core.enums import CascadeStage
from dse.core.models import MemoryRecord, SearchResult
from dse.pipeline.preprocessing import SearchQuery
from dse.pipeline.ranking import (
    compute_final_score,
    reciprocal_rank_fusion,
    rerank,
    temporal_recency_score,
)


def _make_record(
    id: str = "test-1",  # noqa: A002
    namespace: str = "test",
    confidence: float = 0.8,
    decay_score: float = 0.9,
    access_count_30d: int = 5,
    superseded_by: str | None = None,
    created_at: datetime | None = None,
) -> MemoryRecord:
    return MemoryRecord(
        id=id,
        namespace=namespace,
        confidence=confidence,
        decay_score=decay_score,
        access_count_30d=access_count_30d,
        superseded_by=superseded_by,
        created_at=created_at or datetime.now(UTC),
    )


def _make_result(record: MemoryRecord, source: str = "bm25") -> SearchResult:
    return SearchResult(record=record, score=0.0, match_source=source)


def _make_query() -> SearchQuery:
    return SearchQuery(
        text_queries=["test"],
        embedding=[],
        filters={},
        memory_types=[],
        cascade_stage=CascadeStage.PRECISION,
    )


class TestRRF:
    def test_single_list(self) -> None:
        r1 = _make_result(_make_record(id="a"))
        r2 = _make_result(_make_record(id="b"))
        scores = reciprocal_rank_fusion([r1, r2])
        assert scores["a"] > scores["b"]

    def test_two_lists_boost(self) -> None:
        r_a = _make_result(_make_record(id="a"))
        r_b = _make_result(_make_record(id="b"))
        # "a" appears in both lists
        scores = reciprocal_rank_fusion([r_a, r_b], [r_a])
        assert scores["a"] > scores["b"]


class TestTemporalRecency:
    def test_recent_is_higher(self) -> None:
        now = datetime.now(UTC)
        recent = temporal_recency_score(now - timedelta(hours=1), now)
        old = temporal_recency_score(now - timedelta(days=30), now)
        assert recent > old

    def test_returns_between_0_and_1(self) -> None:
        now = datetime.now(UTC)
        score = temporal_recency_score(now - timedelta(days=365), now)
        assert 0.0 < score <= 1.0


class TestFinalScore:
    def test_superseded_penalty(self) -> None:
        query = _make_query()
        normal = _make_record(id="normal")
        superseded = _make_record(id="superseded", superseded_by="other")
        score_normal = compute_final_score(normal, 0.5, query)
        score_superseded = compute_final_score(superseded, 0.5, query)
        assert score_superseded < score_normal * 0.2

    def test_higher_confidence_higher_score(self) -> None:
        query = _make_query()
        low = _make_record(confidence=0.3)
        high = _make_record(confidence=0.9)
        assert compute_final_score(high, 0.5, query) > compute_final_score(low, 0.5, query)

    def test_higher_decay_higher_score(self) -> None:
        query = _make_query()
        low = _make_record(decay_score=0.2)
        high = _make_record(decay_score=0.9)
        assert compute_final_score(high, 0.5, query) > compute_final_score(low, 0.5, query)


class TestRerank:
    def test_returns_top_k(self) -> None:
        bm25 = [_make_result(_make_record(id=f"bm25-{i}"), "bm25") for i in range(10)]
        vector = [_make_result(_make_record(id=f"vec-{i}"), "vector") for i in range(10)]
        query = _make_query()
        query.top_k = 5
        results = rerank(bm25, vector, query)
        assert len(results) <= 5

    def test_deduplicates(self) -> None:
        record = _make_record(id="shared")
        bm25 = [_make_result(record, "bm25")]
        vector = [_make_result(record, "vector")]
        query = _make_query()
        results = rerank(bm25, vector, query)
        assert len(results) == 1
