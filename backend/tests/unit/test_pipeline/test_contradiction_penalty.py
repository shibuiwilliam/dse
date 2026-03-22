from __future__ import annotations

from datetime import UTC, datetime

from dse.core.enums import CascadeStage, VerificationStatus
from dse.core.models import MemoryRecord
from dse.pipeline.preprocessing import SearchQuery
from dse.pipeline.ranking import compute_final_score


def _make_query() -> SearchQuery:
    return SearchQuery(
        text_queries=["test"],
        embedding=[],
        filters={},
        memory_types=[],
        cascade_stage=CascadeStage.PRECISION,
    )


def _make_record(
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    superseded_by: str | None = None,
) -> MemoryRecord:
    return MemoryRecord(
        namespace="test",
        confidence=0.8,
        decay_score=0.9,
        verification_status=verification_status,
        superseded_by=superseded_by,
        created_at=datetime.now(UTC),
    )


class TestContradictionPenalty:
    def test_contradicted_memory_penalized(self) -> None:
        query = _make_query()
        normal = _make_record()
        contradicted = _make_record(verification_status=VerificationStatus.CONTRADICTED)
        score_normal = compute_final_score(normal, 0.5, query)
        score_contradicted = compute_final_score(contradicted, 0.5, query)
        assert score_contradicted < score_normal

    def test_pending_memory_penalized(self) -> None:
        query = _make_query()
        normal = _make_record()
        pending = _make_record(verification_status=VerificationStatus.PENDING)
        score_normal = compute_final_score(normal, 0.5, query)
        score_pending = compute_final_score(pending, 0.5, query)
        assert score_pending < score_normal

    def test_verified_no_penalty(self) -> None:
        query = _make_query()
        now = datetime.now(UTC)
        normal = _make_record()
        normal.created_at = now
        verified = _make_record(verification_status=VerificationStatus.VERIFIED)
        verified.created_at = now
        score_normal = compute_final_score(normal, 0.5, query, now=now)
        score_verified = compute_final_score(verified, 0.5, query, now=now)
        assert abs(score_verified - score_normal) < 1e-10

    def test_superseded_and_contradicted_stacks(self) -> None:
        query = _make_query()
        normal = _make_record()
        both = _make_record(
            verification_status=VerificationStatus.CONTRADICTED,
            superseded_by="other",
        )
        score_normal = compute_final_score(normal, 0.5, query)
        score_both = compute_final_score(both, 0.5, query)
        # Both penalties multiply: 0.1 * 0.3 = 0.03
        assert score_both < score_normal * 0.05
