from fastapi.testclient import TestClient

from app.main import app


def _headers(idem: str = "idem-jobs") -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": idem}


def _valid_csv() -> bytes:
    header = (
        "Дирекция,Проект,Статус КТ,Количество КТ,Количество этапов,РП,Куратор,Последнее изменение,"
        "Ссылка КТ,Ссылка на проект,Статус проекта в КТ,Статус согласования\n"
    )
    row = "IT,Проект E,open,1,1,user5@example.com,curator,2026-01-01,url1,key-e,active,ok\n"
    return (header + row).encode("utf-8")


def test_allowed_actions_endpoint() -> None:
    with TestClient(app) as client:
        client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers("idem-upload-allowed"),
            files={"file": ("import.csv", _valid_csv(), "text/csv")},
            data={"dry_run": "true"},
        )
        imports = client.get("/api/v1/imports", headers={"Authorization": "Bearer test-token"}).json()["items"]
        client.post(f"/api/v1/imports/{imports[0]['id']}/apply", headers=_headers("idem-apply-allowed"))
        assignment_id = client.get("/api/v1/assignments", headers={"Authorization": "Bearer test-token"}).json()["items"][0]["id"]
        allowed = client.get(
            f"/api/v1/assignments/{assignment_id}/actions/allowed",
            headers={"Authorization": "Bearer test-token"},
        )
        assert allowed.status_code == 200
        assert "allowed_actions" in allowed.json()


def test_retry_job_endpoint() -> None:
    with TestClient(app) as client:
        # create failed job by canceling and retrying from terminal state
        upload = client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers("idem-upload-retry-job"),
            files={"file": ("import.csv", _valid_csv(), "text/csv")},
            data={"dry_run": "true"},
        )
        assert upload.status_code == 202
        job_location = upload.headers.get("Location")
        assert job_location
        job_id = job_location.rsplit("/", 1)[-1]
        cancel = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=_headers("idem-cancel-job"))
        assert cancel.status_code == 202

        retry = client.post(f"/api/v1/jobs/{job_id}/retry", headers=_headers("idem-retry-job"))
        assert retry.status_code == 202
        assert "job_id" in retry.json()
