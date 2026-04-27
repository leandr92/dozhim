from fastapi.testclient import TestClient

from app.main import app


def _headers(idem: str) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": idem}


def test_manual_create_and_delete_assignment() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/api/v1/assignments",
            headers=_headers("assignment-create-1"),
            json={
                "project_id": "system-project",
                "title": "Ручная задача для проверки",
                "target_object_external_key": "manual-object-1",
                "target_object_name": "Manual Object 1",
            },
        )
        assert create.status_code == 200
        payload = create.json()
        assert payload["created"] is True
        assignment_id = payload["id"]

        listing = client.get("/api/v1/assignments", headers={"Authorization": "Bearer test-token"})
        assert listing.status_code == 200
        ids = {item["id"] for item in listing.json()["items"]}
        assert assignment_id in ids

        remove = client.delete(
            f"/api/v1/assignments/{assignment_id}",
            headers=_headers("assignment-delete-1"),
        )
        assert remove.status_code == 200
        assert remove.json()["deleted"] is True

        details = client.get(
            f"/api/v1/assignments/{assignment_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert details.status_code == 404
