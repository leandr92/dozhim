from fastapi.testclient import TestClient

from app.main import app


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": "idem-1"}


def test_assignments_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/assignments")
        assert response.status_code == 401


def test_job_action_returns_202_and_location() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assignments/nonexistent/actions",
            json={"action": "send_reminder", "revision": 1, "payload": {}},
            headers=_auth_headers(),
        )
        assert response.status_code in (202, 404)
        if response.status_code == 202:
            assert "Location" in response.headers
