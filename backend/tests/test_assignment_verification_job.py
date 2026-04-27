from fastapi.testclient import TestClient
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from time import sleep
from uuid import uuid4

from app.db.models import Project, TargetObject, TaskAssignment
from app.db.session import SessionLocal
from app.main import app


def _seed_assignment() -> str:
    db = SessionLocal()
    try:
        suffix = uuid4().hex[:8]
        project = Project(project_code=f"VRF-PROJ-{suffix}", project_name="Verification Project", status="active")
        db.add(project)
        db.flush()
        target = TargetObject(
            project_id=project.id,
            target_object_external_key=f"vrf-target-{suffix}",
            target_object_name="Verification Object",
        )
        db.add(target)
        db.flush()
        assignment = TaskAssignment(
            external_key=f"vrf-assignment-{suffix}",
            project_id=project.id,
            target_object_id=target.id,
            task_code=f"VRF-{suffix}",
            title="Verify status transition",
            status="in_progress",
            revision=1,
        )
        db.add(assignment)
        db.commit()
        return assignment.id
    finally:
        db.close()


def _run_until_status(client: TestClient, assignment_id: str, expected_status: str) -> dict:
    for _ in range(50):
        run_once = client.post(
            "/api/v1/jobs/run-once",
            headers={"Authorization": "Bearer test-token", "X-Role": "operator"},
        )
        assert run_once.status_code == 200
        details = client.get(
            f"/api/v1/assignments/{assignment_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert details.status_code == 200
        body = details.json()
        if body["assignment"]["status"] == expected_status:
            return body
    return body


def test_run_verification_action_changes_assignment_status() -> None:
    assignment_id = _seed_assignment()
    with TestClient(app) as client:
        action = client.post(
            f"/api/v1/assignments/{assignment_id}/actions",
            headers={
                "Authorization": "Bearer test-token",
                "X-Role": "operator",
                "Idempotency-Key": f"idem-verify-action-{uuid4()}",
            },
            json={
                "action": "run_verification",
                "revision": 1,
                "payload": {"verification_status": "verified", "business_outcome": "done"},
            },
        )
        assert action.status_code == 202

        body = _run_until_status(client, assignment_id, "done")
        assert body["assignment"]["status"] == "done"
        assert len(body["evidence"]) >= 1


def test_verification_strategies_modes() -> None:
    scenarios = [
        ("manual", {"mode": "manual", "verification_status": "verified", "business_outcome": "done"}, "done"),
        ("http_api", {"mode": "http_api", "expected_status": 200, "response_status": 500}, "blocked"),
        ("sql_query", {"mode": "sql_query", "row_count": 0, "min_required": 1}, "blocked"),
        ("file", {"mode": "file", "file_exists": True}, "done"),
        ("webhook", {"mode": "webhook", "webhook_received": False}, "blocked"),
    ]
    with TestClient(app) as client:
        for mode, payload, expected_status in scenarios:
            assignment_id = _seed_assignment()
            action = client.post(
                f"/api/v1/assignments/{assignment_id}/actions",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Role": "operator",
                    "Idempotency-Key": f"idem-verify-{mode}-{uuid4()}",
                },
                json={"action": "run_verification", "revision": 1, "payload": payload},
            )
            assert action.status_code == 202
            body = _run_until_status(client, assignment_id, expected_status)
            assert body["assignment"]["status"] == expected_status
            assert body["evidence"][0]["verification_status"] in {"verified", "rejected"}


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):  # noqa: A003
        return


class _JsonHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"result":{"status":"ok"}}')

    def log_message(self, format, *args):  # noqa: A003
        return


def test_http_api_live_call_strategy() -> None:
    server = HTTPServer(("127.0.0.1", 0), _OkHandler)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assignment_id = _seed_assignment()
        with TestClient(app) as client:
            action = client.post(
                f"/api/v1/assignments/{assignment_id}/actions",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Role": "operator",
                    "Idempotency-Key": f"idem-verify-http-live-{uuid4()}",
                },
                json={
                    "action": "run_verification",
                    "revision": 1,
                    "payload": {
                        "mode": "http_api",
                        "url": f"http://{host}:{port}/health",
                        "method": "GET",
                        "expected_status": 200,
                        "timeout_seconds": 2,
                        "retries": 2,
                    },
                },
            )
            assert action.status_code == 202
            body = _run_until_status(client, assignment_id, "done")
            assert body["assignment"]["status"] == "done"
            assert body["evidence"][0]["technical_error_code"] is None
    finally:
        server.shutdown()
        sleep(0.05)


