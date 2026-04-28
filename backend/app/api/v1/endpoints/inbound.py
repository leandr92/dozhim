from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Job, OperatorQueueItem, StatusHistory, TaskAssignment, Touchpoint
from app.db.session import get_db
from app.services.jobs import new_job_id as generate_job_id
from app.services.inbound_commands import map_command_to_status, parse_inbound_text

router = APIRouter(prefix="/inbound", tags=["inbound"])


@router.post("/email")
def inbound_email(
    payload: dict,
    x_service_token: str = Header(alias="X-Service-Token"),
    db: Session = Depends(get_db),
) -> dict:
    if x_service_token != settings.inbound_service_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")

    text = str(payload.get("text") or payload.get("body") or "").strip()
    parsed = parse_inbound_text(text)
    if parsed is None:
        item = OperatorQueueItem(
            assignment_id=None,
            type="inbound_unmatched",
            reason="cannot_parse_inbound_email",
            payload={"raw_text": text, "from_email": payload.get("from_email")},
            status="new",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"created_queue_item_id": item.id, "status": "queued_manual_review"}

    assignment = db.query(TaskAssignment).filter(TaskAssignment.task_code == parsed.task_code).first()
    if assignment is None:
        item = OperatorQueueItem(
            assignment_id=None,
            type="inbound_unmatched",
            reason="task_code_not_found",
            payload={"task_code": parsed.task_code, "raw_text": text, "from_email": payload.get("from_email")},
            status="new",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"created_queue_item_id": item.id, "status": "task_code_not_found"}

    to_status, command_payload = map_command_to_status(parsed, assignment.status)
    previous_status = assignment.status
    assignment.status = to_status
    assignment.updated_at = datetime.utcnow()
    assignment.revision += 1
    if command_payload.get("next_commitment_date"):
        assignment.next_commitment_date = datetime.fromisoformat(str(command_payload["next_commitment_date"])).date()
    db.add(assignment)
    db.add(
        StatusHistory(
            assignment_id=assignment.id,
            from_status=previous_status,
            to_status=to_status,
            reason=f"inbound_email:{parsed.command}",
            actor_id="inbound-email",
        )
    )
    db.add(
        Touchpoint(
            assignment_id=assignment.id,
            channel="email",
            kind="email_inbound",
            payload={"command": parsed.command, **command_payload},
            actor_id="inbound-email",
        )
    )
    verification_job_id = None
    if parsed.command == "DONE":
        verification_job_id = generate_job_id()
        db.add(
            Job(
                id=verification_job_id,
                kind="assignment_action:run_verification",
                status="queued",
                payload={"assignment_id": assignment.id, "action": "run_verification", "payload": {"mode": "manual", "verification_status": "verified"}},
            )
        )
    db.commit()
    return {
        "assignment_id": assignment.id,
        "task_code": parsed.task_code,
        "status": assignment.status,
        "verification_job_id": verification_job_id,
    }
