from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dse.core.enums import DecayTier, MemoryType
from dse.core.models import MemoryRecord


class TestMemoryRecord:
    def test_default_creation(self, namespace: str) -> None:
        record = MemoryRecord(namespace=namespace)
        assert record.id
        assert record.namespace == namespace
        assert record.memory_type == MemoryType.EPISODIC
        assert record.confidence == 0.5
        assert record.decay_score == 1.0
        assert record.is_archived is False

    def test_decay_tier_active(self, namespace: str) -> None:
        record = MemoryRecord(namespace=namespace, decay_score=0.8)
        assert record.decay_tier == DecayTier.ACTIVE

    def test_decay_tier_warm(self, namespace: str) -> None:
        record = MemoryRecord(namespace=namespace, decay_score=0.3)
        assert record.decay_tier == DecayTier.WARM

    def test_decay_tier_archive(self, namespace: str) -> None:
        record = MemoryRecord(namespace=namespace, decay_score=0.1)
        assert record.decay_tier == DecayTier.ARCHIVE

    def test_compute_decay_episodic(self, namespace: str) -> None:
        now = datetime.now(UTC)
        record = MemoryRecord(
            namespace=namespace,
            memory_type=MemoryType.EPISODIC,
            created_at=now - timedelta(days=30),
            access_count_30d=0,
            importance_score=0.5,
        )
        decay = record.compute_decay_score(now)
        assert 0.0 < decay < 1.0
        # Episodic decays faster
        assert decay < 0.5

    def test_compute_decay_semantic_slower(self, namespace: str) -> None:
        now = datetime.now(UTC)
        base_kwargs = dict(
            namespace=namespace,
            created_at=now - timedelta(days=30),
            access_count_30d=0,
            importance_score=0.5,
        )
        episodic = MemoryRecord(memory_type=MemoryType.EPISODIC, **base_kwargs)
        semantic = MemoryRecord(memory_type=MemoryType.SEMANTIC, **base_kwargs)
        assert semantic.compute_decay_score(now) > episodic.compute_decay_score(now)

    def test_compute_decay_prospective_no_decay(self, namespace: str) -> None:
        now = datetime.now(UTC)
        record = MemoryRecord(
            namespace=namespace,
            memory_type=MemoryType.PROSPECTIVE,
            created_at=now - timedelta(days=365),
            access_count_30d=0,
            importance_score=0.5,
        )
        decay = record.compute_decay_score(now)
        # Prospective memories don't decay
        assert decay > 0.7

    def test_access_frequency_boosts_decay(self, namespace: str) -> None:
        now = datetime.now(UTC)
        base_kwargs = dict(
            namespace=namespace,
            memory_type=MemoryType.EPISODIC,
            created_at=now - timedelta(days=30),
            importance_score=0.5,
        )
        low_access = MemoryRecord(access_count_30d=0, **base_kwargs)
        high_access = MemoryRecord(access_count_30d=20, **base_kwargs)
        assert high_access.compute_decay_score(now) > low_access.compute_decay_score(now)

    def test_importance_boosts_decay(self, namespace: str) -> None:
        now = datetime.now(UTC)
        base_kwargs = dict(
            namespace=namespace,
            memory_type=MemoryType.EPISODIC,
            created_at=now - timedelta(days=30),
            access_count_30d=0,
        )
        low_imp = MemoryRecord(importance_score=0.1, **base_kwargs)
        high_imp = MemoryRecord(importance_score=0.9, **base_kwargs)
        assert high_imp.compute_decay_score(now) > low_imp.compute_decay_score(now)

    def test_to_index_dict(self, namespace: str) -> None:
        record = MemoryRecord(
            namespace=namespace,
            summary="Test summary",
            embedding=[0.1, 0.2],
        )
        data = record.to_index_dict()
        assert "embedding" not in data
        assert "summary_embedding" not in data
        assert data["namespace"] == namespace
        assert data["summary"] == "Test summary"

    def test_confidence_bounds(self, namespace: str) -> None:
        with pytest.raises(ValueError):
            MemoryRecord(namespace=namespace, confidence=1.5)
        with pytest.raises(ValueError):
            MemoryRecord(namespace=namespace, confidence=-0.1)
