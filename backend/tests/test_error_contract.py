from fastapi.testclient import TestClient

from app.main import app


def test_error_contract_for_404() -> None:
    with TestClient(app) as client:
        res = client.get(
            "/api/v1/assignments/not-found-id",
            headers={"Authorization": "Bearer test-token", "X-Correlation-ID": "corr-123"},
        )
        assert res.status_code == 404
        payload = res.json()
        assert payload["code"] == "HTTP_404"
        assert payload["retryable"] is False
        assert payload["correlation_id"] == "corr-123"
        assert payload["severity"] == "warning"
        assert "message" in payload
        assert "details" in payload
