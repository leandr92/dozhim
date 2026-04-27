from datetime import datetime
from hashlib import sha1
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import require_bearer_token, require_roles
from app.db.models import CampaignMessage, Evidence, Job, OperatorQueueItem, Project, Revision, StatusHistory, TargetObject, TaskAssignment
from app.db.session import get_db
from app.schemas.assignments import AssignmentActionRequest, AssignmentCreate, AssignmentPatch
from app.schemas.common import JobAccepted
from app.services.jobs import new_job_id as generate_job_id
from app.services.state_machine import assert_transition

router = APIRouter(prefix="/assignments", tags=["assignments"])

ALLOWED_ACTIONS_BY_STATUS: dict[str, set[str]] = {
    "new": {"send_first_message", "edit_task", "cancel"},
    "notified": {"send_reminder", "edit_deadline", "escalate"},
    "acknowledged": {"send_reminder", "edit_deadline", "escalate"},
    "in_progress": {"send_reminder", "run_verification", "update_progress"},
    "done_pending_check": {"run_verification", "mark_done_manual", "request_clarification"},
    "overdue": {"escalate", "schedule_meeting", "create_call_task"},
    "escalated": {"next_escalation", "schedule_meeting", "create_call_task"},
    "blocked": {"unblock", "request_data", "set_new_date"},
}


def _manual_assignment_external_key(project_id: str, target_object_external_key: str) -> str:
    raw = f"{project_id}:{target_object_external_key}:manual:{uuid4()}"
    return sha1(raw.encode("utf-8")).hexdigest()


def _task_code() -> str:
    return f"T-{str(uuid4())[:8].upper()}"


