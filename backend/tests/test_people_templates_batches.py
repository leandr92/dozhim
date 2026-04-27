from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _headers(idem: str, role: str = "operator") -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "Idempotency-Key": idem,
        "X-Role": role,
    }


def test_people_templates_batches_flow() -> None:
    with TestClient(app) as client:
        person = client.post(
            "/api/v1/people",
            headers=_headers(f"people-create-{uuid4()}"),
            json={
                "full_name": "Иван Петров",
                "email": f"ivan.petrov.{uuid4()}@example.com",
                "phone": "+79991234567",
                "role": "executor",
            },
        )
        assert person.status_code == 200
        person_id = person.json()["id"]

        patch_person = client.patch(
            f"/api/v1/people/{person_id}",
            headers=_headers(f"people-patch-{uuid4()}"),
            json={"telegram_user_id": "ivan_petrov"},
        )
        assert patch_person.status_code == 200

        template = client.post(
            "/api/v1/templates",
            headers=_headers(f"template-create-{uuid4()}"),
            json={
                "name": f"weekly-followup-{uuid4()}",
                "title_template": "Напоминание для {person_name}",
                "default_deadline_days": 5,
                "verification_policy": {"method": "manual"},
                "escalation_policy": {"max_touches": 3},
                "calendar_policy": {"timezone": "Europe/Moscow"},
            },
        )
        assert template.status_code == 200
        template_id = template.json()["id"]

        create_batch = client.post(
            "/api/v1/batches",
            headers=_headers(f"batch-create-{uuid4()}"),
            json={
                "project_id": "system-project",
                "template_id": template_id,
                "name": "Пилотный batch",
                "people_ids": [person_id],
            },
        )
        assert create_batch.status_code == 200
        batch_id = create_batch.json()["id"]

        batch = client.get(f"/api/v1/batches/{batch_id}", headers={"Authorization": "Bearer test-token"})
        assert batch.status_code == 200
        assert batch.json()["status"] == "succeeded"

        retry_batch = client.post(
            f"/api/v1/batches/{batch_id}/retry",
            headers=_headers(f"batch-retry-{uuid4()}"),
        )
        assert retry_batch.status_code == 200
        assert retry_batch.json()["status"] == "succeeded"
