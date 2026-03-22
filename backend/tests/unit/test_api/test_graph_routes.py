from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)


class TestGraphSubgraph:
    def test_subgraph_returns_200(self) -> None:
        resp = client.get("/v1/graph/subgraph", params={"namespace": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data

    def test_subgraph_requires_namespace(self) -> None:
        resp = client.get("/v1/graph/subgraph")
        assert resp.status_code == 422


class TestGraphNeighbors:
    def test_neighbors_returns_200(self) -> None:
        resp = client.get("/v1/graph/neighbors/test-id")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_neighbors_with_depth(self) -> None:
        resp = client.get(
            "/v1/graph/neighbors/test-id",
            params={"depth": 2, "limit": 5},
        )
        assert resp.status_code == 200

    def test_neighbors_depth_max_validation(self) -> None:
        resp = client.get(
            "/v1/graph/neighbors/test-id",
            params={"depth": 10},
        )
        assert resp.status_code == 422


class TestGraphLineage:
    def test_lineage_returns_200(self) -> None:
        resp = client.get("/v1/graph/lineage/test-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["memory_id"] == "test-id"
        assert "lineage" in data
