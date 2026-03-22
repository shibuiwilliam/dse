from __future__ import annotations

from dse.core.exceptions import (
    AccessDeniedError,
    ConflictError,
    DSEError,
    EmbeddingError,
    GraphError,
    MemoryNotFoundError,
    PIIDetectedError,
    SearchServiceError,
    StorageError,
)


class TestExceptions:
    def test_base_error(self) -> None:
        err = DSEError("test", code="TEST")
        assert str(err) == "test"
        assert err.code == "TEST"
        assert err.message == "test"

    def test_memory_not_found(self) -> None:
        err = MemoryNotFoundError("abc-123")
        assert err.code == "MEMORY_NOT_FOUND"
        assert "abc-123" in err.message
        assert err.memory_id == "abc-123"

    def test_search_service_error(self) -> None:
        err = SearchServiceError("timeout")
        assert err.code == "SEARCH_SERVICE_ERROR"

    def test_embedding_error(self) -> None:
        err = EmbeddingError("dim mismatch")
        assert err.code == "EMBEDDING_ERROR"

    def test_graph_error(self) -> None:
        err = GraphError("connection lost")
        assert err.code == "GRAPH_ERROR"

    def test_storage_error(self) -> None:
        err = StorageError("bucket not found")
        assert err.code == "STORAGE_ERROR"

    def test_conflict_error(self) -> None:
        err = ConflictError("a", "b", "duplicate")
        assert err.code == "CONFLICT_ERROR"
        assert err.memory_id == "a"
        assert err.conflicting_id == "b"

    def test_pii_detected(self) -> None:
        err = PIIDetectedError(["email", "phone"])
        assert err.code == "PII_DETECTED"
        assert err.pii_types == ["email", "phone"]

    def test_access_denied(self) -> None:
        err = AccessDeniedError("ns:private", "write")
        assert err.code == "ACCESS_DENIED"

    def test_all_inherit_from_dse_error(self) -> None:
        for exc_cls in [
            MemoryNotFoundError,
            SearchServiceError,
            EmbeddingError,
            GraphError,
            StorageError,
        ]:
            assert issubclass(exc_cls, DSEError)
