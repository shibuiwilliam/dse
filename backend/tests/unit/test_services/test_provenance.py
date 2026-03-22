from __future__ import annotations

import pytest

from dse.core.models import ProvenanceEntry
from dse.infrastructure.provenance import ProvenanceService
from dse.services.storage import MockStorageService


class TestProvenanceService:
    @pytest.fixture
    def svc(self) -> ProvenanceService:
        return ProvenanceService(MockStorageService())

    @pytest.mark.asyncio
    async def test_initialize_creates_record(self, svc: ProvenanceService) -> None:
        entry = ProvenanceEntry(step="observation", performed_by="agent:test", description="test")
        await svc.initialize("m1", "test", created_by=entry)
        result = await svc.get("m1", "test")
        assert result is not None
        assert result.memory_id == "m1"
        assert result.created_by.step == "observation"

    @pytest.mark.asyncio
    async def test_record_transformation(self, svc: ProvenanceService) -> None:
        await svc.initialize(
            "m1",
            "test",
            created_by=ProvenanceEntry(
                step="observation", performed_by="agent:test", description="init"
            ),
        )
        await svc.record_transformation(
            "m1",
            "test",
            entry=ProvenanceEntry(
                step="summarization",
                performed_by="agent:mma",
                model_used="gemini-3.0-flash",
                description="summarized",
            ),
        )
        result = await svc.get("m1", "test")
        assert result is not None
        assert len(result.transformations) == 1
        assert result.transformations[0].step == "summarization"

    @pytest.mark.asyncio
    async def test_record_access(self, svc: ProvenanceService) -> None:
        await svc.initialize(
            "m1",
            "test",
            created_by=ProvenanceEntry(
                step="observation", performed_by="agent:test", description="init"
            ),
        )
        await svc.record_access("m1", "test", accessed_by="agent:task-1", utility_score=0.85)
        result = await svc.get("m1", "test")
        assert result is not None
        assert len(result.access_log) == 1
        assert result.access_log[0].utility_score == 0.85

    @pytest.mark.asyncio
    async def test_access_log_max_500(self, svc: ProvenanceService) -> None:
        await svc.initialize(
            "m1",
            "test",
            created_by=ProvenanceEntry(
                step="observation", performed_by="agent:test", description="init"
            ),
        )
        for i in range(550):
            await svc.record_access("m1", "test", accessed_by=f"agent:{i}")
        result = await svc.get("m1", "test")
        assert result is not None
        assert len(result.access_log) <= 500

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, svc: ProvenanceService) -> None:
        result = await svc.get("nonexistent", "test")
        assert result is None
