from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)


class TestHealthEndpoints:
    def test_health(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_returns_200(self) -> None:
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ready", "degraded")
        assert "checks" in data
