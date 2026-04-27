from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _headers(idem: str = "idem-queue") -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "Idempotency-Key": f"{idem}-{uuid4()}"}


def test_operator_queue_flow() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/api/v1/operator-queue/inbound-unmatched",
            headers=_headers("idem-create-queue"),
            json={"reason": "no_assignment_match", "message": "text"},
        )
        assert create.status_code == 200
        item_id = create.json()["id"]

        listing = client.get("/api/v1/operator-queue", headers={"Authorization": "Bearer test-token"})
        assert listing.status_code == 200
        assert listing.json()["total"] >= 1

        claim = client.post(
            f"/api/v1/operator-queue/{item_id}/claim",
            headers=_headers("idem-claim"),
        )
        assert claim.status_code == 200
        assert claim.json()["status"] == "in_progress"

        resolve = client.post(
            f"/api/v1/operator-queue/{item_id}/resolve",
            headers=_headers("idem-resolve"),
            json={"result": "handled"},
        )
        assert resolve.status_code == 200
        assert resolve.json()["status"] == "resolved"

        follow_up = client.post(
            f"/api/v1/operator-queue/{item_id}/follow-up",
            headers=_headers("idem-follow-up"),
            json={"reason": "second-touch"},
        )
        assert follow_up.status_code == 200
        assert follow_up.json()["status"] == "new"


def test_bind_queue_item_to_assignment() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/api/v1/operator-queue/inbound-unmatched",
            headers=_headers("idem-create-bind"),
            json={"reason": "no_assignment_match"},
        )
        item_id = create.json()["id"]
        # create assignment through import/apply
        header = (
            "Дирекция,Проект,Статус КТ,Количество КТ,Количество этапов,РП,Куратор,Последнее изменение,"
            "Ссылка КТ,Ссылка на проект,Статус проекта в КТ,Статус согласования\n"
        )
        row = "IT,Проект D,open,1,1,user4@example.com,curator,2026-01-01,url1,key-d,active,ok\n"
        client.post(
            "/api/v1/campaigns/personalized/upload",
            headers=_headers("idem-upload-bind"),
            files={"file": ("import.csv", (header + row).encode("utf-8"), "text/csv")},
            data={"dry_run": "true"},
        )
        imports = client.get("/api/v1/imports", headers={"Authorization": "Bearer test-token"}).json()["items"]
        client.post(f"/api/v1/imports/{imports[0]['id']}/apply", headers=_headers("idem-apply-bind"))
        assignment_id = client.get("/api/v1/assignments", headers={"Authorization": "Bearer test-token"}).json()["items"][0]["id"]
        bind = client.post(
            f"/api/v1/operator-queue/{item_id}/bind-assignment",
            headers=_headers("idem-bind"),
            json={"assignment_id": assignment_id},
        )
        assert bind.status_code == 200
        assert bind.json()["assignment_id"] == assignment_id
