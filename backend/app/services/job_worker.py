from __future__ import annotations

from datetime import datetime, timedelta
import json
from random import randint
from urllib.parse import urlparse
from urllib import error as urlerror
from urllib import request as urlrequest

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Campaign, CampaignMessage, Evidence, Job, Revision, StatusHistory, TaskAssignment


def _extract_json_path(payload: dict, path: str) -> object | None:
    normalized = path.strip()
    if not normalized.startswith("$."):
        return None
    parts = [p for p in normalized[2:].split(".") if p]
    current: object = payload
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def lease_next_job(db: Session, *, lease_seconds: int = 300) -> Job | None:
    now = datetime.utcnow()
    candidates = (
        db.query(Job)
        .filter(
            Job.status.in_(["queued", "running"]),
        )
        .order_by(Job.created_at.asc())
        .all()
    )
    for job in candidates:
        if job.status == "running" and job.lease_until and job.lease_until > now:
            continue
        job.status = "running"
        job.started_at = job.started_at or now
        job.lease_until = now + timedelta(seconds=lease_seconds)
        job.updated_at = now
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    return None


def _set_job_terminal(job: Job, *, status: str, result: dict | None = None, error: dict | None = None) -> None:
    job.status = status
    job.result = result
    job.error = error
    job.finished_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    job.lease_until = None


def _mark_sent(rows: list[CampaignMessage]) -> int:
    updated = 0
    for row in rows:
        row.status = "sent"
        row.email_sent_flag = True
        row.is_payload_immutable = True
        row.updated_at = datetime.utcnow()
        updated += 1
    return updated


def _run_http_verification(payload: dict) -> tuple[str, str, str | None, dict]:
    url = str(payload.get("url") or "").strip()
    if not url:
        return "rejected", "cannot_be_done", "HTTP_URL_REQUIRED", {"mode": "http_api", "attempts": 0}
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowlist = {x.strip().lower() for x in settings.verification_http_allowed_hosts.split(",") if x.strip()}
    if host not in allowlist:
        return (
            "rejected",
            "cannot_be_done",
            "HTTP_HOST_NOT_ALLOWED",
            {"mode": "http_api", "attempts": 0, "host": host, "allowlist": sorted(list(allowlist))},
        )
    method = str(payload.get("method") or "GET").upper()
    method_allowlist = {x.strip().upper() for x in settings.verification_http_allowed_methods.split(",") if x.strip()}
    if method not in method_allowlist:
        return (
            "rejected",
            "cannot_be_done",
            "HTTP_METHOD_NOT_ALLOWED",
            {"mode": "http_api", "attempts": 0, "method": method, "allowed_methods": sorted(list(method_allowlist))},
        )
    expected = int(payload.get("expected_status") or 200)
    timeout_seconds = float(payload.get("timeout_seconds") or 5)
    timeout_seconds = min(max(timeout_seconds, 0.1), settings.verification_http_max_timeout_seconds)
    retries = max(1, int(payload.get("retries") or 3))
    response_json_path = str(payload.get("response_json_path") or "").strip()
    has_expected_json_value = "expected_json_value" in payload
    expected_json_value = payload.get("expected_json_value")
    headers = payload.get("headers") or {}
    body = payload.get("body")
    encoded_body = None
    if body is not None:
        encoded_body = json.dumps(body).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}

    last_error: str | None = None
    last_status: int | None = None
    last_json_value: object | None = None
    for attempt in range(1, retries + 1):
        req = urlrequest.Request(url=url, method=method, data=encoded_body, headers=headers)
        try:
            with urlrequest.urlopen(req, timeout=timeout_seconds) as resp:
                last_status = resp.getcode()
                raw = resp.read()
            response_ok = last_status == expected
            if response_ok and response_json_path and has_expected_json_value:
                try:
                    parsed_body = json.loads(raw.decode() or "{}")
                    if not isinstance(parsed_body, dict):
                        parsed_body = {"data": parsed_body}
                    last_json_value = _extract_json_path(parsed_body, response_json_path)
                    response_ok = last_json_value == expected_json_value
                    if not response_ok:
                        last_error = "HTTP_JSON_CONDITION_FAILED"
                except Exception:  # noqa: BLE001
                    response_ok = False
                    last_error = "HTTP_JSON_PARSE_FAILED"
            if response_ok:
                return (
                    "verified",
                    "done",
                    None,
                    {
                        "mode": "http_api",
                        "attempts": attempt,
                        "response_status": last_status,
                        "timeout_seconds": timeout_seconds,
                        "response_json_path": response_json_path or None,
                        "actual_json_value": last_json_value,
                    },
                )
            if not last_error:
                last_error = "HTTP_STATUS_MISMATCH"
        except urlerror.HTTPError as exc:
            last_status = exc.code
            last_error = "HTTP_STATUS_MISMATCH"
        except urlerror.URLError:
            last_error = "HTTP_UNREACHABLE"
        except TimeoutError:
            last_error = "HTTP_TIMEOUT"
    return (
        "rejected",
        "cannot_be_done",
        last_error or "HTTP_FAILED",
        {
            "mode": "http_api",
            "attempts": retries,
            "response_status": last_status,
            "timeout_seconds": timeout_seconds,
            "response_json_path": response_json_path or None,
            "actual_json_value": last_json_value,
        },
    )


