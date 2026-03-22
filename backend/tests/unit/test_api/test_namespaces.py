from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)

NS = "agent:ns-test"


def _seed_namespace() -> None:
    """Create a memory to ensure the namespace exists."""
    client.post(
        "/v1/memories",
        json={"namespace": NS, "content_text": "test memory for namespace"},
    )


class TestListNamespaces:
    def test_list_empty(self) -> None:
        resp = client.get("/v1/namespaces")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_after_create_memory(self) -> None:
        _seed_namespace()
        resp = client.get("/v1/namespaces")
        assert resp.status_code == 200
        assert NS in resp.json()


class TestGetNamespace:
    def test_get_existing(self) -> None:
        _seed_namespace()
        resp = client.get(f"/v1/namespaces/{NS}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["namespace"] == NS
        assert data["total_memories"] >= 1
        assert "memory_type_distribution" in data

    def test_get_nonexistent(self) -> None:
        resp = client.get("/v1/namespaces/nonexistent:xyz")
        assert resp.status_code == 404


class TestCreateNamespace:
    def test_create_new(self) -> None:
        ns = "agent:brand-new-ns"
        resp = client.post(f"/v1/namespaces?namespace={ns}")
        assert resp.status_code == 201
        data = resp.json()
        assert data["namespace"] == ns
        assert data["status"] == "created"

        # Verify it shows up in the list
        list_resp = client.get("/v1/namespaces")
        assert ns in list_resp.json()

    def test_create_duplicate(self) -> None:
        ns = "agent:dup-ns"
        client.post(f"/v1/namespaces?namespace={ns}")
        resp = client.post(f"/v1/namespaces?namespace={ns}")
        assert resp.status_code == 409


class TestDeleteNamespace:
    def test_delete_existing(self) -> None:
        ns = "agent:to-delete"
        client.post(
            "/v1/memories",
            json={"namespace": ns, "content_text": "will be deleted"},
        )

        resp = client.delete(f"/v1/namespaces/{ns}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["namespace"] == ns
        assert data["status"] == "deleted"
        assert data["search_deleted"] >= 1

        # Verify namespace is gone
        list_resp = client.get("/v1/namespaces")
        assert ns not in list_resp.json()

    def test_delete_nonexistent(self) -> None:
        resp = client.delete("/v1/namespaces/nonexistent:xyz")
        assert resp.status_code == 404
