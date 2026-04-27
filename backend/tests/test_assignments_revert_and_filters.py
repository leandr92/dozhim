from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _headers(idem: str) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": idem}


def test_assignments_filter_sort_and_revert() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/api/v1/assignments",
            headers=_headers(f"assignment-create-{uuid4()}"),
            json={
                "project_id": "system-project",
                "title": "Фильтр и revert",
                "target_object_external_key": f"manual-filter-{uuid4()}",
            },
        )
        assert create.status_code == 200
        assignment_id = create.json()["id"]

        details = client.get(f"/api/v1/assignments/{assignment_id}", headers={"Authorization": "Bearer test-token"})
        rev = details.json()["assignment"]["revision"]
        patch = client.patch(
            f"/api/v1/assignments/{assignment_id}",
            headers=_headers(f"assignment-patch-{uuid4()}"),
            json={"revision": rev, "progress_completion": 45, "progress_note": "patched"},
        )
        assert patch.status_code == 200

        filtered = client.get(
            "/api/v1/assignments?project_id=system-project&sort_by=created_at&sort_dir=desc&page=1&page_size=20",
            headers={"Authorization": "Bearer test-token"},
        )
        assert filtered.status_code == 200
        assert "items" in filtered.json()

        revert = client.post(
            f"/api/v1/assignments/{assignment_id}/revert",
            headers=_headers(f"assignment-revert-{uuid4()}"),
            json={"revision": patch.json()["revision"]},
        )
        assert revert.status_code == 200
        assert revert.json()["reverted"] is True
        details_after = client.get(f"/api/v1/assignments/{assignment_id}", headers={"Authorization": "Bearer test-token"})
        assert details_after.status_code == 200
        assert isinstance(details_after.json().get("touchpoints"), list)
        assert len(details_after.json()["touchpoints"]) >= 2