def _evaluate_verification_strategy(payload: dict) -> tuple[str, str, str | None, dict]:
    mode = str(payload.get("mode") or "manual").strip().lower()
    if mode == "manual":
        verification_status = str(payload.get("verification_status") or "verified")
        business_outcome = str(payload.get("business_outcome") or ("done" if verification_status == "verified" else "cannot_be_done"))
        technical_error_code = payload.get("technical_error_code")
    elif mode == "http_api":
        return _run_http_verification(payload)
    elif mode == "sql_query":
        row_count = int(payload.get("row_count") or 0)
        min_required = int(payload.get("min_required") or 1)
        verification_status = "verified" if row_count >= min_required else "rejected"
        business_outcome = "done" if verification_status == "verified" else "cannot_be_done"
        technical_error_code = None if verification_status == "verified" else "SQL_EMPTY_RESULT"
    elif mode == "file":
        exists = bool(payload.get("file_exists"))
        verification_status = "verified" if exists else "rejected"
        business_outcome = "done" if verification_status == "verified" else "cannot_be_done"
        technical_error_code = None if exists else "FILE_NOT_FOUND"
    elif mode == "webhook":
        received = bool(payload.get("webhook_received"))
        verification_status = "verified" if received else "rejected"
        business_outcome = "done" if verification_status == "verified" else "cannot_be_done"
        technical_error_code = None if received else "WEBHOOK_NOT_RECEIVED"
    else:
        verification_status = "rejected"
        business_outcome = "cannot_be_done"
        technical_error_code = "UNKNOWN_VERIFICATION_MODE"
    return verification_status, business_outcome, technical_error_code, {"mode": mode}


def _handle_assignment_verification(db: Session, job: Job) -> None:
    payload = job.payload or {}
    assignment_id = payload.get("assignment_id")
    verification_payload = payload.get("payload") or {}
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise ValueError("Assignment not found")

    verification_status, business_outcome, technical_error_code, meta = _evaluate_verification_strategy(verification_payload)

    db.add(
        Evidence(
            assignment_id=assignment.id,
            verification_status=verification_status,
            business_outcome=business_outcome,
            technical_error_code=technical_error_code,
            payload={"source": "assignment_action", **meta, **verification_payload},
        )
    )

    previous_status = assignment.status
    if verification_status == "verified":
        assignment.status = "done"
    elif verification_status in {"rejected", "failed"}:
        assignment.status = "blocked"
    else:
        assignment.status = "done_pending_check"

    if assignment.status != previous_status:
        db.add(
            StatusHistory(
                assignment_id=assignment.id,
                from_status=previous_status,
                to_status=assignment.status,
                reason="verification_result",
                actor_id="job-worker",
            )
        )
        assignment.revision += 1
        db.add(
            Revision(
                entity_type="task_assignment",
                entity_id=assignment.id,
                revision=assignment.revision,
                diff={
                    "before": {"status": previous_status},
                    "after": {"status": assignment.status},
                },
                actor_id="job-worker",
            )
        )
    assignment.updated_at = datetime.utcnow()
    db.add(assignment)
    _set_job_terminal(
        job,
        status="succeeded",
        result={
            "assignment_id": assignment.id,
            "verification_status": verification_status,
            "new_status": assignment.status,
        },
    )


def process_job(db: Session, job: Job) -> Job:
    try:
        if job.kind == "campaign_approve_send":
            campaign_id = (job.payload or {}).get("campaign_id")
            campaign = db.get(Campaign, campaign_id)
            if campaign is None:
                raise ValueError("Campaign not found")
            rows = db.query(CampaignMessage).filter(CampaignMessage.campaign_id == campaign_id).all()
            updated = _mark_sent(rows)
            campaign.status = "sent"
            campaign.updated_at = datetime.utcnow()
            db.add(campaign)
            for row in rows:
                db.add(row)
            _set_job_terminal(job, status="succeeded", result={"sent": updated})
        elif job.kind == "campaign_retry_failed":
            campaign_id = (job.payload or {}).get("campaign_id")
            rows = (
                db.query(CampaignMessage)
                .filter(CampaignMessage.campaign_id == campaign_id, CampaignMessage.status == "failed")
                .all()
            )
            updated = _mark_sent(rows)
            for row in rows:
                db.add(row)
            _set_job_terminal(job, status="succeeded", result={"retried": updated})
        elif job.kind == "assignment_action:run_verification":
            _handle_assignment_verification(db, job)
        else:
            _set_job_terminal(job, status="succeeded", result={"message": "no-op handler"})

        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:  # noqa: BLE001
        job.retry_count += 1
        job.last_retry_at = datetime.utcnow()
        max_attempts = 3
        if job.retry_count >= max_attempts:
            _set_job_terminal(
                job,
                status="failed",
                error={
                    "message": str(exc),
                    "retryable": False,
                    "correlation_id": f"job-{job.id}",
                },
            )
        else:
            # Fixed backoff + jitter (+/-20%) around 30s.
            jitter = randint(-6, 6)
            delay_seconds = 30 + jitter
            job.status = "queued"
            job.lease_until = datetime.utcnow() + timedelta(seconds=delay_seconds)
            job.error = {
                "message": str(exc),
                "retryable": True,
                "correlation_id": f"job-{job.id}",
            }
            job.updated_at = datetime.utcnow()
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