def test_http_api_host_not_allowed() -> None:
    assignment_id = _seed_assignment()
    with TestClient(app) as client:
        action = client.post(
            f"/api/v1/assignments/{assignment_id}/actions",
            headers={
                "Authorization": "Bearer test-token",
                "X-Role": "operator",
                "Idempotency-Key": f"idem-verify-http-deny-{uuid4()}",
            },
            json={
                "action": "run_verification",
                "revision": 1,
                "payload": {
                    "mode": "http_api",
                    "url": "https://example.com/ping",
                    "method": "GET",
                    "expected_status": 200,
                },
            },
        )
        assert action.status_code == 202
        body = _run_until_status(client, assignment_id, "blocked")
        assert body["assignment"]["status"] == "blocked"
        assert body["evidence"][0]["technical_error_code"] == "HTTP_HOST_NOT_ALLOWED"


def test_http_api_method_not_allowed() -> None:
    assignment_id = _seed_assignment()
    with TestClient(app) as client:
        action = client.post(
            f"/api/v1/assignments/{assignment_id}/actions",
            headers={
                "Authorization": "Bearer test-token",
                "X-Role": "operator",
                "Idempotency-Key": f"idem-verify-http-method-{uuid4()}",
            },
            json={
                "action": "run_verification",
                "revision": 1,
                "payload": {
                    "mode": "http_api",
                    "url": "http://127.0.0.1:8000/api/v1/health",
                    "method": "DELETE",
                    "expected_status": 200,
                },
            },
        )
        assert action.status_code == 202
        body = _run_until_status(client, assignment_id, "blocked")
        assert body["assignment"]["status"] == "blocked"
        assert body["evidence"][0]["technical_error_code"] == "HTTP_METHOD_NOT_ALLOWED"


def test_http_api_json_path_business_condition() -> None:
    server = HTTPServer(("127.0.0.1", 0), _JsonHandler)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assignment_id = _seed_assignment()
        with TestClient(app) as client:
            action = client.post(
                f"/api/v1/assignments/{assignment_id}/actions",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Role": "operator",
                    "Idempotency-Key": f"idem-verify-http-json-{uuid4()}",
                },
                json={
                    "action": "run_verification",
                    "revision": 1,
                    "payload": {
                        "mode": "http_api",
                        "url": f"http://{host}:{port}/health",
                        "method": "GET",
                        "expected_status": 200,
                        "response_json_path": "$.result.status",
                        "expected_json_value": "ok",
                    },
                },
            )
            assert action.status_code == 202
            body = _run_until_status(client, assignment_id, "done")
            assert body["assignment"]["status"] == "done"
            assert body["evidence"][0]["technical_error_code"] is None
    finally:
        server.shutdown()
        sleep(0.05)


def test_http_api_json_path_business_condition_failed() -> None:
    server = HTTPServer(("127.0.0.1", 0), _JsonHandler)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assignment_id = _seed_assignment()
        with TestClient(app) as client:
            action = client.post(
                f"/api/v1/assignments/{assignment_id}/actions",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Role": "operator",
                    "Idempotency-Key": f"idem-verify-http-json-fail-{uuid4()}",
                },
                json={
                    "action": "run_verification",
                    "revision": 1,
                    "payload": {
                        "mode": "http_api",
                        "url": f"http://{host}:{port}/health",
                        "method": "GET",
                        "expected_status": 200,
                        "response_json_path": "$.result.status",
                        "expected_json_value": "not-ok",
                    },
                },
            )
            assert action.status_code == 202
            body = _run_until_status(client, assignment_id, "blocked")
            assert body["assignment"]["status"] == "blocked"
            assert body["evidence"][0]["technical_error_code"] == "HTTP_JSON_CONDITION_FAILED"
    finally:
        server.shutdown()
        sleep(0.05)
