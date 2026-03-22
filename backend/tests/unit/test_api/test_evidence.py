from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)


class TestEvidenceEndpoint:
    def _create_memory(self) -> str:
        resp = client.post(
            "/v1/memories",
            json={
                "namespace": "test-evidence",
                "content_text": "The sky is blue",
                "confidence": 0.5,
            },
        )
        return resp.json()["id"]

    def test_corroborating_evidence_increases_confidence(self) -> None:
        memory_id = self._create_memory()
        resp = client.post(
            f"/v1/memories/{memory_id}/evidence",
            json={
                "evidence_type": "corroborating_source",
                "source_independent": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["posterior"] > data["prior"]

    def test_contradicting_evidence_decreases_confidence(self) -> None:
        memory_id = self._create_memory()
        resp = client.post(
            f"/v1/memories/{memory_id}/evidence",
            json={"evidence_type": "contradicting_source"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["posterior"] < data["prior"]

    def test_user_correction_forces_value(self) -> None:
        memory_id = self._create_memory()
        resp = client.post(
            f"/v1/memories/{memory_id}/evidence",
            json={
                "evidence_type": "user_explicit_correction",
                "forced_value": 0.95,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["posterior"] == 0.95

    def test_evidence_on_nonexistent_memory(self) -> None:
        resp = client.post(
            "/v1/memories/nonexistent/evidence",
            json={"evidence_type": "corroborating_source"},
        )
        assert resp.status_code == 404

    def test_invalid_evidence_type(self) -> None:
        resp = client.post(
            "/v1/memories/test/evidence",
            json={"evidence_type": "invalid_type"},
        )
        assert resp.status_code == 422
