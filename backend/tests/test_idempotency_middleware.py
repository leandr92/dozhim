from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


AUTH = {"Authorization": "Bearer test-token"}


def test_idempotency_replay_same_payload() -> None:
    with TestClient(app) as client:
        key = f"idem-{uuid4()}"
        project_code = f"P-{uuid4().hex[:10]}"
        payload = {"project_code": project_code, "project_name": "Idem Project", "status": "active"}

        first = client.post("/api/v1/projects", headers={**AUTH, "Idempotency-Key": key}, json=payload)
        assert first.status_code == 200
        first_body = first.json()

        second = client.post("/api/v1/projects", headers={**AUTH, "Idempotency-Key": key}, json=payload)
        assert second.status_code == 200
        assert second.headers.get("X-Idempotent-Replay") == "true"
        assert second.json() == first_body


def test_idempotency_conflict_different_payload() -> None:
    with TestClient(app) as client:
        key = f"idem-{uuid4()}"
        project_code = f"P-{uuid4().hex[:10]}"
        first_payload = {"project_code": project_code, "project_name": "First Name", "status": "active"}
        second_payload = {"project_code": project_code, "project_name": "Different Name", "status": "active"}

        first = client.post("/api/v1/projects", headers={**AUTH, "Idempotency-Key": key}, json=first_payload)
        assert first.status_code == 200

        second = client.post("/api/v1/projects", headers={**AUTH, "Idempotency-Key": key}, json=second_payload)
        assert second.status_code == 409
        body = second.json()
        assert body["code"] == "IDEMPOTENCY_KEY_REUSED"
        assert body["retryable"] is False
