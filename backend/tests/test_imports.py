from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": f"idem-import-{uuid4()}"}


def test_import_upload_validation_error_for_empty_csv() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers(),
            files={"file": ("empty.csv", b"", "text/csv")},
            data={"dry_run": "true"},
        )
        assert response.status_code == 422


def test_imports_list_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/imports")
        assert response.status_code == 401
