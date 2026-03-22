from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dse.core.enums import (
    CascadeStage,
    ContentType,
    EvidenceType,
    MemorySubtype,
    MemoryType,
    SourceType,
    TriggerType,
)

# --- Request schemas ---


class MemoryCreateRequest(BaseModel):
    """Request to create a new memory record."""

    namespace: str
    content_text: str
    summary: str = ""
    memory_type: MemoryType = MemoryType.EPISODIC
    memory_subtype: MemorySubtype = MemorySubtype.OBSERVATION
    content_type: ContentType = ContentType.TEXT
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_type: SourceType = SourceType.OBSERVATION
    source_id: str = ""
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    language: str = "ja"

    # Prospective memory fields
    trigger_type: TriggerType | None = None
    trigger_at: datetime | None = None
    trigger_condition: str | None = None


class MemoryUpdateRequest(BaseModel):
    """Request to update an existing memory record."""

    summary: str | None = None
    content_text: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    importance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    entities: list[str] | None = None
    is_archived: bool | None = None


class RetrieveRequest(BaseModel):
    """Request to retrieve memory context."""

    query: str
    namespace: str | None = None
    memory_types: list[MemoryType] | None = None
    token_budget: int = Field(default=4000, ge=100, le=100000)
    cascade_stage: CascadeStage | None = None
    task_context: str = ""
    top_k: int = Field(default=10, ge=1, le=100)


class FeedbackRequest(BaseModel):
    """Feedback on a memory's utility in a specific context."""

    utility_score: float = Field(ge=0.0, le=1.0)
    accessor_type: str = "agent"
    task_id: str = ""


class CurateRequest(BaseModel):
    """Manual curation action on a memory."""

    action: str  # "pin", "archive", "delete", "update_importance"
    importance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str = ""


class EvidenceRequest(BaseModel):
    """Submit evidence to update a memory's confidence score."""

    evidence_type: EvidenceType
    source_independent: bool = False
    forced_value: float | None = Field(default=None, ge=0.0, le=1.0)
    description: str = ""


# --- Response schemas ---


class MemoryResponse(BaseModel):
    """Single memory record response."""

    id: str
    namespace: str
    summary: str
    content_text: str = ""
    content_path: str = ""
    memory_type: MemoryType
    memory_subtype: MemorySubtype
    content_type: ContentType
    confidence: float
    source_type: SourceType
    source_id: str
    verification_status: str
    created_at: datetime
    updated_at: datetime
    decay_score: float
    importance_score: float
    tags: list[str]
    entities: list[str]
    language: str
    is_archived: bool
    superseded_by: str | None = None
    trigger_type: TriggerType | None = None
    trigger_at: datetime | None = None
    is_triggered: bool = False


class ContextItemResponse(BaseModel):
    """A memory item in the assembled context."""

    memory_id: str
    memory_type: MemoryType
    content: str
    tier: str
    score: float
    confidence: float
    created_at: datetime
    tokens: int


class RetrieveResponse(BaseModel):
    """Response from the retrieve endpoint."""

    items: list[ContextItemResponse]
    total_tokens: int
    query: str
    namespace: str


class ConflictResponse(BaseModel):
    """A pair of contradicting memories."""

    a_id: str
    b_id: str
    a_summary: str
    b_summary: str


class StatsResponse(BaseModel):
    """Namespace statistics."""

    namespace: str
    total_memories: int
    active_count: int
    warm_count: int
    archived_count: int
    contradiction_count: int
    memory_type_distribution: dict[str, int]


class GraphNeighborResponse(BaseModel):
    """A neighbor in the memory graph."""

    id: str
    summary: str
    memory_type: str
    confidence: float
    relation_type: str
    strength: float | None = None


class GraphResponse(BaseModel):
    """Graph visualization data."""

    center_id: str
    neighbors: list[GraphNeighborResponse]


class LineageResponse(BaseModel):
    """Provenance lineage for a memory."""

    memory_id: str
    lineage: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
