from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)


class TestCreateMemory:
    def test_create_minimal(self) -> None:
        response = client.post(
            "/v1/memories",
            json={
                "namespace": "agent:test/project:test",
                "content_text": "Python is an interpreted language",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"]
        assert data["namespace"] == "agent:test/project:test"
        assert data["memory_type"] == "episodic"
        assert data["confidence"] == 0.5

    def test_create_with_all_fields(self) -> None:
        response = client.post(
            "/v1/memories",
            json={
                "namespace": "agent:test/project:test",
                "content_text": "Always check test coverage",
                "summary": "Test coverage rule",
                "memory_type": "procedural",
                "memory_subtype": "user_explicit",
                "content_type": "text",
                "confidence": 0.9,
                "source_type": "user_explicit",
                "source_id": "conv:123",
                "tags": ["testing", "rules"],
                "entities": ["pytest", "coverage"],
                "language": "en",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["memory_type"] == "procedural"
        assert data["confidence"] == 0.9
        assert "testing" in data["tags"]

    def test_create_invalid_confidence(self) -> None:
        response = client.post(
            "/v1/memories",
            json={
                "namespace": "test",
                "content_text": "test",
                "confidence": 1.5,
            },
        )
        assert response.status_code == 422

    def test_create_missing_namespace(self) -> None:
        response = client.post(
            "/v1/memories",
            json={"content_text": "test"},
        )
        assert response.status_code == 422


class TestDeleteMemory:
    def test_delete_returns_204(self) -> None:
        # Create first
        create_resp = client.post(
            "/v1/memories",
            json={
                "namespace": "test",
                "content_text": "to be deleted",
            },
        )
        memory_id = create_resp.json()["id"]

        # Delete
        response = client.delete(f"/v1/memories/{memory_id}")
        assert response.status_code == 204


class TestFeedback:
    def test_feedback_on_nonexistent(self) -> None:
        response = client.post(
            "/v1/memories/nonexistent-id/feedback",
            json={"utility_score": 0.8},
        )
        assert response.status_code == 404


class TestCurate:
    def test_curate_on_nonexistent(self) -> None:
        response = client.post(
            "/v1/memories/nonexistent-id/curate",
            json={"action": "pin"},
        )
        assert response.status_code == 404
