from fastapi.testclient import TestClient

from app.main import app


def _headers(idem: str = "idem-campaign") -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": idem}


def _valid_csv() -> bytes:
    header = (
        "Дирекция,Проект,Статус КТ,Количество КТ,Количество этапов,РП,Куратор,Последнее изменение,"
        "Ссылка КТ,Ссылка на проект,Статус проекта в КТ,Статус согласования\n"
    )
    row = "IT,Проект А,open,1,1,user@example.com,curator,2026-01-01,url1,key-a,active,ok\n"
    return (header + row).encode("utf-8")


def test_campaign_preview_edit_flow() -> None:
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers("idem-upload"),
            files={"file": ("import.csv", _valid_csv(), "text/csv")},
            data={"dry_run": "true"},
        )
        assert upload.status_code == 202

        campaigns = client.get("/api/v1/campaigns", headers={"Authorization": "Bearer test-token"})
        assert campaigns.status_code == 200
        assert campaigns.json()["total"] >= 1
        campaign_id = campaigns.json()["items"][0]["id"]

        messages = client.get(
            f"/api/v1/campaigns/{campaign_id}/messages",
            headers={"Authorization": "Bearer test-token"},
        )
        assert messages.status_code == 200
        message_id = messages.json()["items"][0]["id"]

        save = client.patch(
            f"/api/v1/campaigns/{campaign_id}/messages/{message_id}",
            headers=_headers("idem-save"),
            json={
                "subject": "Новая тема",
                "body": "Новое тело",
                "to_email": "user@example.com",
                "cc_emails": ["copy@example.com"]
            },
        )
        assert save.status_code == 200

        approve = client.post(
            f"/api/v1/campaigns/{campaign_id}/approve-send",
            headers=_headers("idem-approve"),
        )
        assert approve.status_code == 202

        retry = client.post(
            f"/api/v1/campaigns/{campaign_id}/retry-failed",
            headers=_headers("idem-retry"),
        )
        assert retry.status_code == 202
