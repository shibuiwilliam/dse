from __future__ import annotations


class DSEError(Exception):
    """Base exception for all DSE errors."""

    def __init__(self, message: str, code: str = "DSE_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class MemoryNotFoundError(DSEError):
    """Requested memory record does not exist."""

    def __init__(self, memory_id: str) -> None:
        super().__init__(
            message=f"Memory not found: {memory_id}",
            code="MEMORY_NOT_FOUND",
        )
        self.memory_id = memory_id


class SearchServiceError(DSEError):
    """Elasticsearch search operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="SEARCH_SERVICE_ERROR")


class EmbeddingError(DSEError):
    """Embedding generation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="EMBEDDING_ERROR")


class GraphError(DSEError):
    """Neo4j graph operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="GRAPH_ERROR")


class StorageError(DSEError):
    """Object storage operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="STORAGE_ERROR")


class ConflictError(DSEError):
    """Memory conflict detected (duplicate or contradiction)."""

    def __init__(self, memory_id: str, conflicting_id: str, reason: str) -> None:
        super().__init__(
            message=f"Conflict between {memory_id} and {conflicting_id}: {reason}",
            code="CONFLICT_ERROR",
        )
        self.memory_id = memory_id
        self.conflicting_id = conflicting_id


class PIIDetectedError(DSEError):
    """PII was detected in content and policy is BLOCK."""

    def __init__(self, pii_types: list[str]) -> None:
        super().__init__(
            message=f"PII detected: {', '.join(pii_types)}",
            code="PII_DETECTED",
        )
        self.pii_types = pii_types


class AccessDeniedError(DSEError):
    """Insufficient permissions for the requested operation."""

    def __init__(self, namespace: str, required_scope: str) -> None:
        super().__init__(
            message=f"Access denied to {namespace}: requires {required_scope}",
            code="ACCESS_DENIED",
        )
