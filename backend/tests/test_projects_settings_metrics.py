from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


AUTH = {"Authorization": "Bearer test-token"}


def test_projects_and_metrics_flow() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/api/v1/projects",
            headers={**AUTH, "Idempotency-Key": f"project-create-{uuid4()}"},
            json={"project_code": "P-001", "project_name": "Pilot", "status": "active"},
        )
        assert create.status_code in (200, 409)

        projects = client.get("/api/v1/projects", headers=AUTH)
        assert projects.status_code == 200
        assert isinstance(projects.json()["items"], list)

        kpi = client.get("/api/v1/metrics/kpi", headers=AUTH)
        assert kpi.status_code == 200
        assert "kpi" in kpi.json()


def test_settings_patch() -> None:
    with TestClient(app) as client:
        update = client.patch(
            "/api/v1/settings",
            headers={**AUTH, "Idempotency-Key": f"settings-{uuid4()}"},
            json={"timezone": "Europe/Moscow", "queue_red_zone": 35},
        )
        assert update.status_code == 200
        assert update.json()["updated"] is True

        current = client.get("/api/v1/settings", headers=AUTH)
        assert current.status_code == 200
        assert current.json()["timezone"] == "Europe/Moscow"
