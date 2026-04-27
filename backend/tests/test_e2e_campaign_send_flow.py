from fastapi.testclient import TestClient

from app.main import app


def _headers(idem: str = "idem-e2e") -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": idem}


def _valid_csv() -> bytes:
    header = (
        "Дирекция,Проект,Статус КТ,Количество КТ,Количество этапов,РП,Куратор,Последнее изменение,"
        "Ссылка КТ,Ссылка на проект,Статус проекта в КТ,Статус согласования\n"
    )
    row = "IT,Проект Z,open,1,1,e2e@example.com,curator,2026-01-01,url1,key-z,active,ok\n"
    return (header + row).encode("utf-8")


def test_e2e_upload_preview_approve_run_worker_sent() -> None:
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers("idem-e2e-upload"),
            files={"file": ("import.csv", _valid_csv(), "text/csv")},
            data={"dry_run": "true"},
        )
        assert upload.status_code == 202

        imports_resp = client.get("/api/v1/imports", headers={"Authorization": "Bearer test-token"})
        assert imports_resp.status_code == 200
        latest_import_id = imports_resp.json()["items"][0]["id"]

        campaigns_resp = client.get("/api/v1/campaigns", headers={"Authorization": "Bearer test-token"})
        assert campaigns_resp.status_code == 200
        campaign = next((c for c in campaigns_resp.json()["items"] if c["import_id"] == latest_import_id), None)
        assert campaign is not None
        campaign_id = campaign["id"]

        preview = client.get(
            f"/api/v1/campaigns/{campaign_id}/messages",
            headers={"Authorization": "Bearer test-token"},
        )
        assert preview.status_code == 200
        msg = preview.json()["items"][0]

        save = client.patch(
            f"/api/v1/campaigns/{campaign_id}/messages/{msg['id']}",
            headers=_headers("idem-e2e-save"),
            json={
                "subject": "E2E subject",
                "body": "E2E body",
                "to_email": "e2e@example.com",
                "cc_emails": []
            },
        )
        assert save.status_code == 200

        approve = client.post(
            f"/api/v1/campaigns/{campaign_id}/approve-send",
            headers=_headers("idem-e2e-approve"),
        )
        assert approve.status_code == 202

        # There can be multiple queued jobs from previous tests; process until target message is sent.
        for _ in range(50):
            run_once = client.post("/api/v1/jobs/run-once", headers={"Authorization": "Bearer test-token"})
            assert run_once.status_code == 200
            check = client.get(
                f"/api/v1/campaigns/{campaign_id}/messages",
                headers={"Authorization": "Bearer test-token"},
            )
            item = next((x for x in check.json()["items"] if x["id"] == msg["id"]), None)
            if item and item["status"] == "sent":
                break

        sent_check = client.get(
            f"/api/v1/campaigns/{campaign_id}/messages",
            headers={"Authorization": "Bearer test-token"},
        )
        assert sent_check.status_code == 200
        sent_item = next((x for x in sent_check.json()["items"] if x["id"] == msg["id"]), None)
        assert sent_item is not None
        assert sent_item["status"] == "sent"
        assert sent_item["email_sent_flag"] is True
        assert sent_item["is_payload_immutable"] is True
