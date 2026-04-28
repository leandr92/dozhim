from __future__ import annotations

from datetime import datetime, timedelta
import json
from random import randint
from urllib.parse import urlparse
from urllib import error as urlerror
from urllib import request as urlrequest

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Campaign, CampaignMessage, Evidence, Job, OperatorQueueItem, Person, Revision, StatusHistory, TaskAssignment, Touchpoint
from app.services.channels.email import send_email
from app.services.jobs import new_job_id as generate_job_id
from app.services.scheduling import next_action_after_touchpoint


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


def _touchpoint_count(db: Session, assignment_id: str) -> int:
    return db.query(Touchpoint).filter(Touchpoint.assignment_id == assignment_id).count()


def _add_touchpoint(
    db: Session,
    *,
    assignment_id: str,
    kind: str,
    channel: str = "system",
    payload: dict | None = None,
    actor_id: str = "job-worker",
) -> None:
    db.add(
        Touchpoint(
            assignment_id=assignment_id,
            channel=channel,
            kind=kind,
            payload=payload or {},
            actor_id=actor_id,
        )
    )


def _transition_assignment(
    db: Session,
    *,
    assignment: TaskAssignment,
    to_status: str,
    reason: str,
) -> None:
    previous_status = assignment.status
    if previous_status == to_status:
        return
    assignment.status = to_status
    assignment.revision += 1
    assignment.updated_at = datetime.utcnow()
    db.add(
        StatusHistory(
            assignment_id=assignment.id,
            from_status=previous_status,
            to_status=to_status,
            reason=reason,
            actor_id="job-worker",
        )
    )
    db.add(
        Revision(
            entity_type="task_assignment",
            entity_id=assignment.id,
            revision=assignment.revision,
            diff={"before": {"status": previous_status}, "after": {"status": to_status}},
            actor_id="job-worker",
        )
    )


def _upsert_call_task(
    db: Session,
    *,
    assignment: TaskAssignment,
    reason: str,
    queue_type: str = "call",
) -> OperatorQueueItem:
    existing = (
        db.query(OperatorQueueItem)
        .filter(
            OperatorQueueItem.assignment_id == assignment.id,
            OperatorQueueItem.type == queue_type,
            OperatorQueueItem.status.in_(["new", "in_progress"]),
        )
        .first()
    )
    if existing:
        return existing
    person = db.get(Person, assignment.assignee_person_id) if assignment.assignee_person_id else None
    payload = {
        "task_code": assignment.task_code,
        "deadline_at": assignment.deadline_at.isoformat() if assignment.deadline_at else None,
        "touchpoints_count": _touchpoint_count(db, assignment.id),
        "phone": person.phone if person else None,
    }
    item = OperatorQueueItem(
        assignment_id=assignment.id,
        type=queue_type,
        reason=reason,
        payload=payload,
        status="new",
    )
    db.add(item)
    return item


def _enqueue_email_for_assignment(
    db: Session,
    *,
    assignment: TaskAssignment,
    subject: str,
    body: str,
    to_email: str | None = None,
) -> None:
    recipient = (to_email or "").strip()
    if not recipient and assignment.assignee_person_id:
        person = db.get(Person, assignment.assignee_person_id)
        recipient = (person.email if person else "").strip()
    if not recipient:
        return
    db.add(
        Job(
            id=generate_job_id(),
            kind="channel:email_send",
            status="queued",
            payload={
                "assignment_id": assignment.id,
                "to_email": recipient,
                "subject": subject,
                "body": body,
            },
        )
    )


