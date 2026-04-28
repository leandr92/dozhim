from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AppSetting, Job, TaskAssignment
from app.db.session import SessionLocal
from app.services.job_worker import lease_next_job, process_job
from app.services.jobs import new_job_id as generate_job_id


def _schedule_due_assignments(db: Session, *, batch_size: int = 20) -> int:
    now = datetime.utcnow()
    due_rows = (
        db.query(TaskAssignment)
        .filter(
            TaskAssignment.next_action_at.isnot(None),
            TaskAssignment.next_action_at <= now,
            TaskAssignment.status.in_(["new", "notified", "acknowledged", "in_progress", "overdue", "escalated"]),
        )
        .order_by(TaskAssignment.next_action_at.asc())
        .limit(batch_size)
        .all()
    )
    scheduled = 0
    for assignment in due_rows:
        pending_rows = (
            db.query(Job)
            .filter(
                Job.kind == "assignment_action:send_reminder",
                Job.status.in_(["queued", "running"]),
            )
            .all()
        )
        has_pending = any((row.payload or {}).get("assignment_id") == assignment.id for row in pending_rows)
        if has_pending:
            continue
        db.add(
            Job(
                id=generate_job_id(),
                kind="assignment_action:send_reminder",
                status="queued",
                payload={"assignment_id": assignment.id, "action": "send_reminder", "payload": {"cadence_hours": 24}},
            )
        )
        scheduled += 1
    if scheduled:
        db.commit()
    return scheduled


def _schedule_daily_digest(db: Session) -> int:
    settings_row = db.get(AppSetting, "global")
    settings_value = settings_row.value if settings_row else {}
    recipients = settings_value.get("digest_recipients") or []
    digest_hour = int(settings_value.get("digest_hour_utc") or 6)
    now = datetime.utcnow()
    if now.hour < digest_hour or not recipients:
        return 0
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    already = (
        db.query(Job)
        .filter(Job.kind == "digest:daily", Job.created_at >= day_start)
        .count()
    )
    if already > 0:
        return 0
    for recipient in recipients:
        db.add(
            Job(
                id=generate_job_id(),
                kind="digest:daily",
                status="queued",
                payload={"to_email": recipient},
            )
        )
    db.commit()
    return len(recipients)


def run_background_loop(poll_interval_seconds: int = 2, max_cycles: int | None = None) -> None:
    cycles = 0
    while True:
        with SessionLocal() as db:  # type: Session
            job = lease_next_job(db)
            if job is not None:
                process_job(db, job)
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            return
        time.sleep(poll_interval_seconds)


def run_once_with_summary() -> dict:
    with SessionLocal() as db:  # type: Session
        scheduled_due = _schedule_due_assignments(db)
        scheduled_digest = _schedule_daily_digest(db)
        job = lease_next_job(db)
        if job is None:
            return {
                "processed": False,
                "scheduled_due": scheduled_due,
                "scheduled_digest": scheduled_digest,
                "message": "No available jobs",
            }
        updated = process_job(db, job)
        return {
            "processed": True,
            "scheduled_due": scheduled_due,
            "scheduled_digest": scheduled_digest,
            "job_id": updated.id,
            "status": updated.status,
            "processed_at": datetime.utcnow().isoformat(),
        }
