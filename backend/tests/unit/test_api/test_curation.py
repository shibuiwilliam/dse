from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)

NAMESPACE = "test-curation"


def _create_memory(summary: str = "test memory", memory_type: str = "episodic") -> str:
    resp = client.post(
        "/v1/memories",
        json={
            "namespace": NAMESPACE,
            "content_text": summary,
            "summary": summary,
            "memory_type": memory_type,
        },
    )
    return resp.json()["id"]


class TestCurationMemories:
    def test_list_memories(self) -> None:
        _create_memory("curation test A")
        resp = client.get("/v1/curation/memories", params={"namespace": NAMESPACE})
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        assert data["total"] >= 1

    def test_list_with_type_filter(self) -> None:
        _create_memory("semantic test", memory_type="semantic")
        resp = client.get(
            "/v1/curation/memories",
            params={"namespace": NAMESPACE, "memory_type": "semantic"},
        )
        assert resp.status_code == 200

    def test_list_requires_namespace(self) -> None:
        resp = client.get("/v1/curation/memories")
        assert resp.status_code == 422


class TestCurationPin:
    def test_pin_sets_importance_to_1(self) -> None:
        mid = _create_memory("pin test")
        resp = client.post(f"/v1/curation/memories/{mid}/pin", json={"pinned": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "pinned"

    def test_pin_nonexistent_404(self) -> None:
        resp = client.post("/v1/curation/memories/nonexistent/pin", json={"pinned": True})
        assert resp.status_code == 404


class TestCurationForget:
    def test_forget_deletes_memory(self) -> None:
        mid = _create_memory("forget test")
        resp = client.post(f"/v1/curation/memories/{mid}/forget")
        assert resp.status_code == 200
        assert mid in resp.json()["deleted_ids"]


class TestCurationProspective:
    def test_create_prospective(self) -> None:
        resp = client.post(
            "/v1/curation/prospective",
            json={
                "namespace": NAMESPACE,
                "summary": "Check project X status",
                "trigger_type": "time",
                "trigger_at": "2026-12-31T00:00:00Z",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "created"

    def test_list_prospective(self) -> None:
        resp = client.get("/v1/curation/prospective", params={"namespace": NAMESPACE})
        assert resp.status_code == 200


class TestCurationStats:
    def test_stats(self) -> None:
        _create_memory("stats test")
        resp = client.get("/v1/curation/stats", params={"namespace": NAMESPACE})
        assert resp.status_code == 200
        data = resp.json()
        assert data["namespace"] == NAMESPACE
        assert "total_memories" in data
        assert "memory_type_distribution" in data
        assert "decay_distribution" in data
