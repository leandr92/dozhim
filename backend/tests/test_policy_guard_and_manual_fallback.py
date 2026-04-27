from fastapi.testclient import TestClient

from app.main import app


def _headers(idem: str = "idem-guard") -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": idem}


def _valid_csv() -> bytes:
    header = (
        "Дирекция,Проект,Статус КТ,Количество КТ,Количество этапов,РП,Куратор,Последнее изменение,"
        "Ссылка КТ,Ссылка на проект,Статус проекта в КТ,Статус согласования\n"
    )
    row = "IT,Проект C,open,1,1,user3@example.com,curator,2026-01-01,url1,key-c,active,ok\n"
    return (header + row).encode("utf-8")


def test_policy_guard_blocks_unknown_action() -> None:
    with TestClient(app) as client:
        # prepare one assignment
        upload = client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers("idem-upload-guard"),
            files={"file": ("import.csv", _valid_csv(), "text/csv")},
            data={"dry_run": "true"},
        )
        assert upload.status_code == 202
        # apply latest import
        imports = client.get("/api/v1/imports", headers={"Authorization": "Bearer test-token"}).json()["items"]
        client.post(
            f"/api/v1/imports/{imports[0]['id']}/apply",
            headers=_headers("idem-apply-guard"),
        )
        assignments = client.get("/api/v1/assignments", headers={"Authorization": "Bearer test-token"}).json()["items"]
        assignment = assignments[0]
        response = client.post(
            f"/api/v1/assignments/{assignment['id']}/actions",
            headers=_headers("idem-action-guard"),
            json={"action": "unknown_action", "revision": assignment["revision"], "payload": {}},
        )
        assert response.status_code == 422


def test_manual_sent_flag_requires_comment() -> None:
    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers("idem-upload-manual"),
            files={"file": ("import.csv", _valid_csv(), "text/csv")},
            data={"dry_run": "true"},
        )
        assert upload.status_code == 202
        campaign_id = client.get("/api/v1/campaigns", headers={"Authorization": "Bearer test-token"}).json()["items"][0]["id"]
        msg_id = client.get(
            f"/api/v1/campaigns/{campaign_id}/messages",
            headers={"Authorization": "Bearer test-token"},
        ).json()["items"][0]["id"]

        bad = client.post(
            f"/api/v1/campaigns/{campaign_id}/messages/{msg_id}/manual-sent-flag",
            headers=_headers("idem-manual-bad"),
            json={"comment": ""},
        )
        assert bad.status_code == 422

        good = client.post(
            f"/api/v1/campaigns/{campaign_id}/messages/{msg_id}/manual-sent-flag",
            headers=_headers("idem-manual-good"),
            json={"comment": "fallback via outlook"},
        )
        assert good.status_code == 200
