from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from dse.core.enums import (
    CDCEventType,
    ContentType,
    DecayTier,
    EvidenceType,
    MemoryEventType,
    MemorySubtype,
    MemoryType,
    RelationType,
    SourceType,
    TriggerType,
    VerificationStatus,
)


def _generate_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


class MemoryRecord(BaseModel):
    """Core domain model representing a single memory in DSE."""

    id: str = Field(default_factory=_generate_id)
    namespace: str = Field(..., description="Scope: agent:{id}/project:{id}")

    content_path: str = ""
    summary: str = Field(default="", max_length=500)
    content_text: str = ""

    embedding: list[float] = Field(default_factory=list)
    summary_embedding: list[float] = Field(default_factory=list)
    embedding_model: str = "gemini-embedding-2-preview"
    embedding_version: str = "2026-01"

    memory_type: MemoryType = MemoryType.EPISODIC
    memory_subtype: MemorySubtype = MemorySubtype.OBSERVATION
    content_type: ContentType = ContentType.TEXT

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_basis: str = "observation"
    corroborating_sources: int = 0
    contradicting_sources: int = 0
    confidence_updated_at: str = ""
    source_type: SourceType = SourceType.OBSERVATION
    source_id: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    last_verified_at: datetime | None = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    accessed_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None

    access_count: int = 0
    access_count_7d: int = 0
    access_count_30d: int = 0
    last_access_utility: float = 0.0

    decay_score: float = Field(default=1.0, ge=0.0, le=1.0)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)

    superseded_by: str | None = None
    supersedes: list[str] = Field(default_factory=list)
    parent_id: str | None = None

    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    language: str = "ja"

    trigger_type: TriggerType | None = None
    trigger_at: datetime | None = None
    trigger_condition: str | None = None
    is_triggered: bool = False

    is_archived: bool = False
    archived_at: datetime | None = None
    archive_reason: str | None = None

    neighbor_ids: list[str] = Field(default_factory=list)

    @property
    def decay_tier(self) -> DecayTier:
        if self.decay_score > 0.4:
            return DecayTier.ACTIVE
        if self.decay_score > 0.2:
            return DecayTier.WARM
        return DecayTier.ARCHIVE

    def compute_decay_score(self, now: datetime | None = None) -> float:
        """Ebbinghaus-inspired decay with access frequency and importance correction."""
        now = now or datetime.now(UTC)
        age_days = (now - self.created_at).total_seconds() / 86400

        decay_rates: dict[str, float] = {
            MemoryType.EPISODIC: 0.05,
            MemoryType.SEMANTIC: 0.01,
            MemoryType.PROCEDURAL: 0.008,
            MemoryType.PROSPECTIVE: 0.0,
        }
        decay_rate = decay_rates.get(self.memory_type, 0.05)
        base_decay = math.exp(-decay_rate * age_days)
        access_boost = 1.0 + 0.1 * math.log(1 + self.access_count_30d)
        importance_factor = 0.5 + 0.5 * self.importance_score
        return min(1.0, base_decay * access_boost * importance_factor)

    def to_index_dict(self) -> dict[str, Any]:
        """Serialize for search index upsert."""
        data = self.model_dump(mode="json")
        data.pop("embedding", None)
        data.pop("summary_embedding", None)
        return data


# ---------------------------------------------------------------------------
# Graph models (Phase 2 — P2-1)
# ---------------------------------------------------------------------------


class MemoryNode(BaseModel):
    """Lightweight graph node representation for Neo4j operations."""

    id: str
    namespace: str
    memory_type: str = "episodic"
    confidence: float = 0.5
    importance: float = 0.5
    verification_status: str = "unverified"
    is_archived: bool = False
    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)


class RelationRecord(BaseModel):
    """Edge record for creating graph relationships."""

    from_id: str
    to_id: str
    relation_type: RelationType
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: str = Field(default_factory=_utcnow_iso)
    created_by: str = "system"
    method: str = ""


# ---------------------------------------------------------------------------
# Confidence / Evidence (Phase 2 — P2-3)
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """Evidence for Bayesian confidence updates."""

    type: EvidenceType
    source_independent: bool = False
    forced_value: float | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Provenance (Phase 2 — P2-6)
# ---------------------------------------------------------------------------


class ProvenanceEntry(BaseModel):
    """A single step in a memory's lineage."""

    entry_id: str = Field(default_factory=_generate_id)
    step: str
    timestamp: str = Field(default_factory=_utcnow_iso)
    performed_by: str = ""
    task_id: str | None = None
    session_id: str | None = None
    description: str = ""
    model_used: str | None = None
    input_memory_ids: list[str] = Field(default_factory=list)


class AccessLogEntry(BaseModel):
    """Memory access record for provenance tracking."""

    accessed_by: str
    accessed_at: str = Field(default_factory=_utcnow_iso)
    task_id: str | None = None
    utility_score: float | None = None


class MemoryProvenance(BaseModel):
    """Complete provenance for a memory record, persisted in Object Storage."""

    memory_id: str
    created_by: ProvenanceEntry
    transformations: list[ProvenanceEntry] = Field(default_factory=list)
    access_log: list[AccessLogEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Event models (Phase 2 — P2-5)
# ---------------------------------------------------------------------------


class MemoryEvent(BaseModel):
    """Event published to Kafka after memory operations."""

    event_id: str = Field(default_factory=_generate_id)
    event_type: MemoryEventType
    memory_id: str
    namespace: str
    timestamp: str = Field(default_factory=_utcnow_iso)
    payload: dict[str, Any] = Field(default_factory=dict)


class CDCEvent(BaseModel):
    """External CDC event received from Kafka."""

    event_id: str = Field(default_factory=_generate_id)
    event_type: CDCEventType
    source_system: str
    source_entity_type: str
    source_entity_id: str
    namespace: str
    payload_before: dict[str, Any] | None = None
    payload_after: dict[str, Any] | None = None
    timestamp: str = Field(default_factory=_utcnow_iso)


# ---------------------------------------------------------------------------
# Search & retrieval models (unchanged from Phase 1)
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    record: MemoryRecord
    score: float = 0.0
    rrf_score: float = 0.0
    match_source: str = ""


class ContextItem(BaseModel):
    memory_id: str
    memory_type: MemoryType
    content: str
    tier: str
    score: float
    confidence: float
    created_at: datetime
    tokens: int = 0


class AssembledContext(BaseModel):
    items: list[ContextItem] = Field(default_factory=list)
    total_tokens: int = 0
    query: str = ""
    namespace: str = ""


# Keep backwards-compat alias
Relation = RelationRecord
MemoryLineage = MemoryProvenance
