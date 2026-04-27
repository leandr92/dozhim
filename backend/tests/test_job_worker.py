from fastapi.testclient import TestClient
from uuid import uuid4
from uuid import uuid4

from app.main import app


def _headers(idem: str = "idem-worker") -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": f"{idem}-{uuid4()}"}


def _valid_csv() -> bytes:
    header = (
        "Дирекция,Проект,Статус КТ,Количество КТ,Количество этапов,РП,Куратор,Последнее изменение,"
        "Ссылка КТ,Ссылка на проект,Статус проекта в КТ,Статус согласования\n"
    )
    row = "IT,Проект B,open,1,1,worker@example.com,curator,2026-01-01,url1,key-b,active,ok\n"
    return (header + row).encode("utf-8")


def test_run_once_processes_job() -> None:
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers(f"idem-upload-worker-{uuid4()}"),
            files={"file": ("import.csv", _valid_csv(), "text/csv")},
            data={"dry_run": "true"},
        )
        assert upload.status_code == 202

        campaigns = client.get("/api/v1/campaigns", headers={"Authorization": "Bearer test-token"})
        campaign_id = campaigns.json()["items"][0]["id"]
        approve = client.post(
            f"/api/v1/campaigns/{campaign_id}/approve-send",
            headers=_headers(f"idem-approve-worker-{uuid4()}"),
        )
        assert approve.status_code == 202

        run_once = client.post("/api/v1/jobs/run-once", headers={"Authorization": "Bearer test-token"})
        assert run_once.status_code == 200
        assert "processed" in run_once.json()