def _handle_assignment_action(db: Session, job: Job) -> None:
    payload = job.payload or {}
    assignment_id = payload.get("assignment_id")
    action = str(payload.get("action") or "").strip()
    action_payload = payload.get("payload") or {}
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise ValueError("Assignment not found")

    if action == "run_verification":
        _handle_assignment_verification(db, job)
        return

    if action == "send_first_message":
        _transition_assignment(db, assignment=assignment, to_status="notified", reason="send_first_message")
        _add_touchpoint(
            db,
            assignment_id=assignment.id,
            kind="channel_outbound_stub",
            payload={"action": action, "message": "first_message_sent"},
        )
        _enqueue_email_for_assignment(
            db,
            assignment=assignment,
            to_email=action_payload.get("to_email"),
            subject=f"[Dozhim] {assignment.task_code} — новое обязательство",
            body=action_payload.get("text") or assignment.title,
        )
        assignment.next_action_at = next_action_after_touchpoint(cadence_hours=24)
    elif action == "send_reminder":
        _add_touchpoint(
            db,
            assignment_id=assignment.id,
            kind="channel_reminder_stub",
            payload={"action": action},
        )
        _enqueue_email_for_assignment(
            db,
            assignment=assignment,
            to_email=action_payload.get("to_email"),
            subject=f"[Dozhim] Reminder {assignment.task_code}",
            body=action_payload.get("text") or f"Напоминание по задаче {assignment.title}",
        )
        assignment.next_action_at = next_action_after_touchpoint(cadence_hours=int(action_payload.get("cadence_hours") or 24))
    elif action in {"escalate", "next_escalation"}:
        assignment.escalation_level += 1
        target_status = "escalated" if assignment.status in {"overdue", "blocked", "escalated"} else assignment.status
        _transition_assignment(db, assignment=assignment, to_status=target_status, reason=f"action:{action}")
        _add_touchpoint(
            db,
            assignment_id=assignment.id,
            kind=f"action_{action}",
            payload={"escalation_level": assignment.escalation_level},
        )
        _enqueue_email_for_assignment(
            db,
            assignment=assignment,
            to_email=action_payload.get("to_email"),
            subject=f"[Dozhim] Escalation {assignment.task_code}",
            body=action_payload.get("text") or f"Эскалация уровня {assignment.escalation_level}",
        )
        if assignment.escalation_level >= int(action_payload.get("max_text_touches") or 3):
            _upsert_call_task(db, assignment=assignment, reason="escalation_threshold_reached")
    elif action == "create_call_task":
        person = db.get(Person, assignment.assignee_person_id) if assignment.assignee_person_id else None
        queue_type = "call" if person and person.phone else "data_quality_fix"
        reason = "manual_call_required" if queue_type == "call" else "missing_phone_number"
        _upsert_call_task(db, assignment=assignment, reason=reason, queue_type=queue_type)
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_create_call_task", payload={"queue_type": queue_type})
    elif action == "schedule_meeting":
        _upsert_call_task(db, assignment=assignment, reason="meeting_slot_not_implemented", queue_type="meeting_manual")
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_schedule_meeting")
    elif action == "mark_done_manual":
        _transition_assignment(db, assignment=assignment, to_status="done", reason="manual_done")
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_mark_done_manual")
    elif action == "request_clarification":
        _transition_assignment(db, assignment=assignment, to_status="in_progress", reason="request_clarification")
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_request_clarification")
    elif action == "unblock":
        _transition_assignment(db, assignment=assignment, to_status="in_progress", reason="unblock")
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_unblock")
    elif action == "request_data":
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_request_data", payload=action_payload)
        assignment.next_action_at = next_action_after_touchpoint(cadence_hours=24)
    elif action == "set_new_date":
        deadline_raw = action_payload.get("deadline_at")
        if isinstance(deadline_raw, str) and deadline_raw:
            assignment.deadline_at = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
        _transition_assignment(db, assignment=assignment, to_status="in_progress", reason="set_new_date")
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_set_new_date", payload=action_payload)
    elif action == "cancel":
        _transition_assignment(db, assignment=assignment, to_status="cancelled", reason="action_cancel")
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_cancel")
    elif action == "edit_task":
        if "title" in action_payload:
            assignment.title = str(action_payload.get("title") or assignment.title).strip() or assignment.title
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_edit_task", payload=action_payload)
    elif action == "edit_deadline":
        deadline_raw = action_payload.get("deadline_at")
        if isinstance(deadline_raw, str) and deadline_raw:
            assignment.deadline_at = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_edit_deadline", payload=action_payload)
    elif action == "update_progress":
        if "progress_completion" in action_payload:
            assignment.progress_completion = int(action_payload.get("progress_completion") or assignment.progress_completion)
        if "progress_note" in action_payload:
            assignment.progress_note = str(action_payload.get("progress_note") or assignment.progress_note)
        _add_touchpoint(db, assignment_id=assignment.id, kind="action_update_progress", payload=action_payload)
    else:
        raise ValueError(f"Unsupported assignment action: {action}")

    assignment.updated_at = datetime.utcnow()
    db.add(assignment)
    _set_job_terminal(
        job,
        status="succeeded",
        result={"assignment_id": assignment.id, "action": action, "status": assignment.status},
    )


def _handle_channel_email_send(db: Session, job: Job) -> None:
    payload = job.payload or {}
    assignment_id = payload.get("assignment_id")
    assignment = db.get(TaskAssignment, assignment_id) if assignment_id else None
    to_email = str(payload.get("to_email") or "").strip()
    subject = str(payload.get("subject") or "Dozhim notification").strip()
    body = str(payload.get("body") or "").strip()
    result = send_email(to_email=to_email, subject=subject, body=body)
    if assignment is not None:
        _add_touchpoint(
            db,
            assignment_id=assignment.id,
            channel="email",
            kind="email_outbound",
            payload=result,
        )
        assignment.updated_at = datetime.utcnow()
        db.add(assignment)
    _set_job_terminal(job, status="succeeded", result=result)


def _handle_daily_digest(db: Session, job: Job) -> None:
    overdue = db.query(TaskAssignment).filter(TaskAssignment.status == "overdue").count()
    no_reaction = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.status.in_(["new", "notified"]))
        .count()
    )
    call_tasks = (
        db.query(OperatorQueueItem)
        .filter(OperatorQueueItem.type == "call", OperatorQueueItem.status.in_(["new", "in_progress"]))
        .count()
    )
    pending_check = db.query(TaskAssignment).filter(TaskAssignment.status == "done_pending_check").count()
    digest_payload = {
        "overdue": overdue,
        "without_reaction": no_reaction,
        "new_call_tasks": call_tasks,
        "done_pending_check": pending_check,
    }
    recipient = (job.payload or {}).get("to_email")
    if recipient:
        send_email(
            to_email=str(recipient),
            subject="Dozhim daily digest",
            body=json.dumps(digest_payload, ensure_ascii=False, indent=2),
        )
    _set_job_terminal(job, status="succeeded", result=digest_payload)


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
        if technical_error_code and technical_error_code.startswith("HTTP_") and technical_error_code not in {"HTTP_HOST_NOT_ALLOWED", "HTTP_METHOD_NOT_ALLOWED"}:
            _upsert_call_task(db, assignment=assignment, reason="verification_manual_required", queue_type="verification_manual")
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
        elif job.kind in {"campaign_import", "compensation_rollback"}:
            _set_job_terminal(job, status="succeeded", result={"message": "handled"})
        elif job.kind.startswith("assignment_action:"):
            _handle_assignment_action(db, job)
        elif job.kind == "channel:email_send":
            _handle_channel_email_send(db, job)
        elif job.kind == "digest:daily":
            _handle_daily_digest(db, job)
        else:
            raise ValueError(f"Unsupported job kind: {job.kind}")

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
