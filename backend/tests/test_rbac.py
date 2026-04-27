from fastapi.testclient import TestClient

from app.main import app


def test_mutating_endpoint_forbidden_for_viewer() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/projects",
            headers={
                "Authorization": "Bearer test-token",
                "Idempotency-Key": "rbac-project-create",
                "X-Role": "viewer",
            },
            json={"project_code": "RBAC-P1", "project_name": "RBAC Test"},
        )
        assert response.status_code == 403
        payload = response.json()
        assert payload["code"] == "FORBIDDEN"
        assert payload["retryable"] is False
        assert payload["severity"] == "warning"


def test_mutating_endpoint_allowed_for_operator() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/projects",
            headers={
                "Authorization": "Bearer test-token",
                "Idempotency-Key": "rbac-project-create-operator",
                "X-Role": "operator",
            },
            json={"project_code": "RBAC-P2", "project_name": "RBAC Operator"},
        )
        assert response.status_code in (200, 409)