@router.get("")
def list_assignments(
    page: int = 1,
    page_size: int = 50,
    project_id: str | None = None,
    target_object_id: str | None = None,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(TaskAssignment)
    if project_id:
        query = query.filter(TaskAssignment.project_id == project_id)
    if target_object_id:
        query = query.filter(TaskAssignment.target_object_id == target_object_id)

    total = query.count()
    rows = (
        query.order_by(TaskAssignment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "title": row.title,
                "status": row.status,
                "project_id": row.project_id,
                "target_object_id": row.target_object_id,
                "deadline_at": row.deadline_at,
                "revision": row.revision,
            }
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "filters": {
            "project_id": project_id,
            "target_object_id": target_object_id,
        },
    }


@router.post("")
def create_assignment(
    payload: AssignmentCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")

    project = db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    ext_key = payload.target_object_external_key.strip()
    target_name = (payload.target_object_name or ext_key).strip()
    target = (
        db.query(TargetObject)
        .filter(
            TargetObject.project_id == payload.project_id,
            TargetObject.target_object_external_key == ext_key,
        )
        .first()
    )
    if target is None:
        target = TargetObject(
            project_id=payload.project_id,
            target_object_external_key=ext_key,
            target_object_name=target_name,
        )
        db.add(target)
        db.flush()

    assignment = TaskAssignment(
        external_key=_manual_assignment_external_key(payload.project_id, ext_key),
        project_id=payload.project_id,
        target_object_id=target.id,
        task_code=_task_code(),
        title=payload.title.strip(),
        status="new",
        deadline_at=payload.deadline_at,
        progress_completion=0,
    )
    db.add(assignment)
    db.flush()
    db.add(
        StatusHistory(
            assignment_id=assignment.id,
            from_status=None,
            to_status="new",
            reason="manual_create",
            actor_id="api-user",
        )
    )
    db.commit()
    return {"id": assignment.id, "task_code": assignment.task_code, "created": True}


@router.get("/{assignment_id}/actions/allowed")
def get_allowed_assignment_actions(
    assignment_id: str,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    allowed = sorted(list(ALLOWED_ACTIONS_BY_STATUS.get(assignment.status, set())))
    return {"assignment_id": assignment_id, "status": assignment.status, "allowed_actions": allowed}


@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    db.query(StatusHistory).filter(StatusHistory.assignment_id == assignment_id).delete(synchronize_session=False)
    db.query(Evidence).filter(Evidence.assignment_id == assignment_id).delete(synchronize_session=False)
    db.query(CampaignMessage).filter(CampaignMessage.assignment_id == assignment_id).update(
        {"assignment_id": None}, synchronize_session=False
    )
    db.query(OperatorQueueItem).filter(OperatorQueueItem.assignment_id == assignment_id).update(
        {"assignment_id": None}, synchronize_session=False
    )
    db.query(Revision).filter(Revision.entity_type == "task_assignment", Revision.entity_id == assignment_id).delete(
        synchronize_session=False
    )
    db.delete(assignment)
    db.commit()
    return {"id": assignment_id, "deleted": True}


@router.patch("/{assignment_id}")
def patch_assignment(
    assignment_id: str,
    payload: AssignmentPatch,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if assignment.revision != payload.revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CONFLICT_EDIT")

    previous_status = assignment.status
    before = {
        "status": assignment.status,
        "deadline_at": assignment.deadline_at.isoformat() if assignment.deadline_at else None,
        "progress_completion": assignment.progress_completion,
        "progress_note": assignment.progress_note,
        "next_commitment_date": assignment.next_commitment_date.isoformat() if assignment.next_commitment_date else None,
    }
    if payload.status and payload.status != assignment.status:
        try:
            assert_transition(assignment.status, payload.status, policy_enabled=True)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        assignment.status = payload.status
        db.add(
            StatusHistory(
                assignment_id=assignment.id,
                from_status=previous_status,
                to_status=payload.status,
                reason="manual_patch",
                actor_id="api-user",
            )
        )

    if payload.deadline_at is not None:
        assignment.deadline_at = payload.deadline_at
    if payload.progress_completion is not None:
        assignment.progress_completion = payload.progress_completion
    if payload.progress_note is not None:
        assignment.progress_note = payload.progress_note
    if payload.next_commitment_date is not None:
        assignment.next_commitment_date = payload.next_commitment_date

    assignment.revision += 1
    assignment.updated_at = datetime.utcnow()
    db.add(assignment)
    db.add(
        Revision(
            entity_type="task_assignment",
            entity_id=assignment.id,
            revision=assignment.revision,
            diff={
                "before": before,
                "after": {
                    "status": assignment.status,
                    "deadline_at": assignment.deadline_at.isoformat() if assignment.deadline_at else None,
                    "progress_completion": assignment.progress_completion,
                    "progress_note": assignment.progress_note,
                    "next_commitment_date": assignment.next_commitment_date.isoformat() if assignment.next_commitment_date else None,
                },
            },
            actor_id="api-user",
        )
    )
    db.commit()
    db.refresh(assignment)
    return {"assignment_id": assignment_id, "updated": True, "revision": assignment.revision}


@router.get("/{assignment_id}")
def get_assignment_details(
    assignment_id: str,
    _token: str = Depends(require_bearer_token),
    db: Session = Depends(get_db),
) -> dict:
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    history = (
        db.query(StatusHistory)
        .filter(StatusHistory.assignment_id == assignment_id)
        .order_by(StatusHistory.created_at.desc())
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.assignment_id == assignment_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )
    revisions = (
        db.query(Revision)
        .filter(Revision.entity_type == "task_assignment", Revision.entity_id == assignment_id)
        .order_by(Revision.revision.desc())
        .all()
    )

    return {
        "assignment": {
            "id": assignment.id,
            "task_code": assignment.task_code,
            "title": assignment.title,
            "status": assignment.status,
            "project_id": assignment.project_id,
            "target_object_id": assignment.target_object_id,
            "deadline_at": assignment.deadline_at,
            "progress_completion": assignment.progress_completion,
            "progress_note": assignment.progress_note,
            "next_commitment_date": assignment.next_commitment_date,
            "revision": assignment.revision,
            "created_at": assignment.created_at,
            "updated_at": assignment.updated_at,
        },
        "allowed_actions": sorted(list(ALLOWED_ACTIONS_BY_STATUS.get(assignment.status, set()))),
        "status_history": [
            {
                "id": item.id,
                "from_status": item.from_status,
                "to_status": item.to_status,
                "reason": item.reason,
                "actor_id": item.actor_id,
                "created_at": item.created_at,
            }
            for item in history
        ],
        "evidence": [
            {
                "id": item.id,
                "verification_status": item.verification_status,
                "business_outcome": item.business_outcome,
                "technical_error_code": item.technical_error_code,
                "payload": item.payload,
                "created_at": item.created_at,
            }
            for item in evidence
        ],
        "revisions": [
            {
                "id": item.id,
                "revision": item.revision,
                "diff": item.diff,
                "actor_id": item.actor_id,
                "created_at": item.created_at,
            }
            for item in revisions
        ],
    }


@router.post("/{assignment_id}/actions", status_code=status.HTTP_202_ACCEPTED, response_model=JobAccepted)
def run_assignment_action(
    assignment_id: str,
    payload: AssignmentActionRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    _token: str = Depends(require_bearer_token),
    _role: str = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if assignment.revision != payload.revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CONFLICT_EDIT")
    allowed_actions = ALLOWED_ACTIONS_BY_STATUS.get(assignment.status, set())
    if payload.action not in allowed_actions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "ACTION_NOT_ALLOWED",
                "message": "Действие недоступно для текущего статуса",
                "details": {"status": assignment.status, "allowed_actions": sorted(list(allowed_actions))},
                "retryable": False,
                "correlation_id": "assignment-action-guard",
            },
        )

    job_id = generate_job_id()
    db.add(
        Job(
            id=job_id,
            kind=f"assignment_action:{payload.action}",
            status="queued",
            payload={"assignment_id": assignment_id, "action": payload.action, "payload": payload.payload},
        )
    )
    db.commit()
    response.headers["Location"] = f"/api/v1/jobs/{job_id}"
    return JobAccepted(job_id=job_id)
