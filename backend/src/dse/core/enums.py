from __future__ import annotations

from enum import StrEnum


class MemoryType(StrEnum):
    """Memory classification based on cognitive science."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PROSPECTIVE = "prospective"


class MemorySubtype(StrEnum):
    """How the memory was generated."""

    OBSERVATION = "observation"
    INFERENCE = "inference"
    USER_EXPLICIT = "user_explicit"
    AGENT_GENERATED = "agent_generated"


class ContentType(StrEnum):
    """Content format of the memory."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"
    CODE = "code"
    STRUCTURED_DATA = "structured_data"


class SourceType(StrEnum):
    """Origin of the memory."""

    OBSERVATION = "observation"
    INFERENCE = "inference"
    USER_EXPLICIT = "user_explicit"
    EXTERNAL_API = "external_api"


class VerificationStatus(StrEnum):
    """Trust status of a memory record."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    PENDING = "pending"  # Phase 2: awaiting human resolution
    SUPERSEDED = "superseded"


class RelationType(StrEnum):
    """Edge types in the memory graph.

    Values are Neo4j relationship names (upper snake case).
    Design ref: PROJECT.md Section 3.3
    """

    SUPERSEDED_BY = "SUPERSEDED_BY"
    COMPLEMENTS = "COMPLEMENTS"
    CONTRADICTS = "CONTRADICTS"
    DERIVES = "DERIVES"
    TEMPORALLY_PRECEDES = "TEMPORALLY_PRECEDES"
    CAUSES = "CAUSES"
    HAS_CHILD = "HAS_CHILD"
    REFERENCES = "REFERENCES"


class EvidenceType(StrEnum):
    """Evidence type for Bayesian confidence updates.

    Design ref: PROJECT.md Section 6.2
    """

    USER_EXPLICIT_CORRECTION = "user_explicit_correction"
    CORROBORATING_SOURCE = "corroborating_source"
    CONTRADICTING_SOURCE = "contradicting_source"
    PASSAGE_OF_TIME = "passage_of_time"
    REPEATED_ACCESS = "repeated_access"
    RELATION_DERIVED = "relation_derived"


class TriggerType(StrEnum):
    """Prospective memory trigger type."""

    TIME = "time"
    EVENT = "event"
    CONDITION = "condition"


class DecayTier(StrEnum):
    """Memory lifecycle tier based on decay score."""

    ACTIVE = "active"
    WARM = "warm"
    ARCHIVE = "archive"


class CascadeStage(StrEnum):
    """Cascade retrieval stages for latency/quality trade-off."""

    FAST = "fast"
    PRECISION = "precision"
    DEEP = "deep"


class PIIPolicy(StrEnum):
    """PII handling policy."""

    BLOCK = "block"
    ANONYMIZE = "anonymize"
    TOKENIZE = "tokenize"


class MemoryEventType(StrEnum):
    """Events published to Kafka after memory operations."""

    CREATED = "memory.created"
    UPDATED = "memory.updated"
    DELETED = "memory.deleted"
    ACCESSED = "memory.accessed"


class CDCEventType(StrEnum):
    """External CDC event types."""

    INSERT = "cdc.insert"
    UPDATE = "cdc.update"
    DELETE = "cdc.delete"
