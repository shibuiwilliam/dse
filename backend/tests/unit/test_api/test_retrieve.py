from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)


class TestRetrieveEndpoint:
    def test_retrieve_empty(self) -> None:
        response = client.post(
            "/v1/memories/retrieve",
            json={
                "query": "Python programming",
                "namespace": "test",
                "token_budget": 1000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_tokens" in data
        assert data["query"] == "Python programming"

    def test_retrieve_with_cascade_stage(self) -> None:
        response = client.post(
            "/v1/memories/retrieve",
            json={
                "query": "test query",
                "cascade_stage": "fast",
                "token_budget": 500,
            },
        )
        assert response.status_code == 200

    def test_retrieve_with_memory_types(self) -> None:
        response = client.post(
            "/v1/memories/retrieve",
            json={
                "query": "test",
                "memory_types": ["semantic", "procedural"],
            },
        )
        assert response.status_code == 200

    def test_retrieve_invalid_budget(self) -> None:
        response = client.post(
            "/v1/memories/retrieve",
            json={
                "query": "test",
                "token_budget": 10,  # Below minimum of 100
            },
        )
        assert response.status_code == 422

    def test_retrieve_after_create(self) -> None:
        # Create a memory
        client.post(
            "/v1/memories",
            json={
                "namespace": "test-retrieve",
                "content_text": "Kubernetes is a container orchestration platform",
                "summary": "Kubernetes overview",
                "memory_type": "semantic",
            },
        )

        # Retrieve
        response = client.post(
            "/v1/memories/retrieve",
            json={
                "query": "Kubernetes",
                "namespace": "test-retrieve",
            },
        )
        assert response.status_code == 200
