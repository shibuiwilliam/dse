from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)


class TestSessionContext:
    def test_set_and_get_context(self) -> None:
        client.put(
            "/v1/sessions/s1/context",
            json={"context": {"task": "test", "step": 1}},
        )
        resp = client.get("/v1/sessions/s1/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s1"
        assert data["context"]["task"] == "test"

    def test_get_nonexistent_context(self) -> None:
        resp = client.get("/v1/sessions/nonexistent/context")
        assert resp.status_code == 200
        assert resp.json()["context"] is None


class TestSessionTurns:
    def test_append_and_get_turns(self) -> None:
        client.post(
            "/v1/sessions/s2/turns",
            json={"turn": {"role": "user", "content": "hello"}},
        )
        client.post(
            "/v1/sessions/s2/turns",
            json={"turn": {"role": "assistant", "content": "hi"}},
        )
        resp = client.get("/v1/sessions/s2/turns")
        assert resp.status_code == 200
        assert len(resp.json()["turns"]) == 2


class TestSessionPersist:
    def test_persist_snapshot(self) -> None:
        client.put(
            "/v1/sessions/s3/context",
            json={"context": {"task": "snapshot_test"}},
        )
        client.post(
            "/v1/sessions/s3/turns",
            json={"turn": {"role": "user", "content": "data"}},
        )
        resp = client.post("/v1/sessions/s3/persist")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s3"
        assert data["context"] is not None
        assert len(data["turns"]) >= 1


class TestSessionDelete:
    def test_delete_session(self) -> None:
        client.put(
            "/v1/sessions/s4/context",
            json={"context": {"key": "val"}},
        )
        resp = client.delete("/v1/sessions/s4")
        assert resp.status_code == 204

        # Verify cleaned up
        resp = client.get("/v1/sessions/s4/context")
        assert resp.json()["context"] is None
