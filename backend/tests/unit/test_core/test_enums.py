from __future__ import annotations

from dse.core.enums import (
    CascadeStage,
    ContentType,
    DecayTier,
    MemorySubtype,
    MemoryType,
    PIIPolicy,
    RelationType,
    SourceType,
    TriggerType,
    VerificationStatus,
)


class TestEnums:
    def test_memory_type_values(self) -> None:
        assert MemoryType.EPISODIC == "episodic"
        assert MemoryType.SEMANTIC == "semantic"
        assert MemoryType.PROCEDURAL == "procedural"
        assert MemoryType.PROSPECTIVE == "prospective"

    def test_relation_type_values(self) -> None:
        assert RelationType.SUPERSEDED_BY == "SUPERSEDED_BY"
        assert RelationType.CONTRADICTS == "CONTRADICTS"
        assert RelationType.COMPLEMENTS == "COMPLEMENTS"

    def test_cascade_stage_values(self) -> None:
        assert CascadeStage.FAST == "fast"
        assert CascadeStage.PRECISION == "precision"
        assert CascadeStage.DEEP == "deep"

    def test_decay_tier_values(self) -> None:
        assert DecayTier.ACTIVE == "active"
        assert DecayTier.WARM == "warm"
        assert DecayTier.ARCHIVE == "archive"

    def test_all_enum_members_are_str(self) -> None:
        for enum_cls in [
            MemoryType,
            MemorySubtype,
            ContentType,
            SourceType,
            VerificationStatus,
            RelationType,
            TriggerType,
            DecayTier,
            CascadeStage,
            PIIPolicy,
        ]:
            for member in enum_cls:
                assert isinstance(member.value, str)
