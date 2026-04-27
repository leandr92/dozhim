from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


AUTH = {"Authorization": "Bearer test-token", "X-Role": "operator"}


def test_mutating_request_creates_audit_log() -> None:
    with TestClient(app) as client:
        code = f"AUD-{uuid4().hex[:8]}"
        create = client.post(
            "/api/v1/projects",
            headers={**AUTH, "Idempotency-Key": f"audit-{uuid4()}"},
            json={"project_code": code, "project_name": "Audit Project", "status": "active"},
        )
        assert create.status_code == 200

        logs = client.get("/api/v1/audit-logs", headers={"Authorization": "Bearer test-token"})
        assert logs.status_code == 200
        items = logs.json()["items"]
        assert len(items) > 0
        latest = items[0]
        assert latest["method"] == "POST"
        assert latest["path"] == "/api/v1/projects"
        assert latest["actor_id"] == "test-token"
        assert "request" in latest["diff"]
        assert "response" in latest["diff"]


def test_audit_logs_filtering() -> None:
    with TestClient(app) as client:
        code = f"AUD-{uuid4().hex[:8]}"
        client.post(
            "/api/v1/projects",
            headers={**AUTH, "Idempotency-Key": f"audit-filter-{uuid4()}"},
            json={"project_code": code, "project_name": "Audit Filter Project", "status": "active"},
        )

        filtered = client.get(
            "/api/v1/audit-logs",
            params={"method": "POST", "path": "/projects", "status_code": 200, "actor_id": "test-token"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert filtered.status_code == 200
        items = filtered.json()["items"]
        assert all(x["method"] == "POST" for x in items)
        assert all("/projects" in x["path"] for x in items)
        assert all(x["status_code"] == 200 for x in items)


def test_audit_logs_page_size_capped() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/audit-logs",
            params={"page_size": 9999},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["page_size"] == 200


def test_audit_logs_page_minimum_one() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/audit-logs",
            params={"page": 0},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        assert response.json()["page"] == 1


def test_audit_logs_sorting_status_code_asc() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/audit-logs",
            params={"sort_by": "status_code", "sort_dir": "asc", "page_size": 50},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        codes = [x["status_code"] for x in items]
        assert codes == sorted(codes)
